"""Зарплата, пенсия и рождаемость по регионам помесячно (ЕМИСС 57824, 61699, 61698, 62852; 19.11.2026).

Фикстуры — живые ответы dataGrid.do 19.11.2026, урезанные до строк России и нескольких субъектов.
"""

import asyncio
import json
from pathlib import Path

import pytest

from app.data import emiss_regional_social as reg
from app.services import emiss_regional_social as mod

FIX = Path(__file__).parent / "fixtures" / "emiss_regional_social"


def _parse(name: str, dataset: int):
    payload = json.loads((FIX / name).read_text(encoding="utf-8"))
    points, stats = mod.parse_payload(payload, reg.DATASETS[dataset], mod.territory_slugs())
    return {(slug, period): value for slug, period, value in points}, stats


def test_wages_russia_switches_to_row_without_new_subjects_in_2023():
    points, stats = _parse("dataGrid_57824_vsego_2026-11-19.json", 57824)
    assert stats == {"rejected": 0, "unknown_territories": 0}
    assert points[("russia", 202212)] == 88468.3          # «Российская Федерация»
    assert points[("russia", 202301)] == 63260.3          # «без учёта новых субъектов»
    assert max(p for s, p in points if s == "russia") == 202607   # август 2026 по России ещё не опубликован
    # С 2026 года край идёт строкой «с учётом ФТ «Сириус»» — продолжение того же ряда.
    assert points[("krasnodarskiy-kray", 202601)] > 50_000
    assert points[("krasnodarskiy-kray", 202512)] > 50_000
    assert ("moskva", 202608) in points
    # Строки «январь–…» (нарастающим итогом) в месячный ряд не попадают: у месяца ровно одно значение.
    assert points[("moskva", 201712)] == 104052.0


def test_pension_on_first_day_and_aliases_of_social_fund_names():
    points, stats = _parse("dataGrid_61699_vse_2026-11-19.json", 61699)
    assert stats["unknown_territories"] == 0
    assert points[("russia", 202609)] == 25469.39          # на 1 сентября 2026
    assert points[("russia", 202601)] == 25254.53
    assert ("moskva", 202609) in points                    # «г. Москва » с пробелом
    assert ("arhangelskaya-oblast-bez-ao", 202609) in points


def test_pensioner_count_is_in_thousands():
    points, _stats = _parse("dataGrid_61698_vse_2026-11-19.json", 61698)
    assert points[("russia", 202609)] == pytest.approx(40519.308)


