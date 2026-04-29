from __future__ import annotations

from datetime import date
from typing import Any, Literal

from app.config import settings
from app.services.yandex_client import YandexOAuthClient, YandexResponse


ReportKind = Literal["data", "bytime", "drilldown", "comparison", "comparison/drilldown"]


class MetrikaReportingClient:
    base_url = "https://api-metrika.yandex.net"

    def __init__(self, token: str | None = None):
        self.client = YandexOAuthClient(token or settings.yandex_metrika_read_token, self.base_url)

    async def report(
        self,
        kind: ReportKind,
        *,
        counter_id: str,
        metrics: list[str],
        dimensions: list[str] | None = None,
        date_from: date | str | None = None,
        date_to: date | str | None = None,
        filters: str | None = None,
        segment: str | None = None,
        sort: list[str] | None = None,
        limit: int = 100,
        offset: int = 1,
        attribution: str | None = None,
        accuracy: str | None = None,
        group: str | None = None,
        csv: bool = False,
        extra: dict[str, Any] | None = None,
    ) -> YandexResponse:
        suffix = ".csv" if csv else ""
        path = f"/stat/v1/data/{kind}{suffix}" if kind != "data" else f"/stat/v1/data{suffix}"
        params: dict[str, Any] = {
            "id": counter_id,
            "metrics": ",".join(metrics),
            "limit": limit,
            "offset": offset,
        }
        if dimensions:
            params["dimensions"] = ",".join(dimensions)
        if date_from:
            params["date1"] = str(date_from)
        if date_to:
            params["date2"] = str(date_to)
        if filters:
            params["filters"] = filters
        if segment:
            params["segment"] = segment
        if sort:
            params["sort"] = ",".join(sort)
        if attribution:
            params["attribution"] = attribution
        if accuracy:
            params["accuracy"] = accuracy
        if group:
            params["group"] = group
        if extra:
            params.update(extra)
        return await self.client.request("GET", path, params=params)

    async def table(self, **kwargs: Any) -> YandexResponse:
        return await self.report("data", **kwargs)

    async def bytime(self, **kwargs: Any) -> YandexResponse:
        return await self.report("bytime", **kwargs)

    async def drilldown(self, **kwargs: Any) -> YandexResponse:
        return await self.report("drilldown", **kwargs)

    async def comparison(self, **kwargs: Any) -> YandexResponse:
        return await self.report("comparison", **kwargs)

    async def comparison_drilldown(self, **kwargs: Any) -> YandexResponse:
        return await self.report("comparison/drilldown", **kwargs)
