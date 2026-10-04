"""Алерты Вебмастера: относительные сравнения только по полным дням (2026-10-04).

Яндекс публикует данные за последние 1–2 суток неполными (пустые in_search/crawled),
поэтому «обход 1943 против 6131» и подобные сравнения с неполным днём были ложными.
"""
import asyncio
from datetime import date, timedelta
from unittest.mock import AsyncMock

from app.services.webmaster_indexing_daily import crawl_drop_avg, in_search_drop


def _rows(start, values):
    return [(start + timedelta(days=i), None, v) for i, v in enumerate(values)]


def test_crawl_drop_needs_three_complete_days_in_a_row():
    start = date(2026, 9, 18)
    base = [6000, 6200, 6100, 6300, 5900, 6131, 6000]          # 18..24
    last = date(2026, 9, 27)
    # Три полных дня подряд < 50% среднего — алерт.
    avg, recent = crawl_drop_avg(_rows(start, base + [2500, 2000, 1943]), last)
    assert round(avg) == 6090 and recent == [1943, 2000, 2500]
    # Один низкий день (1943) при нормальных соседях — не алерт.
    assert crawl_drop_avg(_rows(start, base + [6000, 6100, 1943]), last) is None
    # Низкие два дня из трёх — не алерт.
    assert crawl_drop_avg(_rows(start, base + [6000, 2000, 1943]), last) is None
    # Пустой (неполный) последний день — «нет данных», а не ноль.
    assert crawl_drop_avg(_rows(start, base + [2500, 2000, None]), last) is None
    # Нет строки за якорный день.
    assert crawl_drop_avg(_rows(start, base + [2500, 2000]), last) is None
    # Малая база (< 50 в среднем) или < 3 дней базы.
    assert crawl_drop_avg(_rows(start, [40] * 7 + [1, 1, 1]), last) is None
    assert crawl_drop_avg(_rows(date(2026, 9, 23), [6000, 6000, 2500, 2000, 1943]), last) is None


def test_in_search_drop_uses_last_complete_day_only():
    def rows(*pairs):
        return [(date(2026, 9, d), v, None) for d, v in pairs]

    assert in_search_drop(rows((25, 1000), (26, 900)), date(2026, 9, 26)) == (
        date(2026, 9, 26), 900, date(2026, 9, 25), 1000)
    assert in_search_drop(rows((25, 1000), (26, 960)), date(2026, 9, 26)) is None   # -4%
    assert in_search_drop(rows((25, 1000), (26, None)), date(2026, 9, 26)) is None  # пусто
    # Свежее наблюдение — не последний полный день: то же окно не оцениваем снова.
    assert in_search_drop(rows((24, 1000), (25, 900)), date(2026, 9, 26)) is None


def test_alert_host_compares_only_complete_days(tmp_path, monkeypatch):
    """Неполные вчера/позавчера (NULL и заниженные) не дают алертов обхода и in_search."""
    from sqlalchemy import create_engine
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    import app.services.analytics_alerts as alerts
    import app.services.webmaster_indexing_daily as daily
    from app.models import WebmasterIndexingDaily

    db_path = tmp_path / "wm.db"
    sync_engine = create_engine(f"sqlite:///{db_path}")
    WebmasterIndexingDaily.__table__.create(sync_engine)
    today = date(2026, 10, 4)

    def seed(crawled, in_search=None, sitemap=None):
        # crawled[0] — вчера (today-1), далее вглубь истории.
        with sync_engine.begin() as conn:
            conn.execute(WebmasterIndexingDaily.__table__.delete())
            conn.execute(WebmasterIndexingDaily.__table__.insert(), [
                {"host": "h", "day": today - timedelta(days=i + 1), "crawled_2xx": c,
                 "in_search": (in_search or {}).get(i), "sitemap_errors": (sitemap or {}).get(i)}
                for i, c in enumerate(crawled)
            ])

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    notify = AsyncMock(return_value=True)
    monkeypatch.setattr(daily, "analytics_session", async_sessionmaker(engine, expire_on_commit=False))
    monkeypatch.setattr(daily, "today_msk", lambda: today)
    monkeypatch.setattr(alerts, "_alert", notify)

    def run():
        notify.reset_mock()
        asyncio.run(daily._alert_host(today - timedelta(days=1), "h"))
        return [call.args[0] for call in notify.await_args_list]

    # Вчера 1943 при среднем ~6100 и пустое позавчера: данные неполные — тишина.
    seed([1943, None, 6000, 6100, 6200, 6000, 6100, 6300, 5900, 6000, 6100, 6000])
    assert not any(k.startswith("webmaster_crawl_drop") for k in run())
    # Три полных дня (3, 4, 5 суток назад) подряд < 50% — алерт; вчера/позавчера не важны.
    seed([6000, 6000, 2500, 2000, 1943, 6000, 6100, 6200, 6000, 6100, 6300, 5900])
    assert "webmaster_crawl_drop:h" in run()
    # In-search: падение неполного дня игнорируется, полного (3 суток назад) — алерт.
    seed([6000] * 12, in_search={0: 100, 1: 5000, 2: 5000, 3: 5000})
    assert not any(k.startswith("webmaster_in_search_drop") for k in run())
    seed([6000] * 12, in_search={2: 4000, 3: 5000})
    assert "webmaster_in_search_drop:h" in run()
    # Рост ошибок sitemap по-прежнему алертит; снижение — нет.
    seed([6000] * 12, sitemap={0: 86945, 1: 77637})
    assert "webmaster_sitemap_errors:h" in run()
    seed([6000] * 12, sitemap={0: 70000, 1: 77637})
    assert "webmaster_sitemap_errors:h" not in run()
    asyncio.run(engine.dispose())
    sync_engine.dispose()


def test_webmaster_noisy_alerts_cool_down_for_a_day():
    from app.services.analytics_alerts import _alert_cooldown

    for kind in ("webmaster_sitemap_errors", "webmaster_crawl_drop", "webmaster_in_search_drop"):
        assert _alert_cooldown(f"{kind}:forecasteconomy.com") == 24 * 3600
