"""SSR рейтинга региона: нули налога не «минимум»; в туристской теме нет театров и стадионов в «Ещё в разделе» (z5)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.services.seo_regional import _is_zero_none_series, _tourism_siblings


def _ind(name):
    return SimpleNamespace(name=name, code=name, name_en=None)


def test_zero_none_series_only_for_tax_codes():
    assert _is_zero_none_series("tour-nalog-za-god")
    assert _is_zero_none_series("tour-nalog-s-nachala-goda")
    assert _is_zero_none_series("tour-kurortnyy-sbor")
    assert not _is_zero_none_series("chislennost-naseleniya")


def test_tourism_siblings_use_the_same_list_as_api():
    from app.data.tourism_regional import SERIES_BY_CODE

    own = next(iter(SERIES_BY_CODE))
    def row(code, table):
        return SimpleNamespace(code=code, table_code=table, name=code)
    theatre = row("teatry", "6.4")
    hotels = row("gostinitsy", "6.1")
    rows = [theatre, hotels, row(own, "6.x")]
    ind = SimpleNamespace(code=own, table_code="6.x", section_num=6)
    kept = [x.code for x in _tourism_siblings(rows, ind, 10)]
    assert "teatry" not in kept and kept[0] == own
    other = SimpleNamespace(code="x", table_code="1.1", section_num=1)
    assert len(_tourism_siblings(rows, other, 10)) == 3


def test_rating_html_puts_zero_tax_out_of_minimum(auth_env):
    from app.services.seo_regional import render_region_rating_html
    from app.models import Region, RegionDataPoint, RegionIndicator
    code = "tour-nalog-za-god"

    async def seed():
        async with auth_env["session_maker"]() as db:
            regs = [Region(slug=f"r{i}", name=f"Регион {i}", kind="region", sort_order=i) for i in range(11)]
            regs.append(Region(slug="moskva", name="Москва", kind="region", sort_order=99))
            db.add_all(regs)
            await db.flush()
            ind = RegionIndicator(code=code, table_code="6.t60", section_num=6, section_name="Туризм",
                                  name="Туристический налог за год", unit="млн рублей", year_min=2025, year_max=2025, is_listed=True)
            db.add(ind)
            await db.flush()
            for i, r in enumerate(regs):
                db.add(RegionDataPoint(region_id=r.id, indicator_id=ind.id, year=2025, value=0 if r.slug == "moskva" else 10 + i))
            await db.commit()

    async def run():
        await seed()
        async with auth_env["session_maker"]() as db:
            return await render_region_rating_html(code, db)

    status, html = asyncio.run(run())
    assert status == 200
    assert "налог не введён или сбора не было" in html
    assert "Наименьшее значение — Москва" not in html and "Smallest value — Москва" not in html
    assert "12 " in html
