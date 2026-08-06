"""ETL parser for crypto daily history (BTC/ETH/SOL), Binance + Coinbase.

Source (recent era): GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d
Returns OHLCV candles; we take `close_time` (UTC midnight of the day after)
mapped back to the trading day and `close` price as the value.

Глубина истории (source-depth invariant):
  - Binance BTCUSDT/ETHUSDT торгуются с 2017-08-17, SOLUSDT — с 2020-08-11.
  - Более раннюю историю даёт Coinbase Exchange (тоже первоисточник-биржа):
    BTC-USD с 2015-07-20, ETH-USD с 2016-05-18. Подключается через
    `model_config_json.pre_binance = {"provider": "coinbase", "symbol": "BTC-USD"}`
    и заполняет окно [`backfill_from`, первая дата Binance). Сплайс
    BTC-USD (Coinbase) → BTCUSDT (Binance) на 2017-08-17: базис USDT/USD
    в спокойные периоды ~0.1–0.5%, для карточки-обзора рынка приемлемо;
    каноническая свежая история — всегда Binance.
  - `backfill_from` (ISO) — желаемый пол истории. Парсер самовосстанавливается:
    если самая ранняя точка в БД позже `backfill_from`, дозапрашивает окно
    [`backfill_from`, earliest) — поэтому расширение истории не требует
    одноразовых скриптов, достаточно смены конфига и прогона ETL.

Coinbase candles: GET https://api.exchange.coinbase.com/products/{sym}/candles
  ?start=…&end=…&granularity=86400 → rows [time, low, high, open, close, vol],
  time = UTC-полуночь НАЧАЛА дня (та же конвенция даты, что у Binance close),
  максимум 300 свечей на запрос, newest-first. Публичный endpoint без ключа.

Live-котировка в тикере (sticky bar над navbar) — отдельный путь через
`ticker_sources/binance.py` + Redis. Этот парсер — для исторической
страницы /indicator/btc-usd: ежедневный snapshot, который ETL добавляет в
БД точно так же, как любой другой daily-индикатор.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from typing import ClassVar

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FetchLog, Indicator, IndicatorData
from app.services.base_parser import BaseParser

logger = logging.getLogger(__name__)

# api.binance.com отдаёт 451 (Unavailable For Legal Reasons) с российских IP.
# data-api.binance.vision — публичный market-data домен Binance с тем же
# payload и эндпоинтом /api/v3/klines, без гео-ограничений; держим его первым
# (тот же приём, что в ticker_sources/binance.py). Дальше — зеркала на случай
# точечной недоступности конкретного хоста.
_HOSTS = [
    "https://data-api.binance.vision",
    "https://api-gcp.binance.com",
    "https://api.binance.com",
]
_PATH = "/api/v3/klines"
_URL = f"{_HOSTS[0]}{_PATH}"  # канонический источник для FetchLog
_DEFAULT_BACKFILL_DAYS = 1500  # ~4 years, если backfill_from не задан
_LIMIT = 1000

_COINBASE_BASE = "https://api.exchange.coinbase.com"
_COINBASE_CHUNK_DAYS = 290  # лимит Coinbase — 300 свечей на запрос, с запасом


def _fetch_klines(start_ms: int | None, limit: int, symbol: str = "BTCUSDT") -> list[list]:
    params = {"symbol": symbol, "interval": "1d", "limit": limit}
    if start_ms is not None:
        params["startTime"] = start_ms
    last_err: Exception | None = None
    with httpx.Client(timeout=30.0, headers={"User-Agent": "ForecastEconomy/1.0"}) as c:
        for host in _HOSTS:
            try:
                r = c.get(f"{host}{_PATH}", params=params)
                r.raise_for_status()
                return r.json()
            except (httpx.HTTPError, ValueError) as e:
                last_err = e
                continue
    raise last_err or RuntimeError("Binance klines: все зеркала недоступны")


def _klines_to_points(klines: list[list]) -> list[tuple[date, float]]:
    """Map [open_time, open, high, low, close, volume, close_time, ...] → (date, close).

    `close_time` is the last millisecond of the trading day in UTC
    (e.g. 23:59:59.999 of day D). We use the UTC date of close_time as
    the canonical date — same convention BTC indicator pages will show.
    """
    out: list[tuple[date, float]] = []
    for row in klines:
        try:
            close_time_ms = int(row[6])
            close_price = float(row[4])
        except (IndexError, ValueError, TypeError):
            continue
        d = datetime.fromtimestamp(close_time_ms / 1000, tz=timezone.utc).date()
        out.append((d, close_price))
    return out


def _fetch_binance_window(symbol: str, start: date, end: date) -> list[tuple[date, float]]:
    """Дневные свечи Binance за [start, end); пагинация вперёд по 1000.

    Для start раньше листинга символа Binance молча отдаёт данные с даты
    листинга — поэтому pre-Binance окно безопасно запрашивать целиком.
    """
    out: list[tuple[date, float]] = []
    cursor_ms: int | None = int(
        datetime(start.year, start.month, start.day, tzinfo=timezone.utc).timestamp() * 1000
    )
    end_ms = int(
        datetime(end.year, end.month, end.day, tzinfo=timezone.utc).timestamp() * 1000
    )
    for _ in range(20):
        if cursor_ms is not None and cursor_ms >= end_ms:
            break
        kl = _fetch_klines(cursor_ms, _LIMIT, symbol)
        if not kl:
            break
        pts = [(d, v) for d, v in _klines_to_points(kl) if d < end]
        out.extend(pts)
        last_open_ms = int(kl[-1][0])
        if len(kl) < _LIMIT or last_open_ms + 86_400_000 >= end_ms:
            break
        cursor_ms = last_open_ms + 86_400_000  # next day
    return out


def _fetch_coinbase_window(symbol: str, start: date, end: date) -> list[tuple[date, float]]:
    """Дневные свечи Coinbase Exchange за [start, end), чанки по 290 дней."""
    out: list[tuple[date, float]] = []
    cursor = start
    with httpx.Client(timeout=30.0, headers={"User-Agent": "ForecastEconomy/1.0"}) as c:
        while cursor < end:
            chunk_end = min(cursor + timedelta(days=_COINBASE_CHUNK_DAYS), end)
            r = c.get(
                f"{_COINBASE_BASE}/products/{symbol}/candles",
                params={
                    "start": f"{cursor.isoformat()}T00:00:00Z",
                    "end": f"{chunk_end.isoformat()}T00:00:00Z",
                    "granularity": 86400,
                },
            )
            r.raise_for_status()
            rows = r.json()
            if not isinstance(rows, list):
                # Coinbase отвечает {"message": ...} при ошибке rate-limit и т.п.
                raise RuntimeError(f"Coinbase candles: unexpected payload {str(rows)[:200]}")
            for row in rows:
                try:
                    d = datetime.fromtimestamp(int(row[0]), tz=timezone.utc).date()
                    out.append((d, float(row[4])))
                except (IndexError, ValueError, TypeError):
                    continue
            cursor = chunk_end
    return out


class BinanceBtcUsdtParser(BaseParser):
    parser_type: ClassVar[str] = "binance_btcusdt_daily"

    async def _fetch_and_parse(
        self,
        db: AsyncSession,
        indicator: Indicator,
        cfg: dict,
        fetch_log: FetchLog,
    ) -> tuple[list, str]:
        symbol = str(cfg.get("binance_symbol") or "BTCUSDT").upper()
        earliest = (await db.execute(
            select(func.min(IndicatorData.date)).where(IndicatorData.indicator_id == indicator.id)
        )).scalar()
        today = date.today()

        backfill_from: date | None = None
        raw_from = cfg.get("backfill_from")
        if raw_from:
            try:
                backfill_from = date.fromisoformat(str(raw_from))
            except ValueError:
                logger.warning("%s: bad backfill_from %r — игнорирую", indicator.code, raw_from)

        # Окна дозагрузки: свежий хвост всегда; глубокая история — при первом
        # прогоне или когда самая ранняя точка БД позже желаемого пола
        # (self-healing: расширение истории = смена backfill_from + ETL).
        # Флаг deep: pre-Binance сегмент (Coinbase) добирается только для
        # глубокого окна — в свежем окне «первая дата Binance» это просто
        # начало 14-дневного хвоста, а не граница эпохи листинга.
        windows: list[tuple[date, date, bool]] = []
        if earliest is None:
            windows.append((backfill_from or today - timedelta(days=_DEFAULT_BACKFILL_DAYS), today, True))
        else:
            windows.append((today - timedelta(days=14), today + timedelta(days=1), False))
            if backfill_from is not None and earliest > backfill_from:
                windows.append((backfill_from, earliest, True))

        by_date: dict[date, float] = {}
        for w_start, w_end, deep in windows:
            binance_pts = await asyncio.to_thread(_fetch_binance_window, symbol, w_start, w_end)
            first_binance = min((d for d, _ in binance_pts), default=w_end)

            pre = cfg.get("pre_binance") or {}
            pre_symbol = str(pre.get("symbol") or "")
            if deep and pre.get("provider") == "coinbase" and pre_symbol and w_start < first_binance:
                pre_end = min(w_end, first_binance)
                pre_pts = await asyncio.to_thread(
                    _fetch_coinbase_window, pre_symbol, w_start, pre_end
                )
                # Binance — канон: при пересечении дат побеждает он.
                for d, v in pre_pts:
                    by_date.setdefault(d, v)
                logger.info(
                    "%s: Coinbase %s pre-Binance history %s → %s: %d точек",
                    indicator.code, pre_symbol, w_start, pre_end, len(pre_pts),
                )

            for d, v in binance_pts:
                by_date[d] = v

        return sorted(by_date.items()), _URL
