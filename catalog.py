"""Per-platform QQ face catalogs with atomic disk caching."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import tempfile
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import FaceCatalog

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CatalogState:
    """Mutable runtime state for one platform instance."""

    catalog: FaceCatalog
    loaded: bool = False
    retry_after: float = 0.0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class CatalogStore:
    """Load bundled faces and refresh each OneBot instance independently."""

    def __init__(
        self,
        data_dir: Path,
        bundled_path: Path,
        custom_aliases: Mapping[str, Any] | None = None,
        ttl_hours: int = 24,
        retry_seconds: int = 3600,
    ) -> None:
        self.data_dir = data_dir
        self.bundled_path = bundled_path
        self.custom_aliases = custom_aliases or {}
        self.ttl_seconds = max(1, ttl_hours) * 3600
        self.retry_seconds = max(1, retry_seconds)
        bundled_payload = json.loads(bundled_path.read_text(encoding="utf-8"))
        self.bundled = FaceCatalog.from_payload(
            bundled_payload,
            self.custom_aliases,
            source="bundled",
        )
        self._states: dict[str, CatalogState] = {}

    def _state(self, platform_id: str) -> CatalogState:
        if platform_id not in self._states:
            self._states[platform_id] = CatalogState(self.bundled)
        return self._states[platform_id]

    def _cache_path(self, platform_id: str) -> Path:
        digest = hashlib.sha256(platform_id.encode("utf-8")).hexdigest()
        return self.data_dir / "catalogs" / f"{digest}.json"

    @staticmethod
    def _cache_timestamp(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    async def get(self, platform_id: str) -> FaceCatalog:
        """Return the current catalog, loading a stale cache when available."""
        state = self._state(platform_id)
        if state.loaded:
            return state.catalog
        async with state.lock:
            if state.loaded:
                return state.catalog
            payload = await asyncio.to_thread(self._read_cache, platform_id)
            if payload:
                cached = FaceCatalog.from_payload(
                    payload,
                    self.custom_aliases,
                    source="cache",
                    fetched_at=self._cache_timestamp(payload.get("fetched_at", 0.0)),
                )
                if len(cached):
                    state.catalog = cached
            state.loaded = True
        return state.catalog

    async def refresh(
        self,
        platform_id: str,
        bot: Any,
        *,
        force: bool = False,
    ) -> FaceCatalog:
        """Refresh a dynamic catalog, retaining the last good copy on failure."""
        current = await self.get(platform_id)
        state = self._state(platform_id)
        now = time.time()
        if not force and (
            now - current.fetched_at < self.ttl_seconds or now < state.retry_after
        ):
            return current
        async with state.lock:
            current = state.catalog
            now = time.time()
            if not force and (
                now - current.fetched_at < self.ttl_seconds or now < state.retry_after
            ):
                return current
            try:
                response = await asyncio.wait_for(
                    bot.call_action("fetch_sys_faces", refresh=force),
                    timeout=8,
                )
                refreshed = FaceCatalog.from_payload(
                    response,
                    self.custom_aliases,
                    source="dynamic",
                    fetched_at=time.time(),
                )
                if not len(refreshed):
                    raise ValueError("fetch_sys_faces returned no numeric QQ faces")
                await asyncio.to_thread(
                    self._write_cache,
                    platform_id,
                    refreshed.fetched_at,
                    response,
                )
                state.catalog = refreshed
                state.retry_after = 0.0
                return refreshed
            except Exception as exc:
                state.retry_after = time.time() + self.retry_seconds
                logger.warning(
                    "QQ face catalog refresh failed for %s: %s", platform_id, exc
                )
                return current

    async def adopt(self, platform_id: str, payload: Mapping[str, Any]) -> FaceCatalog:
        """Adopt a catalog already fetched during platform capability probing."""
        catalog = FaceCatalog.from_payload(
            payload,
            self.custom_aliases,
            source="dynamic",
            fetched_at=time.time(),
        )
        if not len(catalog):
            return await self.get(platform_id)
        state = self._state(platform_id)
        async with state.lock:
            await asyncio.to_thread(
                self._write_cache, platform_id, catalog.fetched_at, payload
            )
            state.catalog = catalog
            state.loaded = True
        return catalog

    def _read_cache(self, platform_id: str) -> dict[str, Any] | None:
        path = self._cache_path(platform_id)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else None
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Ignoring invalid QQ face cache %s: %s", path, exc)
            return None

    def _write_cache(
        self,
        platform_id: str,
        fetched_at: float,
        payload: Mapping[str, Any],
    ) -> None:
        path = self._cache_path(platform_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        document = {"fetched_at": fetched_at, "data": payload.get("data", payload)}
        temporary_name = ""
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f"{path.stem}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary_name = handle.name
                json.dump(document, handle, ensure_ascii=False, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, path)
        finally:
            if temporary_name and os.path.exists(temporary_name):
                os.unlink(temporary_name)
