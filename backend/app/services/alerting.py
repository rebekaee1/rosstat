"""Telegram alerting for ETL failures and critical events."""

import logging
from typing import Optional

import requests

from app.config import settings

logger = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def send_telegram(message: str) -> bool:
    """Send alert to Telegram. Returns True on success, False otherwise."""
    token = settings.telegram_bot_token
    chat_id = settings.telegram_chat_id
    if not token or not chat_id:
        return False

    try:
        url = _TELEGRAM_API.format(token=token)
        resp = requests.post(
            url,
            json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            timeout=10,
        )
        if resp.status_code != 200:
            logger.warning("Telegram alert failed: HTTP %d", resp.status_code)
            return False
        return True
    except Exception:
        logger.warning("Telegram alert failed", exc_info=True)
        return False


def alert_etl_failure(indicator_code: str, error: str) -> None:
    msg = (
        f"🔴 <b>ETL Failed</b>\n"
        f"Indicator: <code>{indicator_code}</code>\n"
        f"Error: {error[:200]}"
    )
    send_telegram(msg)


def alert_etl_summary(
    total: int,
    updated: int,
    failed: list[str],
    duration_sec: Optional[float] = None,
) -> None:
    status = "🔴" if failed else "🟢"
    parts = [
        f"{status} <b>Daily ETL Complete</b>",
        f"Total: {total} | Updated: {updated} | Failed: {len(failed)}",
    ]
    if duration_sec is not None:
        parts.append(f"Duration: {duration_sec:.0f}s")
    if failed:
        parts.append(f"Failed: {', '.join(failed)}")
    send_telegram("\n".join(parts))
