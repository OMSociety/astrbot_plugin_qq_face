import asyncio
import json
from pathlib import Path

from astrbot_plugin_qq_face.catalog import CatalogStore

BUNDLED = {
    "faces": [
        {"id": 13, "name": "/呲牙", "animation_type": 0},
    ]
}
DYNAMIC = {
    "packs": [
        {
            "pack_name": "动态",
            "emojis": [
                {
                    "q_sid": "317",
                    "q_des": "/菜汪",
                    "ani_sticker_type": 1,
                }
            ],
        }
    ]
}


class FakeBot:
    def __init__(self, response: object) -> None:
        self.response = response

    async def call_action(self, action: str, **kwargs):
        assert action == "fetch_sys_faces"
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def make_store(tmp_path: Path) -> CatalogStore:
    bundled = tmp_path / "bundled.json"
    bundled.write_text(json.dumps(BUNDLED), encoding="utf-8")
    return CatalogStore(tmp_path / "data", bundled, ttl_hours=24)


def test_catalog_refresh_cache_and_instance_isolation(tmp_path) -> None:
    async def scenario() -> None:
        store = make_store(tmp_path)
        assert (await store.get("one")).resolve("呲牙").id == 13

        refreshed = await store.refresh("one", FakeBot(DYNAMIC), force=True)
        assert refreshed.resolve("菜汪").animation_type == 1
        assert (await store.get("two")).resolve("菜汪") is None

        failed = await store.refresh(
            "one", FakeBot(RuntimeError("offline")), force=True
        )
        assert failed.resolve("菜汪").id == 317

        second_store = make_store(tmp_path)
        cached = await second_store.get("one")
        assert cached.source == "cache"
        assert cached.resolve("菜汪").id == 317
        assert "one" not in second_store._cache_path("one").name

    asyncio.run(scenario())


def test_failed_refresh_backs_off_until_forced(tmp_path) -> None:
    class CountingBot:
        def __init__(self) -> None:
            self.calls = 0

        async def call_action(self, action: str, **kwargs):
            self.calls += 1
            raise RuntimeError("unsupported")

    async def scenario() -> None:
        store = make_store(tmp_path)
        store.retry_seconds = 3600
        bot = CountingBot()

        await store.refresh("one", bot)
        await store.refresh("one", bot)
        assert bot.calls == 1

        await store.refresh("one", bot, force=True)
        assert bot.calls == 2

    asyncio.run(scenario())


def test_invalid_cache_timestamp_falls_back_to_zero(tmp_path) -> None:
    async def scenario() -> None:
        store = make_store(tmp_path)
        path = store._cache_path("one")
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps({"fetched_at": "not-a-number", "data": DYNAMIC}),
            encoding="utf-8",
        )

        cached = await store.get("one")
        assert cached.source == "cache"
        assert cached.fetched_at == 0.0
        assert cached.resolve("菜汪").id == 317

    asyncio.run(scenario())
