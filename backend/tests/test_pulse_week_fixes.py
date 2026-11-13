"""Разбор сообщений бота за 06–13.11.2026: мелкие поломки, которых не было видно в утренних сводках."""
import asyncio
from datetime import date, datetime, timedelta

import pytest

from sqlalchemy import select

from app.models import BehaviorEvent, EconomicEvent, Indicator, RawMetrikaVisit
from app.services.calendar_sources.common import CalendarCandidate, upsert_calendar_candidates


def test_metrika_digest_block_retries_a_temporary_failure(monkeypatch):
    """12 и 13.11 Метрика ответила 503 в 09:00:04, блок визитов и целей выпал из дайджеста целиком."""
    from app.services.yandex_client import YandexApiError
    from app.tasks import analytics_scheduler as sched

    calls = []

    async def flaky(report_date):
        calls.append(report_date)
        if len(calls) < 3:
            raise YandexApiError("Yandex API returned HTTP 503 for GET /stat/v1/data", status_code=503)
        return ["🌐 Визиты 10, посетители 9"]

    monkeypatch.setattr(sched, "_metrika_goal_lines", flaky)
    lines = asyncio.run(sched._metrika_goal_lines_with_retry(date(2026, 11, 12), pauses=(0, 0)))
    assert lines == ["🌐 Визиты 10, посетители 9"] and len(calls) == 3


def test_metrika_digest_block_does_not_retry_a_token_failure(monkeypatch):
    from app.services.yandex_client import YandexApiError
    from app.tasks import analytics_scheduler as sched

    calls = []

    async def denied(report_date):
        calls.append(report_date)
        raise YandexApiError("Yandex API returned HTTP 403 for GET /stat/v1/data", status_code=403)

    monkeypatch.setattr(sched, "_metrika_goal_lines", denied)
    with pytest.raises(YandexApiError):
        asyncio.run(sched._metrika_goal_lines_with_retry(date(2026, 11, 12), pauses=(0, 0)))
    assert len(calls) == 1


def test_latest_ingest_times_match_the_full_scan(auth_env):
    """Дешёвые запросы свежести дают тот же ответ, что прежний max(ingested_at) по всей таблице."""
    from app.services.ingest_freshness import latest_behavior_event_ingest, latest_metrika_visit_ingest

    async def check():
        async with auth_env["session_maker"]() as db:
            assert await latest_metrika_visit_ingest(db) is None
            assert await latest_behavior_event_ingest(db) is None
            today = date(2026, 11, 13)
            db.add_all([
                RawMetrikaVisit(counter_id="1", visit_id="old", visit_date=date(2026, 3, 1), row_hash="a",
                                ingested_at=datetime(2026, 3, 2, 8, 0)),
                RawMetrikaVisit(counter_id="1", visit_id="new", visit_date=today - timedelta(days=1), row_hash="b",
                                ingested_at=datetime(2026, 11, 13, 5, 20)),
                RawMetrikaVisit(counter_id="1", visit_id="rewritten", visit_date=today - timedelta(days=3),
                                row_hash="c", ingested_at=datetime(2026, 11, 13, 5, 21)),
            ])
            await db.commit()
            assert await latest_metrika_visit_ingest(db, today=today) == datetime(2026, 11, 13, 5, 21)
            # сырьё старше окна: тревога «Метрика не обновлялась» всё равно сработает
            assert await latest_metrika_visit_ingest(db, today=today + timedelta(days=60)) is None

    asyncio.run(check())


