from __future__ import annotations

from typing import Any

from app.config import settings
from app.services.action_policy import require_allowed_action
from app.services.yandex_client import YandexOAuthClient, YandexResponse


class YandexWebmasterClient:
    base_url = "https://api.webmaster.yandex.net"

    def __init__(self, token: str | None = None):
        self.client = YandexOAuthClient(token or settings.yandex_webmaster_token, self.base_url)

    async def user(self) -> YandexResponse:
        return await self.client.request("GET", "/v4/user/")

    async def hosts(self, user_id: str) -> YandexResponse:
        return await self.client.request("GET", f"/v4/user/{user_id}/hosts/")

    async def host(self, user_id: str, host_id: str) -> YandexResponse:
        return await self.client.request("GET", f"/v4/user/{user_id}/hosts/{host_id}/")

    async def summary(self, user_id: str, host_id: str) -> YandexResponse:
        return await self.client.request("GET", f"/v4/user/{user_id}/hosts/{host_id}/summary/")

    async def diagnostics(self, user_id: str, host_id: str) -> YandexResponse:
        return await self.client.request("GET", f"/v4/user/{user_id}/hosts/{host_id}/diagnostics/")

    async def sitemaps(self, user_id: str, host_id: str) -> YandexResponse:
        return await self.client.request("GET", f"/v4/user/{user_id}/hosts/{host_id}/sitemaps/")

    async def search_queries_popular(self, user_id: str, host_id: str, **params: Any) -> YandexResponse:
        return await self.client.request("GET", f"/v4/user/{user_id}/hosts/{host_id}/search-queries/popular/", params=params)

    async def recrawl_queue(self, user_id: str, host_id: str) -> YandexResponse:
        return await self.client.request("GET", f"/v4/user/{user_id}/hosts/{host_id}/recrawl/queue/")

    async def recrawl_quota(self, user_id: str, host_id: str) -> YandexResponse:
        return await self.client.request("GET", f"/v4/user/{user_id}/hosts/{host_id}/recrawl/quota/")

    async def submit_recrawl(self, user_id: str, host_id: str, url: str, *, approved: bool = False) -> YandexResponse:
        require_allowed_action("webmaster.recrawl.submit", {"host": host_id, "url": url}, approved)
        return await self.client.request(
            "POST",
            f"/v4/user/{user_id}/hosts/{host_id}/recrawl/queue/",
            json_body={"url": url},
        )

    async def indexing_history(self, user_id: str, host_id: str, **params: Any) -> YandexResponse:
        return await self.client.request("GET", f"/v4/user/{user_id}/hosts/{host_id}/indexing/history/", params=params)

    async def links_internal_broken_samples(self, user_id: str, host_id: str) -> YandexResponse:
        return await self.client.request("GET", f"/v4/user/{user_id}/hosts/{host_id}/links/internal/broken/samples/")
