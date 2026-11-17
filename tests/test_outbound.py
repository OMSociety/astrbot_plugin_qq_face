import asyncio
from types import SimpleNamespace

from astrbot.api.event import MessageChain
from astrbot.api.message_components import Face, Image, Plain
from astrbot_plugin_qq_face.models import FaceCatalog, FaceInfo
from astrbot_plugin_qq_face.outbound import OutboundRenderer, install_send_wrapper

CATALOG = FaceCatalog(
    [
        FaceInfo(13, "/呲牙"),
        FaceInfo(178, "/斜眼笑"),
        FaceInfo(182, "/笑哭"),
        FaceInfo(264, "/捂脸"),
        FaceInfo(317, "/菜汪", animation_type=1),
    ]
)


def component_types(chain: MessageChain) -> list[str]:
    return [type(component).__name__ for component in chain.chain]


def plain_text(chain: MessageChain) -> str:
    return "".join(
        component.text for component in chain.chain if isinstance(component, Plain)
    )


def test_dynamic_sticker_splits_following_text() -> None:
    message = MessageChain([Plain("前面<face:菜汪>后面")])

    rendered = asyncio.run(OutboundRenderer().render(message, CATALOG, split=True))

    assert len(rendered) == 2
    assert component_types(rendered[0]) == ["Plain", "Face"]
    assert rendered[0].chain[1].id == 317
    assert plain_text(rendered[1]) == "后面"


def test_classic_faces_all_convert_without_a_limit() -> None:
    message = MessageChain([Plain("A<face:呲牙>B<face:笑哭>C")])

    rendered = asyncio.run(OutboundRenderer().render(message, CATALOG, split=True))

    assert len(rendered) == 1
    assert component_types(rendered[0]) == ["Plain", "Face", "Plain", "Face", "Plain"]
    assert [item.id for item in rendered[0].chain if isinstance(item, Face)] == [
        13,
        182,
    ]


def test_unknown_marker_and_code_are_not_rewritten() -> None:
    unknown = MessageChain([Plain("<face:不存在>")])
    code = MessageChain([Plain("`<face:呲牙>`")])

    assert asyncio.run(OutboundRenderer().render(unknown, CATALOG, split=True)) == [
        unknown
    ]
    assert asyncio.run(OutboundRenderer().render(code, CATALOG, split=True)) == [code]


def test_existing_dynamic_face_is_split_but_not_duplicated() -> None:
    message = MessageChain([Face(id=317), Plain("正文")])

    rendered = asyncio.run(OutboundRenderer().render(message, CATALOG, split=True))

    assert len(rendered) == 2
    assert component_types(rendered[0]) == ["Face"]
    assert plain_text(rendered[1]) == "正文"


def test_plain_media_message_is_untouched(tmp_path) -> None:
    message = MessageChain(
        [Plain("前文"), Image.fromFileSystem(str(tmp_path / "x.png")), Plain("后文")]
    )

    rendered = asyncio.run(OutboundRenderer().render(message, CATALOG, split=True))

    assert rendered == [message]


def test_send_wrapper_splits_only_once() -> None:
    sent = []

    async def original_send(message):
        sent.append(message)

    event = SimpleNamespace(send=original_send)
    install_send_wrapper(event, OutboundRenderer(), CATALOG)
    install_send_wrapper(event, OutboundRenderer(), CATALOG)

    asyncio.run(event.send(MessageChain([Plain("<face:菜汪>正文")])))

    assert len(sent) == 2
    assert component_types(sent[0]) == ["Face"]
    assert plain_text(sent[1]) == "正文"


def test_face_without_id_falls_back_to_readable_text() -> None:
    message = MessageChain([Face.construct(id=None)])

    rendered = asyncio.run(OutboundRenderer().render(message, CATALOG, split=True))

    assert component_types(rendered[0]) == ["Plain"]
    assert plain_text(rendered[0]) == "［QQ表情：未知］"


def test_unknown_existing_face_is_preserved() -> None:
    message = MessageChain([Face(id=99999)])

    rendered = asyncio.run(OutboundRenderer().render(message, CATALOG, split=True))

    assert len(rendered) == 1
    assert component_types(rendered[0]) == ["Face"]
    assert rendered[0].chain[0].id == 99999
