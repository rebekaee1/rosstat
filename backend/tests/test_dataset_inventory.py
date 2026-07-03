"""Инвентаризация DS-датасета: подсчёт строк/параметров и Telegram-вёрстка."""
import asyncio
from datetime import date, datetime

import pytest

from app.models import (
    BehaviorEvent,
    FrontendEvent,
    Hypothesis,
    MetrikaSearchPhrase,
    RawMetrikaVisit,
)
from app.services.dataset_inventory import build_inventory, format_inventory_html


@pytest.fixture
def inventory(auth_env):
    """Инвентаризация поверх наполненной SQLite-схемы auth_env."""
    async def _run():
        async with auth_env["session_maker"]() as db:
            db.add_all([
                BehaviorEvent(event_type="pageview", page="/indicator/cpi",
                              params_json={"vw": 1440, "vh": 900}),
                BehaviorEvent(event_type="click", page="/indicator/cpi",
                              element_path="main > button", element_text="Прогноз",
                              x=10, y=20, params_json=None),
                BehaviorEvent(event_type="dwell", page="/indicator/cpi",
                              params_json={"ms": 30000, "scroll_pct": 70}),
                FrontendEvent(event_name="indicator_view", url="/indicator/cpi",
                              params_json={"indicator": "cpi"}),
                FrontendEvent(event_name="search_query", url="/",
                              params_json={"q": "инфляция", "results": 5}),
                RawMetrikaVisit(counter_id="107136069", visit_id="v1",
                                visit_date=date(2026, 7, 2), traffic_source="ad",
                                raw_json={"ym:s:visitID": "v1", "ym:s:UTMSource": "direct"},
                                row_hash="h1"),
                MetrikaSearchPhrase(counter_id="107136069", date=date(2026, 7, 2),
                                    phrase="инфляция в россии", visits=12, users=10),
                Hypothesis(statement="Реклама конвертируется хуже органики",
                           verdict=None, created_at=datetime(2026, 7, 2),
                           updated_at=datetime(2026, 7, 2)),
                Hypothesis(statement="Ночью трафика нет", verdict=True,
                           confidence=0.9, created_at=datetime(2026, 7, 1),
                           updated_at=datetime(2026, 7, 2)),
            ])
            await db.commit()
            return await build_inventory(db)
    return asyncio.run(_run())


def test_inventory_counts_all_layers(inventory):
    s = inventory["sections"]
    assert s["behavior_events"]["rows"] == 3
    assert s["behavior_events"]["by_type"] == {"pageview": 1, "click": 1, "dwell": 1}
    assert "vw" in s["behavior_events"]["json_keys"]
    assert s["frontend_events"]["rows"] == 2
    assert s["frontend_events"]["event_names"] == 2
    assert s["raw_metrika_visits"]["rows"] == 1
    assert "ym:s:UTMSource" in s["raw_metrika_visits"]["json_keys"]
    assert s["metrika_search_phrases"]["distinct_phrases"] == 1
    assert s["hypotheses"]["by_verdict"] == {"open": 1, "true": 1, "false": 0}


def test_inventory_totals_are_positive(inventory):
    assert inventory["totals"]["rows"] >= 7
    # Параметры = колонки таблиц + JSON-ключи + типы событий: заведомо десятки.
    assert inventory["totals"]["parameters"] > 50


def test_inventory_html_is_telegram_ready(inventory):
    html = format_inventory_html(inventory)
    assert html.startswith("📦 <b>Датасет:")
    assert "Гипотезы: открытых 1, подтверждено 1, опровергнуто 0" in html
    assert "копим без удаления" in html
