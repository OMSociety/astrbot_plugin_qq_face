"""Temporary, non-authoritative prompt text for natural face usage."""

from __future__ import annotations

from collections.abc import Iterable

from .models import FaceCatalog


def build_face_prompt(
    catalog: FaceCatalog,
    preferred_names: Iterable[str],
    *,
    limit: int = 24,
) -> str:
    """Build a compact prompt containing face names from the active catalog."""
    selected = []
    seen: set[int] = set()
    for name in preferred_names:
        face = catalog.resolve(str(name))
        if face is not None and face.id not in seen:
            selected.append(face.name)
            seen.add(face.id)
        if len(selected) >= limit:
            break
    if not selected:
        for face in sorted(catalog.faces.values(), key=lambda item: item.id):
            if not face.is_animated:
                selected.append(face.name)
            if len(selected) >= limit:
                break
    if not selected:
        return ""
    names = "、".join(selected)
    example = selected[0]
    return (
        "QQ 表情只是弱语气线索，不是需要单独回答的问题。"
        "不要解释、复述、总结或回赠用户发来的表情；没有文字时也不要硬猜含义，"
        "按日常聊天简短自然回应即可。\n"
        "只有在表达明显更自然时才偶尔插入 QQ 原生表情，语法为 <face:表情名>，"
        f"例如 <face:{example}>。\n"
        f"当前可用：{names}。\n"
        "不要堆砌表情，不要为了表情牺牲语气与内容。"
        "未列出的名字不要使用；代码块、行内代码、技术语法和引用示例中不要写表情标记。"
    )
