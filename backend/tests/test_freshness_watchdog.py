"""Сторож свежести: правило как у значка на странице, один группированный алерт, health-ручка."""
import asyncio
import re
from datetime import date, datetime
from pathlib import Path

import pytest

from app.models import (
    FetchLog, Indicator, IndicatorData, RegionIndicator, WorldCountry, WorldDataPoint,
    WorldDatasetState, WorldIndicator,
)
from app.services import freshness as fr

TODAY = date(2026, 10, 12)


def test_limits_match_frontend_freshness_badge():
    """Серверное правило обязано совпадать с LIMITS из dataFreshness.js."""
    js = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "dataFreshness.js").read_text()
    block = js.split("const LIMITS = {", 1)[1].split("};", 1)[0]
    parsed = {
        m.group(1): (int(m.group(2)), int(m.group(3)))
        for m in re.finditer(r"(\w+):\s*\{\s*fresh:\s*(\d+),\s*aging:\s*(\d+)\s*\}", block)
    }
    assert parsed == fr.FRESHNESS_LIMITS


def test_period_end_and_levels():
    assert fr.period_end(date(2026, 2, 1), "monthly") == date(2026, 2, 28)
    assert fr.period_end(date(2026, 4, 1), "quarterly") == date(2026, 6, 30)
    assert fr.period_end(date(2025, 1, 1), "annual") == date(2025, 12, 31)
    assert fr.period_end(date(2026, 9, 28), "weekly") == date(2026, 10, 4)
    # Образец тестера: Франция, ряд до декабря 2025 -> 'Устарело' 12.10.2026
    assert fr.freshness_level(date(2025, 12, 1), "monthly", TODAY) == "stale"
    assert fr.freshness_level(date(2026, 8, 1), "monthly", TODAY) == "fresh"   # 42 дня после 31.08
    assert fr.freshness_level(date(2026, 7, 1), "monthly", TODAY) == "aging"   # 73 дня после 31.07
    assert fr.freshness_level(date(2026, 5, 1), "monthly", TODAY) == "stale"   # 134 дня после 31.05
    # годовые производные (последний завершённый год) не шумят
    assert fr.freshness_level(date(2025, 1, 1), "annual", TODAY) == "fresh"
    assert fr.freshness_level(date(2024, 1, 1), "annual", TODAY) == "aging"
    assert fr.freshness_level(date(2023, 1, 1), "annual", TODAY) == "stale"
    assert fr.freshness_level(None, "monthly", TODAY) is None
    assert fr.normalize_frequency("weird") == "monthly"


def _g(domain, source, total, stale, causes, examples, counts=None, ages=None):
    g = fr.FreshnessGroup(domain, source)
    g.total, g.stale = total, stale
    g.causes.update(causes)
    g.examples = examples
    g.example_counts = dict(counts or {})
    g.example_ages = dict(ages or {})
    return g


def test_message_is_one_grouped_text_with_sources_counts_and_examples():
    report = fr.FreshnessReport("t", TODAY.isoformat(), [
        _g("world", "Мир · eurostat", 1000, 300, {"parser": 280, "source": 20}, ["sts_trtu_m", "ei_isrt_m"]),
        _g("ru", "Россия · Росстат", 200, 12, {"source": 12}, ["birth-rate"]),
        _g("ru", "Россия · ЦБ", 100, 0, {}, []),
    ], )
    text = fr.format_message(report)
    assert text.count("Сторож свежести") == 1
    assert "Просрочено 312 из 1300" in text
    assert "Мир · eurostat: 300 из 1000" in text and "sts_trtu_m" in text
    assert "Россия · Росстат: 12 из 200" in text
    assert "Россия · ЦБ" not in text            # здоровые источники не перечисляются
    assert text.index("eurostat") < text.index("Росстат")   # крупные сверху


