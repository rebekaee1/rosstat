"""The public embed trackers must keep their Redis hash evictable and bounded."""

import asyncio

import fakeredis.aioredis

from app.api import embed


def test_both_embed_trackers_set_ttl_and_bound_hash_fields(monkeypatch):
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    async def get_redis():
        return redis

    class Request:
        headers = {"referer": "https://" + "a" * 300 + ".example/path"}

        async def json(self):
            return {"code": "c" * 100, "type": "t" * 100, "referrer": self.headers["referer"]}

    monkeypatch.setattr(embed, "get_redis", get_redis)

    async def check():
        for send in (
            lambda: embed.track_impression(Request()),
            lambda: embed.tracking_pixel(code="c" * 100, t="t" * 100, request=Request()),
        ):
            await redis.flushdb()
            await send()
            keys = await redis.keys("fe:embed:imp:*")
            assert len(keys) == 1
            assert 0 < await redis.ttl(keys[0]) <= embed._IMPRESSION_TTL
            fields = await redis.hkeys(keys[0])
            assert len(fields) == 1
            code, kind, domain = fields[0].split(":", 2)
            assert len(code) == 64
            assert len(kind) == 32
            assert len(domain) == 255

    asyncio.run(check())
