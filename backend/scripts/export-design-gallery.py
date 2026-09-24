#!/usr/bin/env python3
"""Export real OG variants for local review, without sending crawl submissions.

Run inside the local backend container after build:
  python /app/scripts/export-design-gallery.py --out /tmp/design-review-cards
All observations come from the local database; the existing HTTP handlers and
Pillow renderers are invoked directly, sequentially, with a read-only DB session.
This exports review files, not millions of per-URL production assets.
"""
import argparse
import asyncio
import hashlib
import inspect
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone
sys.path.insert(0, os.environ.get('PYTHONPATH_ROOT', '/app'))

from sqlalchemy import select, func, text
from app.database import async_session
from app.models import Region, RegionIndicator, RegionDataPoint, WorldCountry, WorldIndicator, WorldDataPoint
from app.api.sitemap import router
from app.services.locale import set_locale, reset_locale
from app.services.og_image import quicklink_art_theme
from app.services.seo_i18n import region_indicator_copy

BASE = [
 ('inflation', 'Инфляция за год', 'finance', '/russia/indicator/cpi/2025', '/api/v1/og-image/indicator/cpi/2025.png'),
 ('policy', 'Ключевая ставка', 'finance', '/russia/indicator/key-rate', '/api/v1/og-image/indicator/key-rate.png'),
 ('housing', 'Стоимость жилья', 'housing', '/russia/indicator/housing-price-primary/2024', '/api/v1/og-image/indicator/housing-price-primary/2024.png'),
 ('industry', 'Промышленное производство', 'industry', '/russia/indicator/ipi', '/api/v1/og-image/indicator/ipi.png'),
 ('commodity', 'Нефть Brent', 'commodity', '/russia/indicator/brent', '/api/v1/og-image/indicator/brent.png'),
 ('population-history', 'История населения: 1897', 'population', '/russia/indicator/population/1897', '/api/v1/og-image/indicator/population/1897.png'),
 ('germany-year', 'Экономика Германии: 2024', 'industry', '/germany/indicator/de-weo-ngdpd/2024', '/api/v1/og-image/world/germany/de-weo-ngdpd/2024.png'),
 ('us-employment', 'Занятость в США', 'population', '/united-states/indicator/us-nonfarm-payrolls', '/api/v1/og-image/world/united-states/us-nonfarm-payrolls.png'),
 ('california', 'Безработица в Калифорнии', 'population', '/united-states/region/california/unemployment-rate', '/api/v1/og-image/world-region/united-states/california/unemployment-rate.png'),
 ('california-housing', 'Жильё в Калифорнии', 'housing', '/united-states/region/california/house-price-index', '/api/v1/og-image/world-region/united-states/california/house-price-index.png'),
 ('rating', 'Рейтинг стран по ВВП: 2024', 'industry', '/world/rating/gdp-usd/2024', '/api/v1/og-image/world-rating/gdp-usd/2024.png'),
 ('comparison', 'Франция и Германия', 'industry', '/france-vs-germany/gdp-usd', '/api/v1/og-image/world-vs/france-vs-germany/gdp-usd.png'),
 ('region-comparison', 'Москва и Тульская область', 'population', '/russia/region-vs/moskva-vs-tulskaya-oblast', '/api/v1/og-image/region-vs/moskva-vs-tulskaya-oblast.png'),
 ('today', 'Экономика России сегодня', 'finance', '/russia/today', '/api/v1/og-image/today.png'),
 ('us-country', 'Экономика США', 'industry', '/united-states', '/api/v1/og-image/world/united-states.png'),
 ('us-states', 'Сравнение штатов США', 'population', '/united-states/regions', '/api/v1/og-image/world-regions/united-states.png'),
 ('us-state-profile', 'Профиль Калифорнии', 'industry', '/united-states/region/california', '/api/v1/og-image/world-region/united-states/california.png'),
 ('demographics', 'Возрастная структура населения', 'population', '/russia/demographics', '/api/v1/og-image/demographics.png'),
]

# Review labels use the same language as the rendered PNG. These names only
# describe the fixed editorial samples; data and image copy remain in OG handlers.
TITLE_EN = {
    'inflation': 'Consumer Price Index: 2025',
    'policy': 'Bank of Russia key rate',
    'housing': 'Primary housing prices',
    'industry': 'Industrial production',
    'commodity': 'Brent oil',
    'population-history': 'Population history: 1897',
    'germany-year': 'Germany: 2024',
    'us-employment': 'U.S. employment',
    'california': 'Unemployment in California',
    'california-housing': 'Housing in California',
    'rating': 'GDP ranking by country: 2024',
    'comparison': 'France and Germany',
    'region-comparison': 'Moscow and Tula Oblast',
    'today': "Russia's economy today",
    'us-country': 'U.S. economy',
    'us-states': 'U.S. state comparison',
    'us-state-profile': 'California profile',
    'demographics': 'Age structure of the population',
}

