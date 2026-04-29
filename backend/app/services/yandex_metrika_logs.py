from __future__ import annotations

from datetime import date
from typing import Any, Literal

from app.config import settings
from app.services.yandex_client import YandexOAuthClient, YandexResponse


LogSource = Literal["visits", "hits"]


class MetrikaLogsClient:
    base_url = "https://api-metrika.yandex.net"

    def __init__(self, token: str | None = None):
        self.client = YandexOAuthClient(token or settings.yandex_metrika_read_token, self.base_url)

    async def list_requests(self, counter_id: str) -> YandexResponse:
        return await self.client.request("GET", f"/management/v1/counter/{counter_id}/logrequests")

    async def create_request(
        self,
        counter_id: str,
        *,
        source: LogSource,
        fields: list[str],
        date_from: date | str,
        date_to: date | str,
        attribution: str | None = None,
    ) -> YandexResponse:
        params: dict[str, Any] = {
            "source": source,
            "fields": ",".join(fields),
            "date1": str(date_from),
            "date2": str(date_to),
        }
        if attribution:
            params["attribution"] = attribution
        return await self.client.request("POST", f"/management/v1/counter/{counter_id}/logrequests", params=params)

    async def request_info(self, counter_id: str, request_id: str) -> YandexResponse:
        return await self.client.request("GET", f"/management/v1/counter/{counter_id}/logrequest/{request_id}")

    async def download_part(self, counter_id: str, request_id: str, part_number: int) -> YandexResponse:
        return await self.client.request(
            "GET",
            f"/management/v1/counter/{counter_id}/logrequest/{request_id}/part/{part_number}/download",
            headers={"Accept": "text/tab-separated-values"},
        )

    async def clean_request(self, counter_id: str, request_id: str) -> YandexResponse:
        return await self.client.request("POST", f"/management/v1/counter/{counter_id}/logrequest/{request_id}/clean")
