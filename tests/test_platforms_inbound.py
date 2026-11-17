import asyncio
from types import SimpleNamespace

from astrbot.api.message_components import At, Face, Plain
from astrbot_plugin_qq_face.inbound import annotate_incoming_faces
from astrbot_plugin_qq_face.models import FaceCatalog, FaceInfo
from astrbot_plugin_qq_face.platforms import PlatformResolver

CATALOG_PAYLOAD = {
    "packs": [
        {
            "pack_name": "测试",
            "emojis": [{"q_sid": "13", "q_des": "/呲牙"}],
        }
    ]
}


class FakeBot:
    def __init__(self, app_name: str = "SnowLuma", faces: object = None) -> None:
        self.app_name = app_name
        self.faces = faces
        self.calls = []

    async def call_action(self, action: str, **kwargs):
        self.calls.append((action, kwargs))
        if action == "get_version_info":
            return {"app_name": self.app_name, "app_version": "1.0"}
        if action == "fetch_sys_faces":
            if isinstance(self.faces, Exception):
                raise self.faces
            return self.faces
        raise AssertionError(action)


class FakeEvent:
    def __init__(self, adapter: str, platform_id: str, bot: object = None) -> None:
        self.adapter = adapter
        self.platform_id = platform_id
        self.bot = bot
        self.message_obj = SimpleNamespace(message=[])
        self.message_str = ""

    def get_platform_name(self) -> str:
        return self.adapter

    def get_platform_id(self) -> str:
        return self.platform_id


def resolve(event: FakeEvent, overrides=None):
    return asyncio.run(PlatformResolver(overrides).resolve(event))


def test_non_qq_platform_never_probes_bot() -> None:
    bot = FakeBot()
    decision = resolve(FakeEvent("telegram", "tg", bot))
    assert decision.mode == "disabled"
    assert decision.reason == "not_qq"
    assert bot.calls == []


def test_known_qq_peers_use_native_faces_without_catalog_requirement() -> None:
    for name in ("SnowLuma", "NapCat.Onebot", "LLOneBot", "Lagrange.Onebot"):
        bot = FakeBot(name)
        decision = resolve(FakeEvent("aiocqhttp", name, bot))
        assert decision.mode == "native"
        assert decision.reason == "known_qq"
        assert [call[0] for call in bot.calls] == ["get_version_info"]


def test_flandora_is_denied_even_when_forced() -> None:
    decision = resolve(
        FakeEvent("aiocqhttp", "wechat", FakeBot("Flandora")),
        {"wechat": "enabled"},
    )
    assert decision.mode == "disabled"
    assert decision.reason == "non_qq_onebot"


def test_unknown_peer_needs_positive_catalog_capability() -> None:
    with_faces = resolve(
        FakeEvent("aiocqhttp", "fork", FakeBot("CommunityFork", CATALOG_PAYLOAD))
    )
    without_faces = resolve(
        FakeEvent(
            "aiocqhttp",
            "other",
            FakeBot("UnknownBridge", RuntimeError("unsupported")),
        )
    )
    assert with_faces.mode == "native"
    assert with_faces.catalog_payload == CATALOG_PAYLOAD
    assert without_faces.mode == "disabled"
    assert without_faces.reason == "unverified_onebot"


def test_non_onebot_and_override_modes() -> None:
    for adapter in ("qq_official", "qq_official_webhook"):
        decision = resolve(
            FakeEvent(adapter, "official"),
            {"official": "enabled"},
        )
        assert decision.mode == "disabled"
        assert decision.reason == "not_qq"

    forced = resolve(
        FakeEvent("aiocqhttp", "unknown", FakeBot("Unknown")),
        {"unknown": "enabled"},
    )
    disabled = resolve(
        FakeEvent("aiocqhttp", "snow", FakeBot("SnowLuma")),
        {"snow": "disabled"},
    )
    assert forced.mode == "native"
    assert disabled.mode == "disabled"


def test_platform_cache_is_isolated_per_instance() -> None:
    async def scenario() -> None:
        resolver = PlatformResolver()
        first = FakeEvent("aiocqhttp", "one", FakeBot("SnowLuma"))
        second = FakeEvent("aiocqhttp", "two", FakeBot("Flandora"))
        assert (await resolver.resolve(first)).mode == "native"
        assert (await resolver.resolve(second)).mode == "disabled"
        assert (await resolver.resolve(first)).app_name == "SnowLuma"

    asyncio.run(scenario())


def test_inbound_annotation_preserves_text_face_order() -> None:
    event = FakeEvent("aiocqhttp", "qq")
    event.message_obj.message = [
        Plain("你好"),
        At(qq="42", name="小明"),
        Face(id=317),
        Plain("再见"),
        Face(id=99999),
    ]
    catalog = FaceCatalog([FaceInfo(317, "/菜汪", animation_type=1)])

    assert annotate_incoming_faces(event, catalog)
    assert event.message_str == "你好@小明 [QQ表情:/菜汪]再见[QQ表情:ID 99999]"
    assert len(event.message_obj.message) == 5


def test_forced_mode_still_requires_a_probe_bot() -> None:
    decision = resolve(
        FakeEvent("aiocqhttp", "unknown", None),
        {"unknown": "enabled"},
    )
    assert decision.mode == "disabled"
    assert decision.reason == "bot_unavailable"


def test_inbound_face_without_id_is_ignored() -> None:
    event = FakeEvent("aiocqhttp", "qq")
    event.message_obj.message = [Face.construct(id=None), Face(id=317)]
    catalog = FaceCatalog([FaceInfo(317, "/菜汪", animation_type=1)])

    assert annotate_incoming_faces(event, catalog)
    assert event.message_str == "[QQ表情:/菜汪]"