def test_calendar_refresh_skips_a_colliding_event_and_keeps_the_rest(auth_env):
    """13.11.2026: одно событие встало на занятую дату того же показателя и отменило обновление всего календаря."""

    def candidate(key, day, title, code="cpi"):
        return CalendarCandidate(event_key=key, title=title, event_type="data_release", source="rosstat",
                                 scheduled_date=day, date_confidence="official_explicit", importance=3,
                                 source_url="https://rosstat.gov.ru/", indicator_code=code)

    async def check():
        async with auth_env["session_maker"]() as db:
            db.add_all([
                Indicator(code=code, name=code, name_en=code, unit="%", frequency="monthly",
                          source="Росстат", parser_type="rosstat_cpi", is_active=True)
                for code in ("cpi", "ppi")
            ])
            await db.commit()
            await upsert_calendar_candidates(db, [
                candidate("ipc:2026-09", date(2026, 11, 14), "ИПЦ за сентябрь"),
                candidate("ipc:2026-10", date(2026, 11, 20), "ИПЦ за октябрь"),
            ])
            # источник перенёс сентябрьский выпуск на день октябрьского; следом идёт обычное новое событие
            changed = await upsert_calendar_candidates(db, [
                candidate("ipc:2026-09", date(2026, 11, 20), "ИПЦ за сентябрь"),
                candidate("ppi:2026-10", date(2026, 11, 21), "ИЦП за октябрь", code="ppi"),
            ])
            rows = {e.event_key: e.scheduled_date for e in (
                await db.execute(select(EconomicEvent))).scalars()}
            return changed, rows

    changed, rows = asyncio.run(check())
    assert rows["ppi:2026-10"] == date(2026, 11, 21)   # остальной календарь обновился
    assert rows["ipc:2026-10"] == date(2026, 11, 20)
    assert rows["ipc:2026-09"] == date(2026, 11, 14)   # спорное событие осталось как было
    assert changed == 1


def test_small_tables_are_counted_exactly(auth_env):
    from app.models import User
    from app.services.dataset_inventory import EXACT_COUNT_MAX_ROWS, _row_count

    async def check():
        async with auth_env["session_maker"]() as db:
            return await _row_count(db, User), await _row_count(db, BehaviorEvent)

    assert asyncio.run(check()) == (0, 0)
    assert EXACT_COUNT_MAX_ROWS <= 100_000  # точный счёт только там, где он не читает сотни мегабайт


def test_category_siblings_are_computed_once_per_country_category(auth_env, monkeypatch):
    """Блок «Ещё в разделе» читал все ряды категории на каждом рендере: 1766 строк ради 12 ссылок."""
    from sqlalchemy import event

    from app.models import WorldCountry, WorldIndicator
    from app.services import seo_world

    statements: list[str] = []
    store: dict[str, list[int]] = {}

    async def fake_get(key):
        return store.get(key)

    async def fake_set(key, value, ttl=None):
        store[key] = value

    monkeypatch.setattr(seo_world, "cache_get", fake_get)
    monkeypatch.setattr(seo_world, "cache_set", fake_set)

    async def check():
        async with auth_env["session_maker"]() as db:
            country = WorldCountry(code="DE", slug="germany", name_ru="Германия", name_en="Germany",
                                   region_ru="Европа", sort_order=1)
            db.add(country)
            await db.flush()
            rows = [
                WorldIndicator(country_id=country.id, code=f"de-series-{i:02d}", dataset_id=f"set_{i:02d}",
                               slice_json={"unit": "PC"}, slice_hash=f"h{i}", name_ru=f"Ряд {i:02d}",
                               name_quality="curated", unit="PC", frequency="monthly", category_ru="Цены",
                               is_listed=True, provider="eurostat")
                for i in range(20)
            ]
            hidden = WorldIndicator(country_id=country.id, code="de-hidden", dataset_id="set_hidden",
                                    slice_json={"unit": "PC"}, slice_hash="hh", name_ru="Ряд 00а",
                                    name_quality="curated", unit="PC", frequency="monthly", category_ru="Цены",
                                    is_listed=False, provider="eurostat")
            db.add_all(rows + [hidden])
            await db.commit()

            engine = db.bind.sync_engine

            @event.listens_for(engine, "before_cursor_execute")
            def _capture(conn, cursor, statement, parameters, context, executemany):
                statements.append(statement)

            first = await seo_world._category_siblings(db, country.id, rows[0])
            cold = [s for s in statements if "category_ru" in s and "WHERE" in s]
            statements.clear()
            second = await seo_world._category_siblings(db, country.id, rows[5])
            warm = [s for s in statements if "world_indicators.category_ru =" in s]
            event.remove(engine, "before_cursor_execute", _capture)
            return [r.code for r in first], [r.code for r in second], len(cold), len(warm)

    first, second, cold, warm = asyncio.run(check())
    assert first == [f"de-series-{i:02d}" for i in range(1, 13)]           # без самого ряда, 12 ссылок
    assert second == [f"de-series-{i:02d}" for i in range(13) if i != 5]   # тот же состав, свой ряд убран
    assert "de-hidden" not in first + second
    assert cold >= 1 and warm == 0   # второй рендер не читает категорию целиком
    assert len(store) == 1 and len(next(iter(store.values()))) == 13   # в кэше только список id


