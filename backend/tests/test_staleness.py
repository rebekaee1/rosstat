"""Staleness-алерт: пороги, классы просрочек, группировка и «только новые»."""
from datetime import date, datetime, timedelta

from app.services.staleness import (
    PERIOD_DAYS,
    STALENESS_SLA_DAYS,
    StaleRow,
    build_report,
    derived_roots,
    find_stale,
    plan_staleness_message,
)

TODAY = date(2026, 9, 26)
NOW = datetime(2026, 9, 26, 10, 0)


def _row(code, freq, age, *, parser="rosstat_demo", source="Росстат",
         status="no_new_data", fetched_days_ago=0):
    return StaleRow(
        code=code, frequency=freq, max_date=TODAY - timedelta(days=age),
        parser_type=parser, source=source, last_status=status,
        last_fetch_at=NOW - timedelta(days=fetched_days_ago),
    )


def test_find_stale_reexported_thresholds_unchanged():
    assert STALENESS_SLA_DAYS == {
        "daily": 7, "weekly": 21, "monthly": 75, "quarterly": 150, "annual": 550,
    }
    rows = [
        ("a", "annual", TODAY - timedelta(days=551)),
        ("b", "annual", TODAY - timedelta(days=550)),
        ("c", "irregular", TODAY - timedelta(days=551)),
        ("d", "monthly", None),
    ]
    assert dict(find_stale(rows, TODAY)) == {"a": 551, "c": 551}


def test_period_days_cover_sla_frequencies():
    assert set(PERIOD_DAYS) == set(STALENESS_SLA_DAYS)


def test_healthy_fetch_within_one_period_over_sla_is_not_reported():
    # годовой ряд: SLA 550, период 366 -> до 916 дней это обычный лаг публикации
    report = build_report([_row("births", "annual", 700)], {}, today=TODAY, now=NOW)
    assert report.total_stale == 1
    assert report.within_lag == 1
    assert not report.attention and not report.frozen
    assert plan_staleness_message(report, None, weekly_due=True) is None


def test_threshold_boundary_between_lag_and_frozen():
    sla, period = STALENESS_SLA_DAYS["annual"], PERIOD_DAYS["annual"]
    at_edge = build_report(
        [_row("a", "annual", sla + period)], {}, today=TODAY, now=NOW,
    )
    beyond = build_report(
        [_row("a", "annual", sla + period + 1)], {}, today=TODAY, now=NOW,
    )
    assert at_edge.within_lag == 1 and not at_edge.frozen
    assert [i.code for i in beyond.frozen] == ["a"]


def test_healthy_fetch_beyond_one_missed_release_is_frozen_counter_only():
    rows = [
        _row("births", "annual", 999),
        _row("pop-over-working-age", "annual", 1364),
    ]
    report = build_report(rows, {}, today=TODAY, now=NOW)
    assert {i.code for i in report.frozen} == {"births", "pop-over-working-age"}
    assert not report.attention
    text = plan_staleness_message(report, set(), weekly_due=True)
    # замороженные — только счётчик, без перечисления кодов
    assert "заморожены источником" in text and "новых точек нет): 2" in text
    assert "births" not in text and "pop-over-working-age" not in text


def test_failed_parser_is_attention_even_just_over_sla():
    row = _row("gold-price", "daily", 8, parser="cbr_gold_html", source="Банк России",
               status="failed")
    report = build_report([row], {}, today=TODAY, now=NOW)
    assert [i.code for i in report.attention] == ["gold-price"]
    assert report.attention[0].kind == "source_problem"


def test_silent_parser_for_a_week_is_attention():
    row = _row("cpi", "monthly", 100, parser="rosstat_cpi_xlsx", fetched_days_ago=9)
    report = build_report([row], {}, today=TODAY, now=NOW)
    assert [i.code for i in report.attention] == ["cpi"]


def test_derived_follows_stale_source_but_orphan_is_reported():
    deriv = {"cpi-yoy": ("cpi",), "cpi-yoy-abs": ("cpi-yoy",), "gdp-qoq": ("gdp",)}
    rows = [
        _row("cpi", "monthly", 300, parser="rosstat_cpi_xlsx"),         # frozen
        _row("cpi-yoy", "monthly", 300, parser="derived"),              # следует за cpi
        _row("cpi-yoy-abs", "monthly", 300, parser="derived"),          # через цепочку
        StaleRow("gdp", "quarterly", TODAY - timedelta(days=10), "rosstat_gdp",
                 "Росстат", "success", NOW),                            # свежий
        _row("gdp-qoq", "quarterly", 200, parser="derived"),            # сирота
    ]
    report = build_report(rows, deriv, today=TODAY, now=NOW)
    assert report.derived_follow == 2
    assert [i.code for i in report.frozen] == ["cpi"]
    assert [(i.code, i.kind) for i in report.attention] == [("gdp-qoq", "derived_orphan")]
    assert derived_roots("cpi-yoy-abs", deriv) == {"cpi"}


