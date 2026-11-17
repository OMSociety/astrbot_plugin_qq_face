"""QQ face metadata and name resolution."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any


def normalize_face_name(value: str) -> str:
    """Normalize a user-facing face name for alias lookup."""
    return "".join(value.strip().lstrip("/").split()).casefold()


_COMMON_FACE_ALIASES = {317: ("菜狗",)}


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True, slots=True)
class FaceInfo:
    """Metadata needed to render one QQ face on each supported platform."""

    id: int
    name: str
    aliases: tuple[str, ...] = ()
    pack: str = ""
    animation_type: int = 0
    resource_url: str = ""

    @property
    def is_animated(self) -> bool:
        """Whether QQ treats this face as an animated sticker."""
        return self.animation_type > 0


@dataclass(slots=True)
class FaceCatalog:
    """An immutable-by-convention face collection with a single alias table."""

    faces: dict[int, FaceInfo]
    aliases: dict[str, int] = field(default_factory=dict)
    source: str = "bundled"
    fetched_at: float = 0.0

    def __init__(
        self,
        faces: Iterable[FaceInfo],
        custom_aliases: Mapping[str, Any] | None = None,
        *,
        source: str = "bundled",
        fetched_at: float = 0.0,
    ) -> None:
        self.faces = {face.id: face for face in faces}
        self.source = source
        self.fetched_at = fetched_at
        self.aliases = {}
        for face in sorted(self.faces.values(), key=lambda item: item.id):
            for name in (
                face.name,
                *face.aliases,
                *_COMMON_FACE_ALIASES.get(face.id, ()),
            ):
                key = normalize_face_name(name)
                if key:
                    self.aliases.setdefault(key, face.id)
        for alias, target in (custom_aliases or {}).items():
            key = normalize_face_name(str(alias))
            target_key = normalize_face_name(str(target))
            face_id = (
                int(target_key)
                if target_key.isdecimal()
                else self.aliases.get(target_key)
            )
            if key and face_id in self.faces:
                self.aliases[key] = face_id

    def __len__(self) -> int:
        return len(self.faces)

    def get(self, face_id: int) -> FaceInfo | None:
        """Return metadata for a numeric face ID."""
        return self.faces.get(face_id)

    def resolve(self, token: str) -> FaceInfo | None:
        """Resolve a canonical name, alias, or numeric ID."""
        key = normalize_face_name(token)
        if not key:
            return None
        if key.isdecimal():
            return self.faces.get(int(key))
        face_id = self.aliases.get(key)
        return self.faces.get(face_id) if face_id is not None else None

    @property
    def animated_count(self) -> int:
        """Count faces that require animated-sticker handling."""
        return sum(face.is_animated for face in self.faces.values())

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
        custom_aliases: Mapping[str, Any] | None = None,
        *,
        source: str = "bundled",
        fetched_at: float = 0.0,
    ) -> FaceCatalog:
        """Build a catalog from a bundled cache or fetch_sys_faces response."""
        data = payload.get("data", payload)
        if not isinstance(data, Mapping):
            return cls((), custom_aliases, source=source, fetched_at=fetched_at)

        faces: dict[int, FaceInfo] = {}
        packs = data.get("packs")
        if isinstance(packs, list):
            for pack in packs:
                if not isinstance(pack, Mapping):
                    continue
                pack_name = str(pack.get("pack_name", "")).strip()
                emojis = pack.get("emojis", [])
                if not isinstance(emojis, list):
                    continue
                for item in emojis:
                    if not isinstance(item, Mapping):
                        continue
                    face = _face_from_onebot(item, pack_name)
                    if face is not None:
                        faces.setdefault(face.id, face)
        else:
            items = data.get("faces", [])
            if isinstance(items, list):
                for item in items:
                    if not isinstance(item, Mapping):
                        continue
                    face = _face_from_cache(item)
                    if face is not None:
                        faces[face.id] = face
        return cls(faces.values(), custom_aliases, source=source, fetched_at=fetched_at)


def _aliases(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _face_from_onebot(item: Mapping[str, Any], pack_name: str) -> FaceInfo | None:
    raw_id = str(item.get("q_sid", "")).strip()
    if not raw_id.isdecimal():
        return None
    face_id = int(raw_id)
    name = str(item.get("q_des", "")).strip() or str(face_id)
    return FaceInfo(
        id=face_id,
        name=name,
        aliases=_aliases(item.get("emoji_name_alias")),
        pack=pack_name,
        animation_type=_as_int(item.get("ani_sticker_type")),
        resource_url=str(item.get("url", "")).strip(),
    )


def _face_from_cache(item: Mapping[str, Any]) -> FaceInfo | None:
    face_id = _as_int(item.get("id"), -1)
    if face_id < 0:
        return None
    name = str(item.get("name", "")).strip() or str(face_id)
    return FaceInfo(
        id=face_id,
        name=name,
        aliases=_aliases(item.get("aliases")),
        pack=str(item.get("pack", "")).strip(),
        animation_type=_as_int(item.get("animation_type")),
        resource_url=str(item.get("resource_url", "")).strip(),
    )
