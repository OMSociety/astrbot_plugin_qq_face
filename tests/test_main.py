import asyncio
from pathlib import Path
from types import SimpleNamespace

from astrbot.api.event import MessageChain
from astrbot.api.message_components import Face, Plain
from astrbot.core.star.star_manager import PluginManager
from astrbot.core.star.star_tools import StarTools
from astrbot_plugin_qq_face.main import QQFacePlugin, _command_arguments
from astrbot_plugin_qq_face.platforms import PlatformDecision


class FakeBot:
    async def call_action(self, action: str, **kwargs):
        if action == "get_version_info":
            return {"app_name": "SnowLuma", "app_version": "2.1.1-node"}
        if action == "fetch_sys_faces":
            return {
                "packs": [
                    {
                        "pack_name": "测试",
                        "emojis": [
                            {"q_sid": "13", "q_des": "/呲牙"},
                            {
                                "q_sid": "317",
                                "q_des": "/菜汪",
                                "ani_sticker_type": 1,
                            },
                        ],
                    }
                ]
            }
        raise AssertionError(action)


class FakeEvent:
    def __init__(self) -> None:
        self.bot = FakeBot()
        self.message_str = "你好"
        self.message_obj = SimpleNamespace(message=[Plain("你好"), Face(id=317)])
        self.extras = {}
        self.result = None
        self.sent = []

    def get_platform_name(self):
        return "aiocqhttp"

    def get_platform_id(self):
        return "test-instance"

    def set_extra(self, key, value):
        self.extras[key] = value

    def get_extra(self, key, default=None):
        return self.extras.get(key, default)

    def get_result(self):
        return self.result

    async def send(self, message):
        self.sent.append(message)

    def plain_result(self, text):
        return MessageChain([Plain(text)])

    def chain_result(self, chain):
        return MessageChain(chain)


def make_plugin(monkeypatch, tmp_path) -> QQFacePlugin:
    monkeypatch.setattr(
        StarTools,
        "get_data_dir",
        classmethod(lambda cls, plugin_name=None: tmp_path),
    )
    plugin = QQFacePlugin(object())
    monkeypatch.setattr(plugin, "_schedule_catalog_refresh", lambda *args: None)
    return plugin


def test_plugin_prepare_prompt_decorate_and_send(monkeypatch, tmp_path) -> None:
    async def scenario() -> None:
        plugin = make_plugin(monkeypatch, tmp_path)
        event = FakeEvent()

        await plugin.prepare_qq_event(event)

        assert "enable_streaming" not in event.extras
        assert event.message_str == "你好[QQ表情:/菜汪]"
        assert event._qq_native_face_send_wrapped is True

        request = SimpleNamespace(extra_user_content_parts=[])
        await plugin.add_face_prompt(event, request)
        assert len(request.extra_user_content_parts) == 1
        prompt = request.extra_user_content_parts[0].text
        assert "<face:表情名>" in prompt
        assert "不要解释、复述、总结或回赠" in prompt
        assert "每条消息最多" not in prompt

        event.result = MessageChain([Plain("看<face:菜汪>正文")])
        await plugin.convert_result_before_tts(event)
        assert [type(item).__name__ for item in event.result.chain] == [
            "Plain",
            "Face",
            "Plain",
        ]

        await event.send(event.result)
        assert len(event.sent) == 2
        assert event.sent[0].chain[-1].id == 317
        assert event.sent[1].chain[0].text == "正文"
        await plugin.terminate()

    asyncio.run(scenario())


def test_face_command_uses_dynamic_names(monkeypatch, tmp_path) -> None:
    async def scenario() -> None:
        plugin = make_plugin(monkeypatch, tmp_path)
        event = FakeEvent()
        event.message_obj.message = []
        event.message_str = "/表情 菜汪"
        await plugin.prepare_qq_event(event)

        results = [result async for result in plugin.face_command(event)]
        assert len(results) == 1
        assert results[0].chain[0].text == "<face:/菜汪>"

        await event.send(results[0])
        assert len(event.sent) == 1
        assert event.sent[0].chain[0].id == 317
        await plugin.terminate()

    asyncio.run(scenario())


def test_disabled_platform_does_not_inject(monkeypatch, tmp_path) -> None:
    async def scenario() -> None:
        plugin = make_plugin(monkeypatch, tmp_path)
        event = FakeEvent()
        event.adapter = "telegram"
        event.get_platform_name = lambda: "telegram"
        event.message_obj.message = [Plain("hello")]
        event.message_str = "hello"

        await plugin.prepare_qq_event(event)
        request = SimpleNamespace(extra_user_content_parts=[])
        await plugin.add_face_prompt(event, request)

        assert request.extra_user_content_parts == []
        assert not hasattr(event, "_qq_native_face_send_wrapped")
        await plugin.terminate()

    asyncio.run(scenario())


def test_command_argument_parser() -> None:
    assert _command_arguments("/表情 list 菜") == "list 菜"
    assert _command_arguments("表情 捂脸") == "捂脸"
    assert _command_arguments("/表情") == ""
    assert _command_arguments("/face list 菜") == "list 菜"
    assert _command_arguments("face 捂脸") == "捂脸"
    assert _command_arguments("/face") == ""
    assert _command_arguments("hello") == ""


def test_decision_enabled_property() -> None:
    assert PlatformDecision("id", "adapter", "native", "test").enabled
    assert not PlatformDecision("id", "adapter", "disabled", "test").enabled


def test_i18n_layout_matches_host_loader() -> None:
    root = Path(__file__).resolve().parents[1]
    translations = PluginManager._load_plugin_i18n(str(root))

    assert set(translations) == {"zh-CN", "en-US"}
    assert translations["zh-CN"]["metadata"]["display_name"] == "QQ 大黄脸"
    assert (
        translations["en-US"]["metadata"]["short_desc"]
        == "Read and send native QQ faces naturally"
    )


def test_handler_descriptions_are_chinese() -> None:
    assert (
        QQFacePlugin.prepare_qq_event.__doc__ == "在唤醒检查和直接发送前识别平台能力。"
    )
    assert (
        QQFacePlugin.add_face_prompt.__doc__ == "为本次模型请求添加临时的表情语法提示。"
    )
    assert (
        QQFacePlugin.convert_result_before_tts.__doc__
        == "在语音合成前转换表情标记，并在最终发送时按顺序拆条。"
    )
    assert QQFacePlugin.face_command.__doc__ == "查询状态、列出表情或手动发送 QQ 表情。"
