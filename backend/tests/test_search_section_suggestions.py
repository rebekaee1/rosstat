"""«Попробуйте, например» по разделу Росстата и региону (14.11.2026)."""
from app.models import Region, RegionDataPoint, RegionIndicator
from app.services.search_regional_groups import _table_closeness, section_suggestions

from tests.test_analytics2 import _run_with_db


def test_table_closeness():
    assert _table_closeness("13.21", "13.21") == 2
    assert _table_closeness("13.21", "13.4") == 1
    assert _table_closeness("13.21", "4.1") == 0


def _ind(code, name, table, section="Сельское хозяйство"):
    return RegionIndicator(code=code, name=name, table_code=table, section_num=13, section_name=section, unit="")


def test_neighbours_same_table_first_fresh_nonzero_only():
    async def scenario(maker):
        async with maker() as db:
            voronezh = Region(slug="voronezhskaya-oblast", name="Воронежская область", kind="region")
            inds = {
                "potato": _ind("posevnye-ploschadi-kartofelya", "Посевные площади картофеля", "13.21"),
                "veg": _ind("posevnye-ploschadi-ovoschey", "Посевные площади овощей", "13.21"),
                "flax": _ind("posevnye-ploschadi-lna", "Посевные площади льна", "13.21"),
                "old": _ind("posevnye-ploschadi-staroe", "Посевные площади ржи", "13.21"),
                "harvest": _ind("valovoy-sbor-kartofelya", "Валовой сбор картофеля", "13.22"),
                "forest": _ind("lesnye-resursy", "Лесные ресурсы", "13.36"),
                "price": _ind("ceni-moloko", "Средняя цена: молоко", "4.1", section="Цены и тарифы"),
                "empty": _ind("posevnye-ploschadi-pusto", "Посевные площади проса", "13.21"),
            }
            db.add_all([voronezh, *inds.values()])
            await db.flush()
            for key, year, value in (("potato", 2024, 26.9), ("veg", 2024, 15.6), ("flax", 2010, 0.0),
                                     ("old", 2015, 3.0), ("harvest", 2024, 500.0), ("forest", 2024, 10.0),
                                     ("price", 2024, 90.0)):
                db.add(RegionDataPoint(indicator_id=inds[key].id, region_id=voronezh.id, year=year, value=value))
            await db.commit()
        item = {"kind": "region_indicator", "code": "posevnye-ploschadi-kartofelya", "region_slug": "voronezhskaya-oblast",
                "region_name": "Воронежская область", "latest": {"value": 26.9, "date": "2024-01-01"}}
        async with maker() as db:
            ru = await section_suggestions(db, item, set(), "ru")
            short = await section_suggestions(db, item, set(), "ru", region_in_query=True)
            shown = await section_suggestions(db, item, {"posevnye-ploschadi-ovoschey"}, "ru")
            russia = await section_suggestions(db, {**item, "region_slug": "russia"}, set(), "ru")
        return ru, short, shown, russia

    ru, short, shown, russia = _run_with_db(scenario)
    # Та же таблица первой; лён (0, 2010), рожь (2015) и ряд без данных отсеяны; цены из другого раздела не идут.
    queries = ["Посевные площади овощей Воронежская область", "Валовой сбор картофеля Воронежская область",
               "Лесные ресурсы Воронежская область"]
    assert [s["query"] for s in ru] == queries and [s["label"] for s in ru] == queries
    # Регион уже в запросе: подпись короткая, действие — полный запрос с регионом.
    assert [s["label"] for s in short] == ["Посевные площади овощей", "Валовой сбор картофеля", "Лесные ресурсы"]
    assert [s["query"] for s in short] == queries
    assert queries[0] not in [s["query"] for s in shown]  # уже показан в «Ближайшем»
    assert russia == []  # строка-группа «Россия» подсказок не даёт
