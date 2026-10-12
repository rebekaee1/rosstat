"""Блок «Актуальные данные» на странице устаревшего ряда без живого двойника."""
import asyncio
from datetime import date

from app.models import Indicator, IndicatorData, WorldCountry, WorldDatasetState, WorldIndicator
from app.services.freshness_note import (
    build_message,
    decide_reason,
    period_label,
    ru_freshness_note,
    world_freshness_note,
)

TODAY = date(2026, 10, 12)


def test_period_labels_follow_frequency_and_locale():
    assert period_label(date(2023, 12, 1), "monthly") == "декабря 2023"
    assert period_label(date(2023, 12, 1), "monthly", "en") == "December 2023"
    assert period_label(date(2023, 10, 1), "quarterly") == "IV квартала 2023"
    assert period_label(date(2023, 10, 1), "quarterly", "en") == "Q4 2023"
    assert period_label(date(2023, 1, 1), "annual") == "2023"


def test_message_has_honest_tail_with_and_without_nearest():
    with_nearest = build_message(
        reason="source_stopped", last=date(2023, 12, 1), frequency="monthly",
        source_updated_at=None, nearest_name="Розничная торговля, сезонно скорректировано",
    )
    assert with_nearest == (
        "Источник не обновлял ряд с декабря 2023. "
        "Ближайший актуальный показатель: Розничная торговля, сезонно скорректировано."
    )
    bare = build_message(reason="series_lag", last=date(2025, 1, 1), frequency="annual",
                         source_updated_at=None, nearest_name=None)
    assert bare == "Источник обновляет набор, но по этому ряду данных позже 2025 нет."
    assert "no longer" in build_message(reason="retired", last=date(2025, 1, 1), frequency="annual",
                                        source_updated_at=None, nearest_name=None, locale="en")


def test_reason_prefers_our_failure_then_quiet_source():
    kw = dict(dataset_newest_is_stale=False, today=TODAY, retired=False)
    assert decide_reason(source_updated_at=date(2026, 10, 1), state_status="quarantine", **kw) == "update_delayed"
    assert decide_reason(source_updated_at=date(2026, 10, 1), state_status="ok", **kw) == "series_lag"
    assert decide_reason(source_updated_at=date(2026, 3, 20), state_status="ok", **kw) == "source_stopped"
    assert decide_reason(source_updated_at=None, state_status="ok", **kw) == "source_stopped"
    assert decide_reason(source_updated_at=date(2026, 10, 1), state_status="ok",
                         dataset_newest_is_stale=True, today=TODAY, retired=False) == "source_stopped"
    assert decide_reason(source_updated_at=date(2026, 10, 1), state_status="ok",
                         dataset_newest_is_stale=False, today=TODAY, retired=True) == "retired"


def _world(db, country_id, code, he, **kw):
    return WorldIndicator(
        country_id=country_id, provider="eurostat", code=code, dataset_id="tec00134",
        slice_json=kw.pop("slice_json", {"freq": "A", "unit": "PC_TOT", "cpa": "A"}), slice_hash=code,
        frequency="annual", name_ru=kw.pop("name_ru", code), name_en=kw.pop("name_en", code),
        unit="PC_TOT", unit_ru="%", is_listed=True, points_count=12, history_end=he, **kw,
    )


def test_world_note_names_nearest_fresh_measure_of_same_country(auth_env):
    async def go():
        async with auth_env["session_maker"]() as db:
            c = WorldCountry(code="DE", slug="germany", name_ru="Германия", name_en="Germany", is_active=True)
            db.add(c)
            await db.flush()
            old = _world(db, c.id, "de-old", date(2023, 1, 1), name_ru="Старый ряд")
            fresh = _world(db, c.id, "de-fresh", date(2025, 1, 1), name_ru="Свежий ряд",
                           slice_json={"freq": "A", "unit": "PC_EUR", "cpa": "A"})
            other_subject = _world(db, c.id, "de-other", date(2025, 1, 1), name_ru="Другой предмет",
                                   slice_json={"freq": "A", "unit": "PC_TOT", "cpa": "B"})
            db.add_all([old, fresh, other_subject, WorldDatasetState(
                provider="eurostat", dataset_id="tec00134", status="ok",
                last_update_of_data=date(2026, 10, 9))])
            await db.commit()
            return old.id, fresh.id

    old_id, _ = asyncio.run(go())

    async def check():
        async with auth_env["session_maker"]() as db:
            ind = await db.get(WorldIndicator, old_id)
            note = await world_freshness_note(db, ind, today=TODAY, country_slug="germany")
            assert note["level"] == "stale" and note["reason"] == "series_lag"
            assert note["nearest"]["url"] == "/germany/indicator/de-fresh"
            assert note["message"].endswith("Ближайший актуальный показатель: Свежий ряд.")
            assert note["nearest"]["code"] != "de-other", "другой предмет (иная отрасль) не предлагается"
            assert note["age_days"] > 700
            # свежий ряд блока не получает
            fresh_ind = (await db.execute(
                WorldIndicator.__table__.select().where(WorldIndicator.code == "de-fresh")
            )).first()
            assert await world_freshness_note(db, await db.get(WorldIndicator, fresh_ind.id), today=TODAY) is None

    asyncio.run(check())