def test_weekly_message_groups_by_family_not_row_per_series():
    rows = [
        _row(f"fx-{n}", "daily", 20 + n, parser="cbr_fx_xml", source="Банк России",
             status="failed")
        for n in range(30)
    ] + [_row("moex-a", "daily", 30, parser="moex_index_daily", source="МосБиржа",
              status="parsed_zero")]
    report = build_report(rows, {}, today=TODAY, now=NOW)
    text = plan_staleness_message(report, None, weekly_due=True)
    lines = [ln for ln in text.splitlines() if ln.startswith("•")]
    assert len(lines) == 2                       # две группы, а не 31 строка
    assert "Банк России · cbr_fx_xml: 30" in text
    assert "и ещё 27" in text                    # 3 примера + хвост
    assert len(text) < 1500


def test_daily_message_reports_only_new_overdue():
    rows = [
        _row("old-1", "daily", 40, parser="cbr_fx_xml", source="Банк России", status="failed"),
        _row("new-1", "daily", 9, parser="cbr_fx_xml", source="Банк России", status="failed"),
        _row("old-frozen", "annual", 999),
        _row("new-frozen", "annual", 1000),
    ]
    report = build_report(rows, {}, today=TODAY, now=NOW)
    known = {"old-1", "old-frozen"}
    text = plan_staleness_message(report, known, weekly_due=False)
    assert "новые просрочки" in text
    assert "new-1" in text and "new-frozen" in text
    assert "old-1" not in text and "old-frozen" not in text
    assert "Прежние просрочки (1)" in text


def test_daily_message_silent_when_nothing_new():
    rows = [_row("old-1", "daily", 40, parser="cbr_fx_xml", status="failed")]
    report = build_report(rows, {}, today=TODAY, now=NOW)
    assert plan_staleness_message(report, {"old-1"}, weekly_due=False) is None


def test_weekly_or_first_run_sends_full_even_with_known():
    rows = [_row("old-1", "daily", 40, parser="cbr_fx_xml", status="failed")]
    report = build_report(rows, {}, today=TODAY, now=NOW)
    weekly = plan_staleness_message(report, {"old-1"}, weekly_due=True)
    first = plan_staleness_message(report, None, weekly_due=False)
    assert weekly and "недельная сводка" in weekly and "old-1" in weekly
    assert first and "недельная сводка" in first


def test_job_end_to_end_weekly_then_only_new(auth_env, monkeypatch):
    """Job целиком (SQLite + fakeredis): первый прогон — сводка, второй — тишина,
    после новой просрочки — только она."""
    import asyncio

    import app.tasks.scheduler as sched
    from app.models import FetchLog, Indicator, IndicatorData

    monkeypatch.setattr(sched, "async_session", auth_env["session_maker"])
    sent = []

    async def fake_send(message, **kwargs):
        sent.append(message)
        return True

    monkeypatch.setattr(sched, "send_telegram", fake_send)
    monkeypatch.setattr("app.services.process_metrics.fd_pressure_high", lambda: False)

    async def seed(code, parser, freq, age_days, status):
        async with auth_env["session_maker"]() as db:
            ind = Indicator(
                code=code, name=code, unit="%", frequency=freq,
                source="Банк России", parser_type=parser, is_active=True,
            )
            db.add(ind)
            await db.flush()
            db.add(IndicatorData(
                indicator_id=ind.id, date=date.today() - timedelta(days=age_days), value=1,
            ))
            db.add(FetchLog(indicator_id=ind.id, status=status))
            await db.commit()

    async def scenario():
        await seed("fx-a", "cbr_fx_xml", "daily", 20, "failed")
        await seed("fresh", "cbr_fx_xml", "daily", 1, "success")
        await sched.staleness_check_job()          # первый прогон — полная сводка
        await sched.staleness_check_job()          # ничего нового — молчим
        await seed("fx-b", "cbr_fx_xml", "daily", 30, "failed")
        await sched.staleness_check_job()          # новая просрочка

    asyncio.run(scenario())
    assert len(sent) == 2
    assert "недельная сводка" in sent[0] and "fx-a" in sent[0]
    assert "новые просрочки" in sent[1]
    assert "fx-b" in sent[1] and "fx-a" not in sent[1]


def test_fd_line_is_appended():
    rows = [_row("x", "daily", 40, parser="cbr_fx_xml", status="failed")]
    report = build_report(rows, {}, today=TODAY, now=NOW)
    assert plan_staleness_message(
        report, None, weekly_due=True, fd_line="\nfd 10/100",
    ).endswith("fd 10/100")