def test_message_examples_say_how_many_series_and_how_old_and_small_sources_are_one_line():
    report = fr.FreshnessReport("t", TODAY.isoformat(), [
        _g("world", "Мир · eurostat", 1000, 300, {"parser": 280, "source": 20}, ["sts_trtu_m", "tec00134"],
           counts={"sts_trtu_m": 250, "tec00134": 1}, ages={"sts_trtu_m": 1015, "tec00134": 400}),
        _g("world", "Мир · fred", 62, 2, {"source": 2}, ["DEXUSEU"]),
        _g("world", "Мир · abs", 10, 1, {"source": 1}, ["RT"]),
    ])
    text = fr.format_message(report, previous={"stale": 400, "signature": "x", "sent_at": "2026-10-10T10:30:00"})
    assert "<code>sts_trtu_m</code> ×250 (старейший 1015 дн.)" in text
    assert "<code>tec00134</code> 400 дн." in text
    assert "Мир · fred" not in text and "Мир · abs" not in text           # мелочь не перечисляется
    assert "Мелких источников с отдельными рядами за порогом: 2 (3 рядов)" in text
    assert "В прошлом сообщении: 400 (−97)" in text
    assert len(text) < 4096


def _sent(report, days_ago=1):
    return {
        "signature": report.signature(), "digest": report.digest(), "stale": report.stale,
        "sent_at": datetime(2026, 10, 12 - days_ago, 10, 30).isoformat(),
    }


def test_noise_threshold_small_sources_flicker_does_not_resend_but_real_changes_do():
    now = datetime(2026, 10, 12, 10, 30)
    big = _g("world", "Мир · eurostat", 20000, 6000, {"parser": 5800, "source": 200}, ["sts_trtu_m"])
    first = fr.FreshnessReport("t", TODAY.isoformat(), [big])
    previous = _sent(first)
    assert fr.decide_send(first, min_stale=25, previous=previous, now=now) == (False, "unchanged")

    # один ряд FRED пересёк порог «Устарело»: заметной группы не появилось, молчим
    flicker = fr.FreshnessReport("t", TODAY.isoformat(), [big, _g("world", "Мир · fred", 62, 2, {"source": 2}, ["DEXUSEU"])])
    assert fr.decide_send(flicker, min_stale=25, previous=previous, now=now) == (False, "unchanged")
    # малая причина (3 ряда из 6000) не меняет набор причин
    tiny_cause = fr.FreshnessReport("t", TODAY.isoformat(), [
        _g("world", "Мир · eurostat", 20000, 6003, {"parser": 5800, "source": 200, "schedule": 3}, ["sts_trtu_m"])])
    assert fr.decide_send(tiny_cause, min_stale=25, previous=previous, now=now) == (False, "unchanged")
    # колебание на 10 %: мельче четверти
    wobble = fr.FreshnessReport("t", TODAY.isoformat(), [_g("world", "Мир · eurostat", 20000, 6500, {"parser": 6300, "source": 200}, ["a"])])
    assert fr.decide_send(wobble, min_stale=25, previous=previous, now=now) == (False, "unchanged")

    # настоящее улучшение (после исправления среза) — сообщаем
    better = fr.FreshnessReport("t", TODAY.isoformat(), [_g("world", "Мир · eurostat", 20000, 800, {"source": 800}, ["a"])])
    assert fr.decide_send(better, min_stale=25, previous=previous, now=now) == (True, "changed:size")
    # размер тот же, но поменялась главная причина (парсер починили, остался только источник)
    swapped = fr.FreshnessReport("t", TODAY.isoformat(), [_g("world", "Мир · eurostat", 20000, 6000, {"source": 6000}, ["a"])])
    assert fr.decide_send(swapped, min_stale=25, previous=previous, now=now) == (True, "changed:causes")
    shrink = fr.FreshnessReport("t", TODAY.isoformat(), [_g("world", "Мир · eurostat", 20000, 3000, {"parser": 2800, "source": 200}, ["a"])])
    assert fr.decide_send(shrink, min_stale=25, previous=previous, now=now) == (True, "changed:size")
    # источник встал целиком (мало рядов, но вся группа) — это заметная новая группа
    stopped = fr.FreshnessReport("t", TODAY.isoformat(), [big, _g("world", "Мир · banxico_sie", 6, 4, {"schedule": 4}, ["SF43718"])])
    assert fr.decide_send(stopped, min_stale=25, previous=previous, now=now) == (True, "changed:whole")
    # мелкая группа у границы порога (9 -> 10 рядов из 5000) сообщения не вызывает
    edge = fr.FreshnessReport("t", TODAY.isoformat(), [big, _g("ru", "Россия · Росстат", 5000, 10, {"source": 10}, ["x"])])
    assert fr.decide_send(edge, min_stale=25, previous=previous, now=now) == (False, "unchanged")
    # а крупная новая группа (20+ рядов) вызывает
    grown = fr.FreshnessReport("t", TODAY.isoformat(), [big, _g("ru", "Россия · Росстат", 5000, 30, {"source": 30}, ["x"])])
    assert fr.decide_send(grown, min_stale=25, previous=previous, now=now) == (True, "changed:size")
    # без изменений неделю — напоминание
    assert fr.decide_send(first, min_stale=25, previous=_sent(first, days_ago=8), now=now) == (True, "reminder")