STEEL_A = "На сайте нет данных/индикатора по стали (производство, цены), хотя есть повторяющийся спрос во внутреннем поиске"
STEEL_B = "На сайте нет индикатора цены/производства стали, хотя есть повторяющийся спрос во внутреннем поиске"
PALLADIUM = "На сайте нет индикатора цены палладия, хотя есть индикатор золота и повторяющийся спрос в поиске на другие металлы"
BUTTON = "Кнопка «Приблизить Землю» на 3D-глобусе главной страницы не даёт видимого отклика на клик и вызывает rage-клики"


def test_repeated_hypothesis_is_recognised_and_different_topics_are_not():
    """13.11.2026: 266 открытых гипотез при 60 темах — модель переписывала одно и то же новыми записями."""
    from app.services.pulse_report import similar_open_hypothesis

    stored = {156: STEEL_A, 66: PALLADIUM, 304: BUTTON}
    assert similar_open_hypothesis(STEEL_B, stored) == 156
    # тот же шаблон фразы, другой показатель: это новая тема
    assert similar_open_hypothesis(
        "На сайте нет индикатора по поголовью птицы, хотя есть повторяющийся спрос во внутреннем поиске", stored
    ) is None
    assert similar_open_hypothesis("Кнопка 'Приблизить Землю' на глобусе главной не даёт отклика на клик, rage-клики",
                                   stored) == 304
    assert similar_open_hypothesis("", stored) is None and similar_open_hypothesis(STEEL_B, {}) is None


def test_repeated_hypothesis_updates_the_stored_one(auth_env, monkeypatch):
    from contextlib import asynccontextmanager

    from app.models import Hypothesis
    from app.services import pulse_report

    @asynccontextmanager
    async def session():
        async with auth_env["session_maker"]() as db:
            yield db

    monkeypatch.setattr(pulse_report, "analytics_session", session)

    async def check():
        async with auth_env["session_maker"]() as db:
            db.add_all([
                Hypothesis(statement=STEEL_A, confidence=0.5, created_at=datetime(2026, 9, 4),
                           updated_at=datetime(2026, 9, 4)),
                Hypothesis(statement=PALLADIUM, confidence=0.35, created_at=datetime(2026, 7, 23),
                           updated_at=datetime(2026, 7, 23)),
                # уже закрытая гипотеза в сравнении не участвует
                Hypothesis(statement=BUTTON, verdict=True, confidence=0.9, created_at=datetime(2026, 7, 1),
                           updated_at=datetime(2026, 7, 1)),
            ] + [
                Hypothesis(statement=text, confidence=0.4, created_at=datetime(2026, 8, day),
                           updated_at=datetime(2026, 8, day))
                for day, text in enumerate([
                    "На сайте нет индикатора по банкротствам организаций, хотя есть повторяющийся спрос",
                    "Внутренний поиск не находит региональный разрез безработицы, хотя показатель есть",
                    "Страницы карт регионов покидают почти мгновенно: вероятен сбой отрисовки карты",
                ], start=1)
            ])
            await db.commit()
        applied = await pulse_report._apply_hypothesis_updates([
            {"id": None, "statement": STEEL_B, "verdict": None, "confidence": 0.6, "rationale": "снова ищут сталь"},
            {"id": None, "statement": BUTTON, "verdict": None, "confidence": 0.5, "rationale": "rage-клики"},
        ])
        context = await pulse_report._open_hypotheses()
        async with auth_env["session_maker"]() as db:
            rows = (await db.execute(select(Hypothesis).order_by(Hypothesis.id))).scalars().all()
            return applied, [(r.statement, float(r.confidence)) for r in rows], context

    applied, rows, context = asyncio.run(check())
    assert applied == 2 and len(rows) == 7            # сталь обновлена на месте, кнопка записана новой строкой
    assert rows[0] == (STEEL_B, 0.6)
    assert [r[0] for r in rows].count(BUTTON) == 2    # закрытая гипотеза не поглощает новую открытую
    # модель видит свежие гипотезы первыми, самую давнюю последней, без длинных обоснований
    assert context[-1]["statement"][:20] == PALLADIUM[:20]
    assert {context[0]["statement"], context[1]["statement"]} == {STEEL_B, BUTTON}
    assert all(set(item) == {"id", "statement"} for item in context) and len(context) == 6
