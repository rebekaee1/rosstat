"""Поля данных туризма по регионам для API регионов (круг наблюдателей 20.11.2026; отрисовка — у страниц).

- ``source`` в карточке показателя: подпись, адрес конкретной публикации или набора ЕМИСС, «что важно знать»,
  методика региона (для оценки турпотока регионов), признаки ``calculated``/``approximate``/``ranked``;
- статусы нулей туристического налога и курортного сбора в рейтинге (``status`` у значения, у пропуска):
  ``not_introduced`` — налог не введён (подтверждённые случаи); ``zero_year`` — в отчёте за год поступлений нет;
  ``no_receipts_yet`` — в этом месяце платежа ещё не было (налог платят раз в квартал); ``no_data`` — строки нет.
  Для нуля и от нуля изменение («−100 %») не отдаётся: поле ``prev`` у таких значений не заполняется.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.tourism_regional import NOT_RANKED, SERIES_BY_CODE, TAX_NOT_INTRODUCED, ZERO_NOT_CHANGE, api_source


def source_field(code: str, slug: str | None, locale: str) -> dict:
    src = api_source(code, slug, locale)
    return {"source": src} if src else {}


def ranked_field(code: str) -> dict:
    return {"ranked": code not in NOT_RANKED} if code in SERIES_BY_CODE else {}


async def zero_statuses(
    db: AsyncSession, code: str, indicator_id: int, layer: str, period: int, values: list[dict],
    missing: list[dict] | None = None,
) -> None:
    """Проставляет ``status`` нулям и пропускам ряда налога/сбора; убирает ``prev``, если одно из чисел — ноль."""
    if code not in ZERO_NOT_CHANGE:
        return
    from app.models import Region, RegionMonthlyPoint

    year = period // 100 if layer == "monthly" else period
    paid: set[str] = set()
    if layer == "monthly":
        paid = set((await db.execute(
            select(Region.slug).join(RegionMonthlyPoint, RegionMonthlyPoint.region_id == Region.id)
            .where(RegionMonthlyPoint.indicator_id == indicator_id, RegionMonthlyPoint.value != 0,
                   RegionMonthlyPoint.month >= year * 100, RegionMonthlyPoint.month <= period)
            .distinct()
        )).scalars().all())
    for v in values:
        raw, prev = v.get("raw"), v.get("prev")
        if raw == 0:
            slug = v.get("slug")
            if year in TAX_NOT_INTRODUCED.get(slug, ()):
                v["status"] = "not_introduced"
            elif layer == "monthly" and slug in paid:
                v["status"] = "no_receipts_yet"
            else:
                v["status"] = "zero_year"
            v.pop("prev", None)
        elif prev == 0:
            v.pop("prev", None)
    for m in missing or []:
        m["status"] = "not_introduced" if year in TAX_NOT_INTRODUCED.get(m.get("slug"), ()) else "no_data"