def test_decide_send_threshold_change_and_reminder():
    now = datetime(2026, 10, 12, 10, 30)
    base = [_g("world", "Мир · eurostat", 1000, 300, {"parser": 300}, ["a"])]
    report = fr.FreshnessReport("t", TODAY.isoformat(), base)
    assert fr.decide_send(report, min_stale=400, previous=None, now=now) == (False, "below_threshold")
    assert fr.decide_send(report, min_stale=25, previous=None, now=now) == (True, "first")
    same = {"signature": report.signature(), "sent_at": datetime(2026, 10, 11, 10, 30).isoformat()}
    assert fr.decide_send(report, min_stale=25, previous=same, now=now) == (False, "unchanged")
    old = {"signature": report.signature(), "sent_at": datetime(2026, 10, 4, 10, 30).isoformat()}
    assert fr.decide_send(report, min_stale=25, previous=old, now=now) == (True, "reminder")
    # состав изменился: появилась новая группа
    changed = fr.FreshnessReport("t", TODAY.isoformat(), base + [_g("ru", "Россия · Росстат", 10, 5, {"source": 5}, ["x"])])
    assert fr.decide_send(changed, min_stale=25, previous=same, now=now) == (True, "changed")
    # то же число порядка величины -> та же подпись (не шумим из-за 300 -> 305)
    near = fr.FreshnessReport("t", TODAY.isoformat(), [_g("world", "Мир · eurostat", 1000, 305, {"parser": 305}, ["a"])])
    assert near.signature() == report.signature()


def _seed(auth_env):
    async def go():
        async with auth_env["session_maker"]() as db:
            fresh = Indicator(code="cpi", name="ИПЦ", frequency="monthly", source="Росстат",
                              parser_type="rosstat_cpi_xlsx", is_active=True, is_listed=True)
            frozen = Indicator(code="birth-rate", name="Рождаемость", frequency="annual", source="Росстат",
                               parser_type="rosstat_demo", is_active=True, is_listed=True)
            zero = Indicator(code="fuel-ai92", name="АИ-92", frequency="weekly", source="Росстат",
                             parser_type="rosstat_weekly_price", is_active=True, is_listed=True)
            hidden = Indicator(code="x-year", name="x", frequency="annual", source="Росстат",
                               parser_type="derived", is_active=True, is_listed=False)
            db.add_all([fresh, frozen, zero, hidden])
            await db.flush()
            db.add_all([
                IndicatorData(indicator_id=fresh.id, date=date(2026, 9, 1), value=1),
                IndicatorData(indicator_id=frozen.id, date=date(2023, 1, 1), value=1),
                IndicatorData(indicator_id=zero.id, date=date(2026, 5, 4), value=1),
                IndicatorData(indicator_id=hidden.id, date=date(2020, 1, 1), value=1),
                FetchLog(indicator_id=frozen.id, status="no_new_data", started_at=datetime(2026, 10, 12, 3)),
                FetchLog(indicator_id=zero.id, status="parsed_zero", started_at=datetime(2026, 10, 12, 3)),
            ])
            fr_c = WorldCountry(code="FR", slug="france", name_ru="Франция", name_en="France", is_active=True)
            db.add(fr_c)
            await db.flush()
            def w(code, ds, he, listed=True, freq="monthly"):
                return WorldIndicator(
                    country_id=fr_c.id, code=code, dataset_id=ds, provider="eurostat",
                    slice_json={}, slice_hash=code, frequency=freq, name_ru=code, unit="I15",
                    unit_ru="индекс", is_listed=listed, points_count=3, history_end=he,
                )
            db.add_all([
                w("fr-live", "prc_hicp_minr", date(2026, 8, 1)),
                w("fr-cind", "prc_hicp_cind", date(2025, 12, 1)),
                w("fr-sts", "sts_trtu_m", date(2023, 12, 1)),
                w("fr-unlisted-old", "demo_old", date(2010, 1, 1), listed=False),
            ])
            db.add(WorldDatasetState(provider="eurostat", dataset_id="sts_trtu_m", status="ok",
                                     last_update_of_data=date(2026, 10, 10)))
            db.add(RegionIndicator(code="r-old", table_code="1.1", section_num=1, section_name="s",
                                   name="n", year_max=2019, is_listed=True))
            db.add(RegionIndicator(code="r-ok", table_code="1.2", section_num=1, section_name="s",
                                   name="n", year_max=2024, is_listed=True))
            await db.commit()

    asyncio.run(go())


