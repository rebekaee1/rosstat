"""
Rosstat data fetcher with dynamic URL resolution and proper SSL.
Verified through spike testing (2026-02-24):
- HEAD returns 404 for missing files, 200 for existing
- GET returns 200+HTML for missing files — must check magic bytes
- Only russiantrustedca2024.pem works (2022 PEM is broken)
- Old files get deleted from server after ~2 months
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import requests

from app.config import settings
from app.services.http_client import create_session

logger = logging.getLogger(__name__)

XLSX_MAGIC = b"PK\x03\x04"


class RosstatFetcher:
    def __init__(self):
        self.session = create_session()
        self.session.verify = settings.rosstat_ca_cert

    def _build_url(self, month: int, year: int) -> str:
        filename = settings.rosstat_cpi_template.format(mm=f"{month:02d}", yyyy=year)
        return f"{settings.rosstat_base_url}/{filename}"

    def resolve_latest_url(self) -> Optional[Tuple[str, str]]:
        """Find the latest available CPI file.
        Uses HEAD requests (returns proper 404) scanning from current month backward.
        Returns (url, filename) or (None, None).
        """
        now = datetime.now(tz=timezone(timedelta(hours=3)))

        for months_back in range(settings.rosstat_max_months_back):
            check_date = now - timedelta(days=30 * months_back)
            url = self._build_url(check_date.month, check_date.year)
            filename = url.rsplit("/", 1)[-1]

            try:
                resp = self.session.head(url, timeout=settings.rosstat_request_timeout, allow_redirects=True)
                if resp.status_code == 200:
                    logger.info("Found file: %s", filename)
                    return url, filename
                logger.debug("Not found: %s (HTTP %d)", filename, resp.status_code)
            except requests.RequestException as e:
                logger.warning("Error checking %s: %s", filename, e)

        logger.error("No CPI files found in last %d months", settings.rosstat_max_months_back)
        return None, None

    def download(self, url: str) -> Optional[bytes]:
        """Download file and verify it's actually XLSX (not HTML error page)."""
        try:
            resp = self.session.get(url, timeout=settings.rosstat_request_timeout)
            resp.raise_for_status()

            ct = resp.headers.get("content-type", "")
            if "html" in ct.lower():
                logger.warning("Got HTML content-type from %s", url)

            if resp.content[:4] != XLSX_MAGIC:
                logger.error("Downloaded content is not XLSX (got HTML?). URL: %s", url)
                return None

            logger.info("Downloaded %d KB from %s", len(resp.content) // 1024, url)
            return resp.content

        except requests.RequestException as e:
            logger.error("Download failed for %s: %s", url, e)
            return None

    def fetch_latest(self) -> Optional[Tuple[bytes, str]]:
        """Resolve latest URL and download the file.
        Returns (content_bytes, url) or (None, None).
        """
        url, filename = self.resolve_latest_url()
        if not url:
            return None, None

        content = self.download(url)
        if not content:
            return None, None

        return content, url
