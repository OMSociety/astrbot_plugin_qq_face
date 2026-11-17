"""AstrBot QQ native face plugin."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import Plain
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star
from astrbot.core.agent.message import TextPart
from astrbot.core.star.star_tools import StarTools

from .catalog import CatalogStore
from .inbound import annotate_incoming_faces
from .outbound import OutboundRenderer, install_send_wrapper
from .platforms import PlatformDecision, PlatformResolver
from .prompts import build_face_prompt

PLUGIN_NAME = "qq_face"
_DECISION_KEY = "qq_face:decision"
_DEFAULT_PROMPT_NAMES = [
    "呲牙",
    "微笑",
    "笑哭",
    "斜眼笑",
    "捂脸",
    "害羞",
    "可怜",
    "点赞",
    "菜汪",
    "打call",
    "拥抱",
    "送花",
]


class QQFacePlugin(Star):
    """Read and send QQ faces only on platforms that actually support them."""

    def __init__(self, context: Context, config: dict | None = None) -> None:
        super().__init__(context)
        self.config = config or {}
        self.enable_inbound = bool(self.config.get("enable_inbound", True))
        self.prompt_names = [
            str(name)
            for name in self.config.get("prompt_face_names", _DEFAULT_PROMPT_NAMES)
        ]
        data_dir = StarTools.get_data_dir(PLUGIN_NAME)
        self.catalogs = CatalogStore(
            data_dir,
            Path(__file__).parent / "assets" / "default_catalog.json",
            _mapping_option(self.config.get("face_aliases"), "face_aliases"),
            24,
        )
        self.platforms = PlatformResolver(
            _mapping_option(self.config.get("platform_overrides"), "platform_overrides")
        )
        self.renderer = OutboundRenderer()
        self._refresh_tasks: dict[str, asyncio.Task[None]] = {}
        self._adopted_platforms: set[str] = set()

    @filter.event_message_type(filter.EventMessageType.ALL, priority=1000)
    async def prepare_qq_event(self, event: AstrMessageEvent) -> None:
        """在唤醒检查和直接发送前识别平台能力。"""
        try:
            decision, catalog = await self._context_for(event)
            if not decision.enabled:
                return
            install_send_wrapper(event, self.renderer, catalog)
            if self.enable_inbound:
                annotate_incoming_faces(event, catalog)
            self._schedule_catalog_refresh(event, decision)
        except Exception as exc:
            logger.warning("QQ face event preparation failed open: %s", exc)

    @filter.on_llm_request()
    async def add_face_prompt(
        self,
        event: AstrMessageEvent,
        request: ProviderRequest,
    ) -> None:
        """为本次模型请求添加临时的表情语法提示。"""
        decision, catalog = await self._context_for(event)
        if not decision.enabled:
            return
        prompt = build_face_prompt(catalog, self.prompt_names)
        if prompt:
            request.extra_user_content_parts.append(
                TextPart(text=prompt).mark_as_temp()
            )

    @filter.on_decorating_result()
    async def convert_result_before_tts(self, event: AstrMessageEvent) -> None:
        """在语音合成前转换表情标记，并在最终发送时按顺序拆条。"""
        decision, catalog = await self._context_for(event)
        result = event.get_result()
        if not decision.enabled or result is None or not result.chain:
            return
        rendered = await self.renderer.render(result, catalog, split=False)
        result.chain = rendered[0].chain

    @filter.command("表情", alias={"face"})
    async def face_command(self, event: AstrMessageEvent) -> Any:
        """查询状态、列出表情或手动发送 QQ 表情。"""
        arguments = _command_arguments(event.message_str)
        if not arguments:
            yield event.plain_result(
                "用法：/表情 <名字或ID>；/表情 list [关键词]；"
                "/表情 status；英文别名 /face"
            )
            return
        decision, catalog = await self._context_for(event)
        action, _, rest = arguments.partition(" ")
        action = action.casefold()
        if action == "status":
            yield event.plain_result(_status_text(decision, catalog))
            return
        if not decision.enabled:
            yield event.plain_result(
                f"当前平台未启用 QQ 表情（{decision.reason}）。"
                "可在插件配置中设置平台实例覆盖。"
            )
            return
        if action == "list":
            yield event.plain_result(_catalog_list(catalog, rest.strip()))
            return
        token = rest.strip() if action == "send" else arguments
        face = catalog.resolve(token)
        if face is None:
            yield event.plain_result(
                "没有这个表情。用 /face list [关键词] 查询可用名字。"
            )
            return
        yield event.chain_result([Plain(f"<face:{face.name}>")])

    async def terminate(self) -> None:
        """Cancel background refreshes."""
        tasks = list(self._refresh_tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _context_for(
        self, event: AstrMessageEvent
    ) -> tuple[PlatformDecision, Any]:
        decision = event.get_extra(_DECISION_KEY)
        if not isinstance(decision, PlatformDecision):
            decision = await self.platforms.resolve(event)
            event.set_extra(_DECISION_KEY, decision)
        catalog_key = decision.platform_id
        if (
            decision.catalog_payload is not None
            and decision.platform_id not in self._adopted_platforms
        ):
            catalog = await self.catalogs.adopt(
                decision.platform_id, decision.catalog_payload
            )
            self._adopted_platforms.add(decision.platform_id)
        else:
            catalog = await self.catalogs.get(catalog_key)
        return decision, catalog

    def _schedule_catalog_refresh(
        self, event: AstrMessageEvent, decision: PlatformDecision
    ) -> None:
        if decision.catalog_payload is not None:
            return
        bot = getattr(event, "bot", None)
        platform_id = decision.platform_id
        if bot is None or platform_id in self._refresh_tasks:
            return

        async def refresh() -> None:
            try:
                await self.catalogs.refresh(platform_id, bot)
            finally:
                self._refresh_tasks.pop(platform_id, None)

        self._refresh_tasks[platform_id] = asyncio.create_task(refresh())


def _command_arguments(message: str) -> str:
    match = re.match(r"^\s*/?(?:face|表情)(?:\s+|$)([\s\S]*)", message, re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _mapping_option(value: Any, option_name: str) -> dict[str, Any]:
    """Read a JSON object from a free-form WebUI text setting."""
    if value is None or value == "":
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            logger.warning("QQ face setting %s is not valid JSON", option_name)
            return {}
        if isinstance(parsed, dict):
            return parsed
    logger.warning("QQ face setting %s must be a JSON object", option_name)
    return {}


def _status_text(decision: PlatformDecision, catalog: Any) -> str:
    mode_names = {
        "native": "OneBot 原生 Face",
        "disabled": "关闭",
    }
    lines = [
        f"平台：{decision.adapter} / {decision.platform_id}",
        f"模式：{mode_names.get(decision.mode, decision.mode)}（{decision.reason}）",
        f"目录：{len(catalog)} 个表情，其中动态 {catalog.animated_count} 个，"
        f"来源 {catalog.source}",
    ]
    if decision.app_name:
        lines.insert(1, f"协议端：{decision.app_name} {decision.app_version}".rstrip())
    return "\n".join(lines)


def _catalog_list(catalog: Any, query: str) -> str:
    keyword = query.casefold()
    faces = sorted(
        catalog.faces.values(),
        key=lambda item: (item.is_animated, item.id),
    )
    if keyword:
        faces = [
            face
            for face in faces
            if keyword in face.name.casefold()
            or keyword in face.pack.casefold()
            or any(keyword in alias.casefold() for alias in face.aliases)
        ]
    shown = faces[:40]
    if not shown:
        return "没有匹配的表情。"
    entries = [
        f"{face.name}({face.id}{'，动态' if face.is_animated else ''})"
        for face in shown
    ]
    suffix = f"\n共 {len(faces)} 个匹配项，仅显示前 40 个。" if len(faces) > 40 else ""
    return "、".join(entries) + suffix
