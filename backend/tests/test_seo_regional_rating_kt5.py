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
    assert not _is_zero_none_series("chislennost-naseleniya")


def test_tourism_siblings_drop_theatres_and_stadiums_only_in_tourism_section(monkeypatch):
    monkeypatch.setattr("app.services.seo_regional._icopy", lambda i: {"name": i.name})
    rows = [_ind("Число театров"), _ind("Гости гостиниц"), _ind("Число стадионов"), _ind("Библиотеки"), _ind("Число бассейнов")]
    kept = [x.name for x in _tourism_siblings(rows, 6, 10)]
    assert kept == ["Гости гостиниц"]
    assert len(_tourism_siblings(rows, 1, 10)) == 5
    assert len(_tourism_siblings(rows, 6, 10)) == 1


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
