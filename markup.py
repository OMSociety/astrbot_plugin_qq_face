"""Code-aware parsing for inline QQ face markers."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TextFragment:
    """Text that must remain unchanged."""

    text: str


@dataclass(frozen=True, slots=True)
class FaceFragment:
    """A candidate <face:name> marker outside code spans."""

    token: str
    raw: str


Fragment = TextFragment | FaceFragment

_CODE_RE = re.compile(
    r"```[\s\S]*?(?:```|\Z)|~~~[\s\S]*?(?:~~~|\Z)|`[^`\r\n]*`",
)
_FACE_RE = re.compile(r"<face:([^<>\r\n]{1,64})>", re.IGNORECASE)


def parse_face_markup(text: str) -> list[Fragment]:
    """Split text into literal Markdown code and face-marker segments."""
    if not text:
        return []
    fragments: list[Fragment] = []
    cursor = 0
    for code_match in _CODE_RE.finditer(text):
        _parse_text_region(text[cursor : code_match.start()], fragments)
        fragments.append(TextFragment(code_match.group(0)))
        cursor = code_match.end()
    _parse_text_region(text[cursor:], fragments)
    return _merge_text(fragments)


def _parse_text_region(text: str, fragments: list[Fragment]) -> None:
    cursor = 0
    for match in _FACE_RE.finditer(text):
        if match.start() > cursor:
            fragments.append(TextFragment(text[cursor : match.start()]))
        fragments.append(FaceFragment(match.group(1).strip(), match.group(0)))
        cursor = match.end()
    if cursor < len(text):
        fragments.append(TextFragment(text[cursor:]))


def _merge_text(fragments: list[Fragment]) -> list[Fragment]:
    merged: list[Fragment] = []
    for fragment in fragments:
        if (
            isinstance(fragment, TextFragment)
            and merged
            and isinstance(merged[-1], TextFragment)
        ):
            merged[-1] = TextFragment(merged[-1].text + fragment.text)
        elif not isinstance(fragment, TextFragment) or fragment.text:
            merged.append(fragment)
    return merged