async def invoke(path, db, portrait):
    for route in router.routes:
        match = route.path_regex.fullmatch(path)
        if not match:
            continue
        params = match.groupdict()
        signature = inspect.signature(route.endpoint)
        for key, value in params.items():
            if signature.parameters[key].annotation in (int, 'int'):
                params[key] = int(value)
        params['db'] = db
        if 'portrait' not in signature.parameters:
            raise ValueError(f'{path} has no portrait renderer')
        params['portrait'] = portrait
        response = await route.endpoint(**params)
        if response.status_code != 200 or not response.body.startswith(b'\x89PNG'):
            raise ValueError(f'{path}: HTTP {response.status_code}')
        return response.body
    raise ValueError(f'No OG route: {path}')

async def main(out):
    out.mkdir(parents=True, exist_ok=True)
    entries, errors = [], []
    async with async_session() as db:
        await db.execute(text('SET TRANSACTION READ ONLY'))
        await db.execute(text("SET LOCAL statement_timeout='60s'"))
        regional = (await db.execute(select(RegionIndicator.code, RegionIndicator.name)
            .join(RegionDataPoint, RegionDataPoint.indicator_id == RegionIndicator.id)
            .join(Region, Region.id == RegionDataPoint.region_id)
            .where(Region.slug == 'moskva', RegionIndicator.is_listed.is_(True))
            .group_by(RegionIndicator.id).having(func.count() >= 3))).all()
        cases = list(BASE)
        if regional:
            longest = max(regional, key=lambda row: len(row.name))
            cases.append(('regional-long-title', longest.name + ' — Москва',
                          quicklink_art_theme(longest.code + ' ' + longest.name),
                          f'/russia/region/moskva/{longest.code}',
                          f'/api/v1/og-image/region/moskva/{longest.code}.png'))
            TITLE_EN['regional-long-title'] = (
                region_indicator_copy(longest.code, name_ru=longest.name, unit_ru='', locale='en')['name']
                + ' — Moscow'
            )
        longest_world = (await db.execute(select(WorldCountry.slug, WorldIndicator.code,
                                                WorldIndicator.name_ru, WorldIndicator.name_en)
            .join(WorldIndicator, WorldIndicator.country_id == WorldCountry.id)
            .where(WorldCountry.is_active.is_(True), WorldIndicator.is_listed.is_(True),
                   select(WorldDataPoint.id).where(WorldDataPoint.indicator_id == WorldIndicator.id).exists())
            .order_by(func.length(WorldIndicator.name_ru).desc(), WorldIndicator.code).limit(1))).first()
        if longest_world:
            slug, code, name, name_en = longest_world
            cases.append(('world-long-title', name, quicklink_art_theme(code + ' ' + name),
                          f'/{slug}/indicator/{code}', f'/api/v1/og-image/world/{slug}/{code}.png'))
            TITLE_EN['world-long-title'] = name_en or name
        wanted = {'health','education','science','agriculture','tourism','environment','energy','transport','ict','trade','justice'}
        for code, name in sorted(regional, key=lambda r: (len(r.name), r.code)):
            theme = quicklink_art_theme(code + ' ' + name)
            if theme not in wanted:
                continue
            wanted.remove(theme)
            id_ = f'regional-{theme}'
            cases.append((id_, name + ' — Москва', theme,
                          f'/russia/region/moskva/{code}', f'/api/v1/og-image/region/moskva/{code}.png'))
            TITLE_EN[id_] = (
                region_indicator_copy(code, name_ru=name, unit_ru='', locale='en')['name']
                + ' — Moscow'
            )
        for id_, title, theme, path, api in cases:
            for locale in ('ru','en'):
                token = set_locale(locale)
                try:
                    for portrait in (False, True):
                        fmt = 'portrait' if portrait else 'wide'
                        name = f'{id_}-{locale}-{fmt}.png'
                        try:
                            png = await invoke(api, db, portrait)
                            (out/name).write_bytes(png)
                            entries.append(dict(id=id_, title=title if locale == 'ru' else TITLE_EN.get(id_, title),
                                                theme=theme, locale=locale, format=fmt,
                                                file=name, path=path, bytes=len(png), sha256=hashlib.sha256(png).hexdigest()))
                        except Exception as error:
                            errors.append({'id': id_, 'locale': locale, 'format': fmt, 'error': str(error)})
                finally:
                    reset_locale(token)
        await db.rollback()
    manifest = {'generatedAt': datetime.now(timezone.utc).isoformat(),
                'source': 'Local observed data through the production OG handlers; no invented figures',
                'entries': entries, 'errors': errors, 'unrepresentedThemes': sorted(wanted)}
    (out/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'cards':len(entries),'families':len({e['id'] for e in entries}),
                      'themes':sorted({e['theme'] for e in entries}), 'errors':errors, 'missingThemes':sorted(wanted)}, ensure_ascii=False))
    if errors:
        raise SystemExit(1)

if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    asyncio.run(main(parser.parse_args().out))
