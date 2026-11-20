"""Пульс 19.11.2026: «За 14 дней 22 запланированные публикации не отмечены как вышедшие».

Сверка на боевом 20.11: из 22 строк 7 — скрытые оценки дат (их нет в публичном календаре),
6 — выпуски без точки ряда (Eurostat без ряда на сайте, резюме ЦБ, предварительная оценка ВВП),
9 — источник не дал новой точки (ежемесячные выпуски ЦБ к квартальным рядам, ИЦП из доклада
Росстата в конце месяца). Наших пропусков 0. Пульс теперь называет причину, а не одно число.
"""
import asyncio
from datetime import date, datetime

from app.models import EconomicEvent, FetchLog, Indicator
from app.services import pulse_extra


def _ind(code: str, freq: str = "monthly") -> Indicator:
    return Indicator(code=code, name=code, frequency=freq)


def _ev(title: str, day: date, *, ind=None, event_type="data_release", estimated=False, key=None) -> EconomicEvent:
    return EconomicEvent(title=title, event_type=event_type, source="cbr", scheduled_date=day,
                         indicator=ind, is_estimated=estimated, event_key=key or f"t:{title}:{day}",
                         status="scheduled")


def test_classify_reasons():
    ev = EconomicEvent(title="x", event_type="data_release", source="cbr", scheduled_date=date(2026, 11, 11),
                       indicator_id=1, event_key="k")
    assert pulse_extra.classify_unconfirmed(ev, []) == "not_fetched"
    assert pulse_extra.classify_unconfirmed(ev, [("failed", 0), ("fallback_used", 0)]) == "source_unreachable"
    assert pulse_extra.classify_unconfirmed(ev, [("failed", 0), ("no_new_data", 0)]) == "no_new_point"
    assert pulse_extra.classify_unconfirmed(ev, [("no_new_data", 0), ("success", 3)]) == "our_miss"
    report = EconomicEvent(title="Резюме", event_type="report", source="cbr", scheduled_date=date(2026, 11, 5),
                           indicator_id=1, event_key="k2")
    assert pulse_extra.classify_unconfirmed(report, [("success", 1)]) == "no_data_by_design"
    flash = EconomicEvent(title="ВВП", event_type="data_release", source="rosstat", scheduled_date=date(2026, 11, 13),
                          indicator_id=1, event_key="rosstat:plan:gdp-real:q3-2026:flash")
    assert pulse_extra.classify_unconfirmed(flash, []) == "no_data_by_design"
    no_series = EconomicEvent(title="Eurostat", event_type="data_release", source="eurostat",
                              scheduled_date=date(2026, 11, 5), indicator_id=None, event_key="k3")
    assert pulse_extra.classify_unconfirmed(no_series, []) == "no_data_by_design"


def test_past_unconfirmed_skips_hidden_estimates_and_released(auth_env):
    d = date(2026, 11, 20)

    async def run():
        async with auth_env["session_maker"]() as db:
            exports, cpi, ppi = _ind("exports", "quarterly"), _ind("cpi"), _ind("ppi")
            released = _ev("Резервы", date(2026, 11, 12), ind=_ind("international-reserves"))
            released.status, released.actual_value, released.actual_date = "released", "600", date(2026, 11, 6)
            db.add_all([
                _ev("Внешняя торговля товарами", date(2026, 11, 11), ind=exports),
                _ev("ИПЦ (скрытая оценка)", date(2026, 11, 13), ind=cpi, estimated=True),
                _ev("ИЦП", date(2026, 11, 18), ind=ppi),
                _ev("ЕС: инфляция", date(2026, 11, 18)),
                _ev("Старое", date(2026, 10, 1), ind=ppi),
                released,
            ])
            await db.flush()
            db.add_all([
                FetchLog(indicator_id=exports.id, status="no_new_data", records_added=0,
                         started_at=datetime(2026, 11, 12, 4, 0)),
                # Загрузка до дня выпуска не говорит о выпуске.
                FetchLog(indicator_id=ppi.id, status="success", records_added=1,
                         started_at=datetime(2026, 11, 10, 4, 0)),
                FetchLog(indicator_id=ppi.id, status="failed", records_added=0,
                         started_at=datetime(2026, 11, 19, 4, 0)),
            ])
            await db.commit()
            return await pulse_extra.past_unconfirmed(db, d)

    out = asyncio.run(run())
    assert out["total"] == 3
    assert out["by_reason"] == {"no_new_point": 1, "source_unreachable": 1, "no_data_by_design": 1}
    assert set(out["reasons"]) == set(out["by_reason"])
    line = [x for x in pulse_extra.digits_lines({"calendar": {"past_unconfirmed_14d": out}}) if "Календарь" in x]
    assert line and "наш пропуск 0" in line[0] and "без отметки «вышло» 3" in line[0]
