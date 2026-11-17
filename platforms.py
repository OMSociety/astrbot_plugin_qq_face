"""QQ platform capability negotiation.

OneBot is a transport, not proof that the peer is QQ. Decisions are cached per
AstrBot platform instance and can be overridden explicitly in plugin settings.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

_DENIED_APP_MARKERS = ("flandora", "wechat", "weixin")
_KNOWN_QQ_APP_MARKERS = (
    "snowluma",
    "napcat",
    "llonebot",
    "lagrange",
    "go-cqhttp",
    "gocqhttp",
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PlatformDecision:
    """The rendering mode selected for one platform instance."""

    platform_id: str
    adapter: str
    mode: str
    reason: str
    app_name: str = ""
    app_version: str = ""
    catalog_payload: Mapping[str, Any] | None = None
    checked_at: float = 0.0

    @property
    def enabled(self) -> bool:
        return self.mode == "native"


class PlatformResolver:
    """Resolve QQ-capable adapters and their per-instance face modes."""

    def __init__(
        self,
        overrides: Mapping[str, Any] | None = None,
        *,
        retry_seconds: int = 300,
    ) -> None:
        self.overrides = {
            str(key): str(value).strip().lower()
            for key, value in (overrides or {}).items()
        }
        self.retry_seconds = retry_seconds
        self._cache: dict[str, PlatformDecision] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def resolve(self, event: Any, *, force: bool = False) -> PlatformDecision:
        """Return native or disabled for the current event."""
        adapter = str(event.get_platform_name() or "")
        platform_id = str(event.get_platform_id() or adapter or "unknown")
        override = self.overrides.get(platform_id, self.overrides.get(adapter, "auto"))
        now = time.time()
        if override == "disabled":
            return PlatformDecision(platform_id, adapter, "disabled", "override")
        if adapter != "aiocqhttp":
            return PlatformDecision(platform_id, adapter, "disabled", "not_qq")

        cached = self._cache.get(platform_id)
        if (
            not force
            and cached
            and (cached.enabled or now - cached.checked_at < self.retry_seconds)
        ):
            return cached
        lock = self._locks.setdefault(platform_id, asyncio.Lock())
        async with lock:
            cached = self._cache.get(platform_id)
            if (
                not force
                and cached
                and (cached.enabled or now - cached.checked_at < self.retry_seconds)
            ):
                return cached
            decision = await self._probe(event, platform_id, adapter, override)
            self._cache[platform_id] = decision
            return decision

    async def _probe(
        self,
        event: Any,
        platform_id: str,
        adapter: str,
        override: str,
    ) -> PlatformDecision:
        now = time.time()
        bot = getattr(event, "bot", None)
        if bot is None or not hasattr(bot, "call_action"):
            return PlatformDecision(
                platform_id,
                adapter,
                "disabled",
                "bot_unavailable",
                checked_at=now,
            )

        app_name = ""
        app_version = ""
        try:
            response = await asyncio.wait_for(
                bot.call_action("get_version_info"), timeout=5
            )
            data = (
                response.get("data", response) if isinstance(response, Mapping) else {}
            )
            if isinstance(data, Mapping):
                app_name = str(data.get("app_name", "")).strip()
                app_version = str(data.get("app_version", "")).strip()
        except Exception as exc:
            logger.debug("Unable to query OneBot version information: %s", exc)

        normalized_name = app_name.casefold()
        if any(marker in normalized_name for marker in _DENIED_APP_MARKERS):
            return PlatformDecision(
                platform_id,
                adapter,
                "disabled",
                "non_qq_onebot",
                app_name,
                app_version,
                checked_at=now,
            )
        if override == "enabled":
            return PlatformDecision(
                platform_id,
                adapter,
                "native",
                "forced",
                app_name,
                app_version,
                checked_at=now,
            )
        if any(marker in normalized_name for marker in _KNOWN_QQ_APP_MARKERS):
            return PlatformDecision(
                platform_id,
                adapter,
                "native",
                "known_qq",
                app_name,
                app_version,
                checked_at=now,
            )

        try:
            payload = await asyncio.wait_for(
                bot.call_action("fetch_sys_faces", refresh=False), timeout=8
            )
            if _contains_numeric_faces(payload):
                return PlatformDecision(
                    platform_id,
                    adapter,
                    "native",
                    "catalog_capability",
                    app_name,
                    app_version,
                    payload,
                    now,
                )
        except Exception as exc:
            logger.debug("OneBot peer has no usable QQ face catalog: %s", exc)
        return PlatformDecision(
            platform_id,
            adapter,
            "disabled",
            "unverified_onebot",
            app_name,
            app_version,
            checked_at=now,
        )


def _contains_numeric_faces(payload: Any) -> bool:
    if not isinstance(payload, Mapping):
        return False
    data = payload.get("data", payload)
    if not isinstance(data, Mapping):
        return False
    packs = data.get("packs")
    if not isinstance(packs, list):
        return False
    return any(
        isinstance(item, Mapping) and str(item.get("q_sid", "")).isdecimal()
        for pack in packs
        if isinstance(pack, Mapping)
        for item in (
            pack.get("emojis", []) if isinstance(pack.get("emojis"), list) else []
        )
    )
