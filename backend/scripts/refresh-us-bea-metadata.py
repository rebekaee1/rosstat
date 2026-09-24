#!/usr/bin/env python3
"""Publish reviewed Russian BEA labels without replaying millions of observations.

The scheduled ZIP ingestion still checks source revisions independently. This
command only updates existing US rows and fails if the catalog and DB disagree.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.core.cache import bump_namespaces
from app.database import async_session
from app.models import SubnationalIndicator, WorldCountry, WorldIndicator
from app.services.world_bea_regional import load_catalog
from app.services.world_national_ingest import _seo_bundle


async def main() -> None:
    catalog = load_catalog()
    async with async_session() as db:
        country = (
            await db.execute(select(WorldCountry).where(WorldCountry.code == "US"))
        ).scalar_one()
        states = {
            row.code: row for row in (
                await db.execute(select(SubnationalIndicator).where(
                    SubnationalIndicator.country_code == "US",
                    SubnationalIndicator.provider == "bea-regional",
                ))
            ).scalars().all()
        }
        national = {
            row.code: row for row in (
                await db.execute(select(WorldIndicator).where(
                    WorldIndicator.country_id == country.id,
                    WorldIndicator.provider == "bea-regional",
                ))
            ).scalars().all()
        }
        missing_states = {spec.code for spec in catalog} - states.keys()
        missing_national = {spec.national_code for spec in catalog} - national.keys()
        if missing_states or missing_national:
            raise RuntimeError(
                f"Load BEA observations first: missing state={len(missing_states)}, "
                f"national={len(missing_national)}"
            )

        changed = 0
        for spec in catalog:
            state = states[spec.code]
            world = national[spec.national_code]
            updates = (
                (state, {
                    "name_ru": spec.name_ru,
                    "section_ru": spec.section_ru,
                    "description_ru": spec.description_ru,
                    "methodology_ru": spec.methodology_ru,
                }),
                (world, {
                    "name_ru": spec.name_ru,
                    "category_ru": spec.section_ru,
                    "description": spec.description_ru,
                    "methodology": spec.methodology_ru,
                }),
            )
            seo_title, seo_description, seo_keywords = _seo_bundle(
                name_ru=spec.name_ru,
                country_name_ru=country.name_ru,
                description=spec.description_ru,
            )
            updates[1][1].update({
                "seo_title": seo_title,
                "seo_description": seo_description,
                "seo_keywords": seo_keywords,
            })
            for row, fields in updates:
                for field, value in fields.items():
                    if getattr(row, field) != value:
                        setattr(row, field, value)
                        changed += 1
        await db.commit()
    await bump_namespaces("world", "ssr-world")
    print(f"US BEA Russian metadata: {len(catalog)} series, {changed} fields updated")


if __name__ == "__main__":
    asyncio.run(main())
