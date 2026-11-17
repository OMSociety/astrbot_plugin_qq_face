"""Inline-marker conversion and ordered OneBot message splitting."""

from __future__ import annotations

from typing import Any

from astrbot.api.event import MessageChain
from astrbot.api.message_components import Face, Plain

from .markup import FaceFragment, TextFragment, parse_face_markup
from .models import FaceCatalog, FaceInfo


class OutboundRenderer:
    """Render known markers as native Face components in their original order."""

    async def render(
        self,
        message: MessageChain,
        catalog: FaceCatalog,
        *,
        split: bool,
    ) -> list[MessageChain]:
        """Convert one chain and optionally split after animated stickers."""
        if not _has_face_content(message, catalog):
            return [message]
        chains: list[MessageChain] = []
        current: list[Any] = []

        def flush() -> None:
            nonlocal current
            if current:
                chains.append(message.derive(current))
                current = []

        for component in message.chain:
            if isinstance(component, Plain):
                for fragment in parse_face_markup(component.text):
                    if isinstance(fragment, TextFragment):
                        _append(current, Plain(fragment.text))
                        continue
                    face = catalog.resolve(fragment.token)
                    if face is None:
                        _append(current, Plain(fragment.raw))
                    else:
                        _append_face(current, face, split, flush)
            elif isinstance(component, Face):
                if component.id is None:
                    _append(current, Plain("［QQ表情：未知］"))
                    continue
                face = catalog.get(int(component.id))
                if face is None:
                    _append(current, component)
                else:
                    _append_face(current, face, split, flush)
            else:
                _append(current, component)
        if current or not chains:
            chains.append(message.derive(current))
        return chains


def _has_face_content(message: MessageChain, catalog: FaceCatalog) -> bool:
    for component in message.chain:
        if isinstance(component, Face):
            return True
        if isinstance(component, Plain) and any(
            isinstance(fragment, FaceFragment) and catalog.resolve(fragment.token)
            for fragment in parse_face_markup(component.text)
        ):
            return True
    return False


def _append_face(
    current: list[Any],
    face: FaceInfo,
    split: bool,
    flush: Any,
) -> None:
    _append(current, Face(id=face.id))
    if split and face.is_animated:
        flush()


def _append(components: list[Any], component: Any) -> None:
    if isinstance(component, Plain) and not component.text:
        return
    if (
        isinstance(component, Plain)
        and components
        and isinstance(components[-1], Plain)
    ):
        components[-1] = Plain(components[-1].text + component.text)
    else:
        components.append(component)


def install_send_wrapper(
    event: Any,
    renderer: OutboundRenderer,
    catalog: FaceCatalog,
) -> None:
    """Convert direct sends too, while keeping the wrapper idempotent."""
    if getattr(event, "_qq_native_face_send_wrapped", False):
        return
    original_send = event.send

    async def send_with_native_faces(message: MessageChain) -> None:
        rendered = await renderer.render(message, catalog, split=True)
        for chain in rendered:
            if chain.chain or not message.chain:
                await original_send(chain)

    event.send = send_with_native_faces
    event._qq_native_face_send_wrapped = True
