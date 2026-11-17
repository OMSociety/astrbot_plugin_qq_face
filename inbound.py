"""Inbound QQ face annotation that preserves component order."""

from __future__ import annotations

from typing import Any

from astrbot.api.message_components import At, Face, Plain

from .models import FaceCatalog


def annotate_incoming_faces(event: Any, catalog: FaceCatalog) -> bool:
    """Add readable face names to message_str while preserving the real chain."""
    chain = getattr(event.message_obj, "message", None) or []
    if not any(isinstance(component, Face) for component in chain):
        return False
    parts: list[str] = []
    for component in chain:
        if isinstance(component, Plain):
            parts.append(component.text)
        elif isinstance(component, Face) and component.id is not None:
            face = catalog.get(int(component.id))
            label = face.name if face is not None else f"ID {component.id}"
            parts.append(f"[QQ表情:{label}]")
        elif isinstance(component, At):
            parts.append(f"@{component.name or component.qq} ")
    text = "".join(parts).strip()
    if not text:
        return False
    event.message_str = text
    return True