def test_fertility_monthly_without_annual_value():
    points, stats = _parse("dataGrid_62852_2026-11-19.json", 62852)
    assert stats["unknown_territories"] == 0
    assert points[("russia", 202609)] == 1.336
    assert len([p for s, p in points if s == "russia" and p // 100 == 2025]) == 12   # «за год» не взят
    assert ("arhangelskaya-oblast-bez-ao", 202609) in points


def test_out_of_range_cell_is_skipped_not_fatal():
    payload = {"results": [
        {"dim57831": "Тамбовская область", "dim3": "2026", "dim1540283_d1_i1": "1,2", "dim1540282_d1_i2": "77,7"},
    ]}
    points, stats = mod.parse_payload(payload, reg.DATASETS[62852], mod.territory_slugs())
    assert points == [("tambovskaya-oblast", 202601, 1.2)]
    assert stats["rejected"] == 1


def test_unknown_territory_counted_and_empty_parse_is_format_error():
    payload = {"results": [{"dim57831": "Неизвестный край", "dim3": "2026", "dim1540283_d1_i1": "1,2"}]}
    with pytest.raises(mod.EmissFormatError):
        mod.parse_payload(payload, reg.DATASETS[62852], mod.territory_slugs())


def test_request_lists_territories_member_and_monthly_periods_only():
    series = reg.SERIES_BY_CODE["zarplata-mesyachnaya-obrazovanie"]
    params = mod.build_params(reg.DATASETS[57824], series, ["1688487", "1849012"], range(2025, 2027))
    filters = [v for k, v in params if k == "selectedFilterIds"]
    assert ("lineObjectIds", "57940") in params and ("columnObjectIds", "33560") in params
    assert "57940_1692330" in filters and "57831_1849012" in filters and "3_2026" in filters
    assert "33560_1540294" not in filters                  # «январь–февраль»
    assert len([f for f in filters if f.startswith("33560_")]) == 12


def test_territory_lists_cover_every_dataset():
    territories = mod.load_territories()
    assert {int(k) for k in territories} == set(reg.DATASETS)
    assert all(len(v) >= 96 for v in territories.values())


def test_indicators_json_and_english_copy_cover_registry():
    from app.data.i18n.region_indicators_en import REGION_INDICATORS_EN

    rows = json.loads((Path(mod.__file__).parents[1] / "data" / "regional" / "indicators.json").read_text("utf-8"))
    by_code = {r["code"]: r for r in rows}
    assert len(reg.SERIES) == 27
    for series in reg.SERIES:
        row = by_code[series.code]
        assert row["frequency"] == "monthly" and row["name"] == series.name and len(row["table_code"]) <= 20
        assert REGION_INDICATORS_EN[series.code]["name"] == series.name_en
    assert len({s.table_code for s in reg.SERIES}) == len(reg.SERIES)


def test_run_update_first_load_then_incremental(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.models import Base, Region, RegionIndicator, RegionMonthlyPoint

    db_path = tmp_path / "social.db"
    sync_engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(sync_engine)
    sync_engine.dispose()

    requests: list[tuple[int, list[str]]] = []
    written: list[tuple] = []

    async def fake_post_grid(dataset_id, params):
        requests.append((dataset_id, [v for k, v in params if k == "selectedFilterIds" and v.startswith("3_")]))
        return {"results": [{"dim57831": "Тамбовская область", "dim30628": "Тамбовская область",
                             "dim3": "2026", "dim1540283_d1_i1": "5000", "dim1594468_d1_i1": "5000"}]}

    async def fake_upsert(db, values):
        fresh = [v for v in values if v not in written]
        written.extend(fresh)
        db.add_all(RegionMonthlyPoint(indicator_id=i, region_id=r, month=m, value=v) for i, r, m, v in fresh)
        await db.flush()
        return len(fresh), 0

    async def no_publish():
        return None

    monkeypatch.setattr(mod, "_upsert_monthly_points", fake_upsert)
    monkeypatch.setattr(mod, "publish_committed_regional_changes", no_publish)
    monkeypatch.setattr(mod, "_PAUSE_BETWEEN_REQUESTS", 0)
    series = reg.SERIES_BY_CODE["zarplata-mesyachnaya"]
    monkeypatch.setattr(mod, "SERIES", (series,))

    async def scenario():
        engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        maker = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with maker() as db:
                db.add(Region(slug="tambovskaya-oblast", name="Тамбовская область", kind="region"))
                db.add(RegionIndicator(code=series.code, table_code=series.table_code, section_num=3,
                                       section_name=series.section_name, name=series.name))
                await db.commit()
                first = await mod.run_emiss_social_update(db, post_grid=fake_post_grid)
                second = await mod.run_emiss_social_update(db, post_grid=fake_post_grid)
                return first, second
        finally:
            await engine.dispose()

    first, second = asyncio.run(scenario())
    assert first["series"] == 1 and first["added"] == 1 and second["added"] == 0
    assert requests[0][1][0] == "3_2017"                     # пустая база — вся история
    assert requests[1][1][0] == "3_2025"                     # дальше — год последней точки и предыдущий
    assert written[0][2:] == (202601, 5000.0)


GEOMETRY = [
    dict(key="country:russia", kind="country", slug="russia", country_slug="russia", country_code="RU",
         name_ru="Россия", name_en="Russia"),
    dict(key="region:russia:omskaya-oblast", kind="region", slug="omskaya-oblast", country_slug="russia",
         name_ru="Омская область", name_en="Omsk Oblast"),
]


@pytest.mark.parametrize("query,needle", [
    ("зарплата учителей омская область", "по месяцам: образование"),
    ("зарплата врачей", "по месяцам: здравоохранение"),
    ("средняя пенсия омская область", "средняя пенсия"),
    ("суммарный коэффициент рождаемости омская область", "суммарный коэффициент"),
])
def test_search_reaches_monthly_series(query, needle):
    from app.services.search_intent import normalize, parse_intent

    intent = parse_intent(query, GEOMETRY)
    assert any(needle in group for group in intent.terms), intent.terms
    names = [normalize(s.name) for s in reg.SERIES]
    assert any(needle in name for name in names)


@pytest.mark.parametrize("query,expected", [("зарплата", "зарплат"), ("численность врачей", "врачей")])
def test_search_general_words_unchanged(query, expected):
    from app.services.search_intent import parse_intent

    intent = parse_intent(query, GEOMETRY)
    assert any(expected in group for group in intent.terms)
    assert not any("по месяцам" in needle for group in intent.terms for needle in group)


def _render_social(locale):
    from app.models import Region, RegionIndicator, RegionMonthlyPoint
    from app.services.locale import reset_locale, set_locale
    from app.services.seo_regional import _render_region_indicator_monthly
    from tests.test_analytics2 import _run_with_db

    series = reg.SERIES_BY_CODE["pensiya-srednyaya-mesyachnaya"]

    async def scenario(maker):
        async with maker() as db:
            rf = Region(slug="russia", name="Российская Федерация", kind="country")
            ind = RegionIndicator(code=series.code, table_code=series.table_code, section_num=3,
                                  section_name=series.section_name, name=series.name, unit=series.unit)
            db.add_all([rf, ind])
            await db.flush()
            values = {202509: 23520.08, 202608: 25469.0, 202609: 25469.39}
            db.add_all([RegionMonthlyPoint(indicator_id=ind.id, region_id=rf.id, month=m, value=v)
                        for m, v in values.items()])
            await db.commit()
            token = set_locale(locale)
            try:
                return await _render_region_indicator_monthly("russia", ind.code, rf, ind, sorted(values.items()), db)
            finally:
                reset_locale(token)

    return _run_with_db(scenario)


@pytest.mark.parametrize("locale,banned,expected", [
    ("ru", ("потребительские цены", "Какая цена", "среднероссийской ценой"), "Социального фонда"),
    ("en", ("consumer price", "в регионе", "Росстата"), "Social Fund of Russia"),
])
def test_ssr_card_of_social_series_has_no_price_wording(locale, banned, expected):
    status, html = _render_social(locale)
    assert status == 200
    body = html.split("<body", 1)[-1]
    for phrase in banned:
        assert phrase not in body, phrase
    assert expected in body
