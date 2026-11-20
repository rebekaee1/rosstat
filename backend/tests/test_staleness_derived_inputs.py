"""«Производный ряд не пересчитан при свежем источнике» — только когда следующую точку уже можно посчитать (20.11.2026).

Недельная сводка 20.11 называла 23 сироты: 14 рядов доступности жилья (ждали зарплату Росстата за сентябрь)
и 9 годовых «% к году» курсов ЦБ к валютам, которых ЦБ не котировал в 2010–2024. Пересчёт не был сломан ни у одного.
"""

from datetime import date, datetime

from app.services.staleness import (
    StaleRow,
    build_report,
    derived_input_windows,
    next_point_input_window,
    plan_staleness_message,
    sla_days,
)

TODAY = date(2026, 11, 20)
NOW = datetime(2026, 11, 20, 7, 0)


def _row(code, freq, max_date, parser="derived", status="no_new_data"):
    return StaleRow(code, freq, max_date, parser_type=parser, source="Росстат", last_status=status, last_fetch_at=NOW)


def test_next_point_window_needs_closed_period_of_source():
    # месячный производный за август ждёт сентябрьскую точку источника
    assert next_point_input_window(date(2026, 8, 1), "monthly", "monthly") == (date(2026, 8, 31), date(2026, 10, 1))
    # квартал (якорь — третий месяц): после II кв. нужен сентябрь, а не июль-август
    assert next_point_input_window(date(2026, 6, 1), "quarterly", "monthly") == (date(2026, 8, 31), date(2026, 10, 1))
    # месячный из квартального источника: годится точка III кв. (якорь 01.09)
    start, end = next_point_input_window(date(2026, 8, 1), "monthly", "quarterly")
    assert start <= date(2026, 9, 1) < end
    # годовой из дневного: нужен декабрь следующего года
    assert next_point_input_window(date(2009, 1, 1), "annual", "daily") == (date(2010, 12, 1), date(2011, 1, 1))
    assert next_point_input_window(date(2026, 1, 1), "irregular", "daily") is None


def test_currency_gap_years_is_not_orphan():
    """sar-rub: котировки 1998–2009 и с 2025 — годового «% к году» за 2010–2025 не из чего считать."""
    deriv = {"sar-rub-yoy-year": ("sar-rub",)}
    rows = [
        _row("sar-rub", "daily", date(2026, 11, 20), parser="cbr_fx_xml"),
        _row("sar-rub-yoy-year", "annual", date(2009, 1, 1)),
    ]
    windows = derived_input_windows(rows, deriv, today=TODAY)
    assert windows == {"sar-rub-yoy-year": [("sar-rub", date(2010, 12, 1), date(2011, 1, 1))]}
    report = build_report(rows, deriv, today=TODAY, now=NOW, inputs_ready=set())
    assert not report.attention and report.derived_follow == 1
    text = plan_staleness_message(report, None, weekly_due=True)
    assert "производные ждут данных первоисточника: 1" in text
    assert "sar-rub-yoy-year" not in text


def test_housing_waits_for_wages_but_real_orphan_is_reported():
    deriv = {
        "wages-index": ("wages-nominal",),
        "housing-affordability": ("housing-price-secondary", "wages-index"),
        "housing-affordability-avg-quarter": ("housing-affordability",),
    }
    rows = [
        _row("wages-nominal", "monthly", date(2026, 8, 1), parser="rosstat_labor"),
        _row("housing-price-secondary", "quarterly", date(2026, 9, 1), parser="rosstat_housing"),
        _row("wages-index", "monthly", date(2026, 8, 1)),
        _row("housing-affordability", "monthly", date(2026, 8, 1)),
        _row("housing-affordability-avg-quarter", "quarterly", date(2026, 6, 1)),
    ]
    windows = derived_input_windows(rows, deriv, today=TODAY)
    assert set(windows) == {"wages-index", "housing-affordability", "housing-affordability-avg-quarter"}
    # сентябрьской зарплаты нет ни у одного входа — все ждут
    waiting = build_report(rows, deriv, today=TODAY, now=NOW, inputs_ready=set())
    assert not waiting.attention and waiting.derived_follow == 3
    # без проверки входов (None) — прежнее поведение: сироты
    legacy = build_report(rows, deriv, today=TODAY, now=NOW)
    assert {i.kind for i in legacy.attention} == {"derived_orphan"}
    # входы есть, а точки нет — пересчёт сломан, это сообщаем
    broken = build_report(rows, deriv, today=TODAY, now=NOW, inputs_ready={"housing-affordability"})
    assert [(i.code, i.kind) for i in broken.attention] == [("housing-affordability", "derived_orphan")]


def test_wages_nominal_publication_lag_is_within_sla():
    """Росстат выпускает зарплату месяца через 88–93 дня: август вышел 28.10, сентябрь ждём к концу ноября."""
    assert (TODAY - date(2026, 8, 1)).days <= sla_days("monthly", "wages-nominal")
    assert (date(2026, 12, 3) - date(2026, 8, 1)).days <= sla_days("monthly", "wages-nominal")
    assert sla_days("monthly", "wages-real") == 75


def test_job_checks_derived_inputs_in_database(auth_env, monkeypatch):
    """Job целиком (SQLite): дыра котировок — счётчик «ждут данных»; появилась точка закрытого периода — сирота."""
    import asyncio
    from datetime import timedelta

    import app.tasks.scheduler as sched
    from app.models import FetchLog, Indicator, IndicatorData

    monkeypatch.setattr(sched, "async_session", auth_env["session_maker"])
    sent: list[str] = []

    async def fake_send(message, **kwargs):
        sent.append(message)
        return True

    monkeypatch.setattr(sched, "send_telegram", fake_send)
    monkeypatch.setattr("app.services.process_metrics.fd_pressure_high", lambda: False)
    ids: dict[str, int] = {}

    async def seed(code, parser, freq, dates):
        async with auth_env["session_maker"]() as db:
            ind = Indicator(code=code, name=code, unit="%", frequency=freq, source="Банк России",
                            parser_type=parser, is_active=True)
            db.add(ind)
            await db.flush()
            ids[code] = ind.id
            for d in dates:
                db.add(IndicatorData(indicator_id=ind.id, date=d, value=1))
            db.add(FetchLog(indicator_id=ind.id, status="success"))
            await db.commit()

    async def add_point(code, d):
        async with auth_env["session_maker"]() as db:
            db.add(IndicatorData(indicator_id=ids[code], date=d, value=1))
            await db.commit()

    async def scenario():
        await seed("sar-rub", "cbr_fx_xml", "daily", [date(2009, 12, 15), date.today() - timedelta(days=1)])
        await seed("sar-rub-yoy-year", "derived", "annual", [date(2009, 1, 1)])
        await sched.staleness_check_job()
        await add_point("sar-rub", date(2010, 12, 15))
        await sched.staleness_check_job()

    asyncio.run(scenario())
    assert len(sent) == 2
    assert "производные ждут данных первоисточника: 1" in sent[0] and "sar-rub-yoy-year" not in sent[0]
    assert "новые просрочки" in sent[1] and "sar-rub-yoy-year" in sent[1]
