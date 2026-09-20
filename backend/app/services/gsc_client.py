"""Read-only Search Console API, renewable OAuth and daily web-search ingestion.

Search Analytics is a top-row export, not an inventory of all indexed URLs.
The persistent table contains only web/query/page/date; image/country/device
reports are exported separately so different aggregations cannot overwrite it.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote, urlsplit
from zoneinfo import ZoneInfo

import httpx

from app.config import settings

logger = logging.getLogger(__name__)
GSC_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
GSC_API = "https://www.googleapis.com/webmasters/v3"
GSC_TOKEN_URL = "https://oauth2.googleapis.com/token"
GSC_INSPECTION_URL = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"
GSC_SEARCH_ANALYTICS = GSC_API + "/sites/{site}/searchAnalytics/query"
DEFAULT_CREDENTIALS_FILE = Path.home() / ".config/forecasteconomy/gsc-oauth.json"


class GscError(RuntimeError):
    """Sanitized API failure; never include token responses or request bodies."""


def read_credentials(path: str | Path) -> dict:
    credential_path = Path(path).expanduser()
    if credential_path.stat().st_mode & 0o077:
        raise GscError("GSC credentials file must have mode 0600")
    payload = json.loads(credential_path.read_text())
    if payload.get("type") != "authorized_user" or not all(
        isinstance(payload.get(key), str) and payload[key]
        for key in ("client_id", "client_secret", "refresh_token")
    ):
        raise GscError("GSC requires authorized_user OAuth credentials")
    scopes = payload.get("scopes", [])
    if scopes != [GSC_SCOPE]:
        raise GscError("GSC credentials must be scoped to webmasters.readonly only")
    return payload


def configured_site() -> str:
    return settings.gsc_site_url or f"sc-domain:{settings.public_host}"


class GscClient:
    def __init__(self, client: httpx.AsyncClient, *, token: str = "", credentials: dict | None = None):
        self.client = client
        self.credentials = credentials
        self.token = token
        self.expires_at = float("inf") if token else 0.0

    @classmethod
    def from_settings(cls, client: httpx.AsyncClient) -> GscClient:
        if settings.gsc_credentials_file:
            return cls(client, credentials=read_credentials(settings.gsc_credentials_file))
        if settings.gsc_access_token:
            return cls(client, token=settings.gsc_access_token)
        raise GscError("GSC OAuth credentials are not configured")

    async def _access_token(self) -> str:
        if self.token and time.monotonic() < self.expires_at:
            return self.token
        if not self.credentials:
            raise GscError("GSC access token expired; configure renewable OAuth credentials")
        response = await self.client.post(GSC_TOKEN_URL, data={
            "grant_type": "refresh_token",
            **{key: self.credentials[key] for key in ("client_id", "client_secret", "refresh_token")},
        })
        if response.status_code != 200:
            raise GscError(f"GSC OAuth refresh failed (HTTP {response.status_code}); reauthorize if revoked/expired")
        payload = response.json()
        token = payload.get("access_token")
        if not isinstance(token, str) or not token:
            raise GscError("GSC OAuth refresh returned no access token")
        if "scope" in payload and payload["scope"].split() != [GSC_SCOPE]:
            raise GscError("GSC OAuth token scope is not webmasters.readonly")
        self.token = token
        self.expires_at = time.monotonic() + max(0, int(payload.get("expires_in", 3600)) - 60)
        return token

    async def _request(self, method: str, url: str, **kwargs) -> dict:
        for attempt in range(2):
            token = await self._access_token()
            response = await self.client.request(method, url, headers={"Authorization": f"Bearer {token}"}, **kwargs)
            if response.status_code == 401 and self.credentials and attempt == 0:
                self.expires_at = 0
                continue
            if response.status_code >= 400:
                # Do not retry quota errors or print Google's request/response payloads.
                raise GscError(f"GSC API failed (HTTP {response.status_code}); quota/permission errors stop this run")
            return response.json()
        raise GscError("GSC authentication failed")

    async def sites(self) -> dict:
        return await self._request("GET", f"{GSC_API}/sites")

    async def sitemaps(self, site: str) -> dict:
        return await self._request("GET", f"{GSC_API}/sites/{quote(site, safe='')}/sitemaps")

    async def search_day(
        self, site: str, day: date, *, dimensions: tuple[str, ...] = ("query", "page", "date"),
        search_type: str = "web", max_rows: int = 50_000,
    ) -> dict:
        if search_type not in {"web", "image", "video", "news", "discover", "googleNews"}:
            raise ValueError("Unsupported Search Console search type")
        if len(set(dimensions)) != len(dimensions) or not set(dimensions) <= {"query", "page", "date", "country", "device", "searchAppearance"}:
            raise ValueError("Unsupported/duplicate Search Console dimensions")
        if not 1 <= max_rows <= 50_000:
            raise ValueError("max_rows must be between 1 and 50000 per day")
        rows: list[dict] = []
        while len(rows) < max_rows:
            limit = min(25_000, max_rows - len(rows))
            data = await self._request("POST", GSC_SEARCH_ANALYTICS.format(site=quote(site, safe="")), json={
                "startDate": day.isoformat(), "endDate": day.isoformat(),
                "dimensions": list(dimensions), "type": search_type, "dataState": "final",
                "rowLimit": limit, "startRow": len(rows),
            })
            page = data.get("rows") or []
            rows.extend(page)
            if len(page) < limit:
                break
        return {"date": day.isoformat(), "rows": rows, "reached_row_cap": len(rows) >= max_rows}

    async def inspect_sample(self, site: str, urls: list[str]) -> list[dict]:
        urls = list(dict.fromkeys(urls))
        if len(urls) > 20:
            raise ValueError("URL Inspection is limited to 20 distinct URLs per run (Google: 2000/day/property)")
        for url in urls:
            parsed = urlsplit(url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.fragment:
                raise ValueError("Inspection requires canonical HTTP(S) URLs")
            if site.startswith("sc-domain:"):
                domain = site.removeprefix("sc-domain:")
                contained = parsed.hostname == domain or parsed.hostname.endswith("." + domain)
            else:
                contained = url.startswith(site if site.endswith("/") else site + "/")
            if not contained:
                raise ValueError("Inspection URL is outside the selected Search Console property")
        reports = []
        for url in urls:
            reports.append({"url": url, "result": await self._request("POST", GSC_INSPECTION_URL, json={
                "inspectionUrl": url, "siteUrl": site, "languageCode": "en-US",
            })})
        return reports


async def gsc_search_queries_job() -> None:
    if not (settings.gsc_access_token or settings.gsc_credentials_file):
        logger.info("GSC sync skipped: OAuth credentials are not configured")
        return
    try:
        n = await sync_gsc_search_queries()
        logger.info("GSC search queries synced: %d rows", n)
    except Exception:
        logger.exception("GSC search queries sync failed")


async def sync_gsc_search_queries(token: str = "", *, days: int = 7) -> int:
    """Refresh finalized daily web results; dates follow GSC's Pacific timezone."""
    from sqlalchemy.dialects.postgresql import insert
    from app.database import analytics_session
    from app.models import GscSearchQuery

    if not 1 <= days <= 31:
        raise ValueError("GSC sync window must be 1..31 days")
    end = datetime.now(ZoneInfo("America/Los_Angeles")).date() - timedelta(days=1)
    start = end - timedelta(days=days - 1)
    stored = 0
    async with httpx.AsyncClient(timeout=60) as http:
        api = GscClient(http, token=token) if token else GscClient.from_settings(http)
        for offset in range(days):
            result = await api.search_day(configured_site(), start + timedelta(days=offset))
            if result["reached_row_cap"]:
                logger.warning("GSC daily row cap reached for %s; export is partial", result["date"])
            async with analytics_session() as db:
                for row in result["rows"]:
                    keys = row.get("keys") or []
                    if len(keys) != 3:
                        continue
                    query, page, day_s = keys
                    try:
                        day = date.fromisoformat(day_s)
                    except (ValueError, TypeError):
                        continue
                    stmt = insert(GscSearchQuery).values(
                        date=day, query=str(query)[:500], page=str(page)[:1000] if page else None,
                        impressions=int(row.get("impressions") or 0), clicks=int(row.get("clicks") or 0),
                        ctr=row.get("ctr"), position=row.get("position"), raw_json=row,
                    )
                    stmt = stmt.on_conflict_do_update(constraint="uq_gsc_search_query", set_={
                        field: getattr(stmt.excluded, field)
                        for field in ("impressions", "clicks", "ctr", "position", "raw_json")
                    })
                    await db.execute(stmt)
                    stored += 1
                await db.commit()
    return stored
