import json
from pathlib import Path

from astrbot_plugin_qq_face.markup import FaceFragment, TextFragment, parse_face_markup
from astrbot_plugin_qq_face.models import FaceCatalog, normalize_face_name


def test_bundled_catalog_is_complete_and_resolves_names() -> None:
    path = Path(__file__).parents[1] / "assets" / "default_catalog.json"
    catalog = FaceCatalog.from_payload(json.loads(path.read_text(encoding="utf-8")))

    assert len(catalog) == 294
    assert catalog.resolve("呲牙").id == 13
    assert catalog.resolve("/菜汪").id == 317
    assert catalog.resolve("菜狗").id == 317
    assert catalog.resolve("317").name == "/菜汪"
    assert catalog.resolve("菜汪").is_animated
    assert catalog.resolve("不存在") is None


def test_dynamic_catalog_keeps_animation_and_aliases() -> None:
    payload = {
        "packs": [
            {
                "pack_name": "测试包",
                "emojis": [
                    {
                        "q_sid": "317",
                        "q_des": "/菜汪",
                        "emoji_name_alias": [],
                        "ani_sticker_type": 1,
                        "url": "https://gxh.vip.qq.com/317.zip",
                    },
                    {"q_sid": "😂", "q_des": "笑哭"},
                ],
            }
        ]
    }
    catalog = FaceCatalog.from_payload(payload, {"绿狗": "菜汪", "歪嘴": "178"})

    assert len(catalog) == 1
    assert catalog.resolve("菜狗").animation_type == 1
    assert catalog.resolve("绿 狗").id == 317
    assert catalog.animated_count == 1


def test_cache_payload_and_name_normalization() -> None:
    catalog = FaceCatalog.from_payload(
        {
            "faces": [
                {
                    "id": 13,
                    "name": "/呲牙",
                    "aliases": ["龇牙"],
                    "animation_type": 0,
                }
            ]
        }
    )
    assert catalog.resolve("龇 牙").id == 13
    assert normalize_face_name(" /呲 牙 ") == "呲牙"


def test_markup_ignores_fenced_and_inline_code() -> None:
    fragments = parse_face_markup(
        "前<face:呲牙>中 `<face:捂脸>`\n```text\n<face:菜汪>\n```\n后<face:笑哭>"
    )
    faces = [item for item in fragments if isinstance(item, FaceFragment)]
    text = "".join(item.text for item in fragments if isinstance(item, TextFragment))

    assert [item.token for item in faces] == ["呲牙", "笑哭"]
    assert "`<face:捂脸>`" in text
    assert "<face:菜汪>" in text


def test_markup_preserves_unknown_and_unclosed_code() -> None:
    fragments = parse_face_markup("```python\n<face:呲牙>")
    assert len(fragments) == 1
    assert isinstance(fragments[0], TextFragment)
    assert fragments[0].text == "```python\n<face:呲牙>"
