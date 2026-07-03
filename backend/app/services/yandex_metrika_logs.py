from __future__ import annotations

from datetime import date
from typing import Any, Literal

import httpx

from app.config import settings
from app.services.yandex_client import YandexApiError, YandexOAuthClient, YandexResponse, stable_hash


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
        """Скачивание части выгрузки. Отдаётся сырой TSV (content-type может
        приходить как application/json — не доверяем ему), поэтому мимо
        json-парсинга `YandexOAuthClient.request`: читаем text напрямую."""
        path = f"/management/v1/counter/{counter_id}/logrequest/{request_id}/part/{part_number}/download"
        url = f"{self.client.base_url}{path}"
        async with httpx.AsyncClient(timeout=self.client.timeout) as http:
            response = await http.get(
                url,
                headers={"Authorization": f"OAuth {self.client.token}",
                         "Accept": "text/tab-separated-values"},
            )
        if response.status_code >= 400:
            raise YandexApiError(
                f"Yandex Logs API returned HTTP {response.status_code} for download part {part_number}",
                status_code=response.status_code,
                payload=response.text[:500],
            )
        return YandexResponse(
            data=response.text,
            status_code=response.status_code,
            request_hash=stable_hash({"url": url}),
        )

    async def clean_request(self, counter_id: str, request_id: str) -> YandexResponse:
        return await self.client.request("POST", f"/management/v1/counter/{counter_id}/logrequest/{request_id}/clean")