def test_ru_note_for_stalled_indicator_points_to_fresh_one_in_category(auth_env):
    async def go():
        async with auth_env["session_maker"]() as db:
            stalled = Indicator(code="working-age-population", name="Население трудоспособного возраста",
                                unit="тыс.", category="Население", frequency="annual", source="Росстат",
                                is_active=True, is_listed=True)
            live = Indicator(code="population-total", name="Численность населения",
                             unit="тыс.", category="Население", frequency="annual", source="Росстат",
                             is_active=True, is_listed=True)
            other = Indicator(code="wages", name="Зарплата", unit="руб.", category="Население",
                              frequency="annual", source="Росстат", is_active=True, is_listed=True)
            db.add_all([stalled, live, other])
            await db.flush()
            db.add_all([
                IndicatorData(indicator_id=stalled.id, date=date(2023, 1, 1), value=80000),
                IndicatorData(indicator_id=live.id, date=date(2025, 1, 1), value=146000),
                IndicatorData(indicator_id=other.id, date=date(2025, 1, 1), value=70000),
            ])
            await db.commit()
            return stalled.id

    sid = asyncio.run(go())

    async def check():
        async with auth_env["session_maker"]() as db:
            ind = await db.get(Indicator, sid)
            note = await ru_freshness_note(db, ind, date(2023, 1, 1), today=TODAY)
            assert note["reason"] == "source_stopped"
            assert note["nearest"]["code"] == "population-total"
            assert "Численность населения" in note["message"]
            assert await ru_freshness_note(db, ind, date(2026, 8, 1), today=TODAY) is None

    asyncio.run(check())


def test_world_note_without_same_subject_mate_has_honest_text_and_no_nearest(auth_env):
    async def go():
        async with auth_env["session_maker"]() as db:
            c = WorldCountry(code="FR", slug="france", name_ru="Франция", name_en="France", is_active=True)
            db.add(c)
            await db.flush()
            old = _world(db, c.id, "fr-old", date(2021, 1, 1), name_ru="Старый ряд")
            alien = _world(db, c.id, "fr-alien", date(2025, 1, 1), name_ru="Чужой предмет",
                           slice_json={"freq": "A", "unit": "PC_TOT", "cpa": "Z"})
            db.add_all([old, alien, WorldDatasetState(
                provider="eurostat", dataset_id="tec00134", status="ok",
                last_update_of_data=date(2026, 3, 20))])
            await db.commit()
            return old.id

    old_id = asyncio.run(go())

    async def check():
        async with auth_env["session_maker"]() as db:
            note = await world_freshness_note(db, await db.get(WorldIndicator, old_id), today=TODAY,
                                              country_slug="france")
            assert note["nearest"] is None
            assert note["reason"] == "source_stopped"
            assert note["message"] == "Источник не обновлял ряд с 2021."

    asyncio.run(check())


def test_ssr_page_of_stale_series_carries_the_honest_line(auth_env):
    from app.models import WorldDataPoint
    from app.services.seo_world import render_world_indicator_html

    async def go():
        async with auth_env["session_maker"]() as db:
            c = WorldCountry(code="IT", slug="italy", name_ru="Италия", name_en="Italy", is_active=True)
            db.add(c)
            await db.flush()
            old = _world(db, c.id, "it-old", date(2021, 1, 1), name_ru="Старый ряд")
            last_year = date(date.today().year - 1, 1, 1)
            fresh = _world(db, c.id, "it-fresh", last_year, name_ru="Свежий ряд",
                           slice_json={"freq": "A", "unit": "PC_EUR", "cpa": "A"})
            db.add_all([old, fresh])
            await db.flush()
            db.add_all([
                WorldDataPoint(indicator_id=old.id, date=date(2020, 1, 1), value=1.0),
                WorldDataPoint(indicator_id=old.id, date=date(2021, 1, 1), value=2.0),
                WorldDataPoint(indicator_id=fresh.id, date=last_year, value=3.0),
            ])
            await db.commit()
        async with auth_env["session_maker"]() as db:
            return await render_world_indicator_html("italy", "it-old", db)

    status, html = asyncio.run(go())
    assert status == 200
    assert "Источник не обновлял ряд с 2021." in html
    assert "Ближайший актуальный показатель: Свежий ряд." in html