def test_collect_groups_causes_and_ignores_unlisted(auth_env):
    _seed(auth_env)

    async def go():
        async with auth_env["session_maker"]() as db:
            return await fr.collect_freshness(db, TODAY)

    report = asyncio.run(go())
    data = report.as_dict()
    by_source = {g["source"]: g for g in data["groups"]}

    ru = by_source["Россия · Росстат"]
    assert ru["total"] == 3                      # непубличный x-year не считается
    assert ru["stale"] == 2                      # birth-rate (2023) и fuel-ai92 (с мая)
    assert ru["causes"] == {"source": 1, "parser": 1}   # заморожен источником / parsed_zero = наш парсер
    assert set(ru["examples"]) == {"birth-rate", "fuel-ai92"}

    world = by_source["Мир · eurostat"]
    assert world["total"] == 3 and world["stale"] == 2
    # cind - остановленный дубль, sts - Евростат обновил набор позже нашей точки
    assert world["causes"] == {"duplicate": 1, "parser": 1}
    assert set(world["examples"]) == {"prc_hicp_cind", "sts_trtu_m"}

    assert by_source["Регионы России · Росстат/ЕМИСС"]["stale"] == 1
    # примеры - самые крупные наборы, а не первые попавшиеся
    assert world["examples"][0] in {"prc_hicp_cind", "sts_trtu_m"}
    assert data["stale_series"] == 2 + 2 + 1 and data["total_series"] == 3 + 3 + 2


def test_job_sends_one_message_then_stays_silent_and_endpoint_needs_token(auth_env, auth_client, monkeypatch):
    import fakeredis.aioredis

    from app.config import settings
    import app.core.cache as cache_mod
    from app.tasks import freshness_watchdog as job

    _seed(auth_env)
    sent = []

    async def fake_send(message, *a, **k):
        sent.append(message)
        return True

    redis = fakeredis.aioredis.FakeRedis()

    async def fake_state():
        return redis

    monkeypatch.setattr(job, "send_telegram", fake_send)
    monkeypatch.setattr(job, "async_session", auth_env["session_maker"])
    monkeypatch.setattr(cache_mod, "get_state_redis", fake_state)
    monkeypatch.setattr(settings, "freshness_watchdog_min_stale", 3)
    monkeypatch.setattr(settings, "analytics_api_token", "t0k")
    real_collect = fr.collect_freshness

    async def collect_at_fixed_day(db, today=None):
        return await real_collect(db, TODAY)

    monkeypatch.setattr(job, "collect_freshness", collect_at_fixed_day)

    async def twice():
        return await job.freshness_watchdog_job(), await job.freshness_watchdog_job()

    first, second = asyncio.run(twice())
    assert first["notified"] is True and len(sent) == 1
    assert "Сторож свежести" in sent[0]
    assert second["notified"] is False and second["reason"] == "unchanged"
    assert len(sent) == 1                                   # повтор не чаще напоминания

    assert auth_client.get("/api/v1/health/freshness").status_code == 403
    ok = auth_client.get("/api/v1/health/freshness", headers={"X-Analytics-Token": "t0k"})
    assert ok.status_code == 200
    body = ok.json()
    assert body["watchdog_enabled"] is False                # флаг по умолчанию выключен
    assert body["stale_series"] >= 5 and body["groups"]
