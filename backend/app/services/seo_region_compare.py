"""SSR-страницы сравнения двух регионов: /region-vs/{slugA}-vs-{slugB}.

Под спрос вида «зарплата москва или санкт-петербург», «сравнить регионы».
Пары — сочетания топ-регионов по численности населения (спрос концентрируется
на крупных субъектах). Канонический порядок пары — по алфавиту slug'ов;
обратный порядок отдаёт ту же страницу с canonical на упорядоченную пару.
"""

from __future__ import annotations

from html import escape

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Region, RegionDataPoint, RegionIndicator
from app.services.region_compare_data import build_region_compare_payload
from app.services.seo_regional import _fmt
from app.services.seo_renderer import DOMAIN, _breadcrumbs, build_document

_POPULATION_TABLE = "1.1"
TOP_REGIONS_LIMIT = 20


async def _top_region_slugs(db: AsyncSession) -> list[str]:
    pop_ind = (await db.execute(
        select(RegionIndicator).where(RegionIndicator.table_code == _POPULATION_TABLE)
    )).scalars().first()
    if pop_ind is None:
        return []
    last_year = (await db.execute(
        select(func.max(RegionDataPoint.year))
        .where(RegionDataPoint.indicator_id == pop_ind.id)
    )).scalar_one_or_none()
    if last_year is None:
        return []
    rows = (await db.execute(
        select(Region.slug)
        .join(RegionDataPoint, RegionDataPoint.region_id == Region.id)
        .where(RegionDataPoint.indicator_id == pop_ind.id,
               RegionDataPoint.year == last_year,
               Region.kind == "region")
        .order_by(RegionDataPoint.value.desc())
        .limit(TOP_REGIONS_LIMIT)
    )).scalars().all()
    return list(rows)


async def top_region_pairs(db: AsyncSession) -> list[tuple[str, str]]:
    slugs = await _top_region_slugs(db)
    pairs: list[tuple[str, str]] = []
    for i, a in enumerate(slugs):
        for b in slugs[i + 1:]:
            pairs.append(tuple(sorted((a, b))))
    return sorted(set(pairs))


async def render_region_vs_html(
    slug_a: str, slug_b: str, db: AsyncSession
) -> tuple[int, str]:
    payload = await build_region_compare_payload(slug_a, slug_b, db)
    if payload is None:
        if slug_a == slug_b:
            return 404, "<h1>Нужны два разных региона</h1>"
        return 404, "<h1>Регион не найден</h1>"

    region_a = payload["region_a"]
    region_b = payload["region_b"]
    canon_a = region_a["slug"]
    canon_b = region_b["slug"]
    canonical = payload["canonical_path"]

    def _vu(v: float, unit: str) -> str:
        return f"{_fmt(v)} {unit}".strip()

    sections = []
    table_rows = []
    for row in payload["rows"]:
        unit = row["unit"]
        va, vb = row["a"]["value"], row["b"]["value"]
        common_year = row["year"]
        ind_name = row["name"]
        ind_code = row["code"]
        verdict = row["verdict"]
        sections.append(
            f"<section class=\"seo-section\"><h2>{escape(ind_name)} ({common_year})</h2>"
            f"<p>{escape(region_a['name'])}: <strong>{escape(_vu(va, unit))}</strong> · "
            f"{escape(region_b['name'])}: <strong>{escape(_vu(vb, unit))}</strong>. "
            f"Показатель {escape(verdict)}.</p>"
            f"<p><a href=\"/region/{escape(canon_a)}/{escape(ind_code)}\">Динамика — {escape(region_a['name'])}</a> · "
            f"<a href=\"/region/{escape(canon_b)}/{escape(ind_code)}\">Динамика — {escape(region_b['name'])}</a> · "
            f"<a href=\"/region-rating/{escape(ind_code)}\">Рейтинг всех регионов</a></p></section>"
        )
        table_rows.append(
            f"<tr><td>{escape(ind_name)}</td><td>{common_year}</td>"
            f"<td>{escape(_vu(va, unit))}</td><td>{escape(_vu(vb, unit))}</td></tr>"
        )

    title = f"{region_a['name']} или {region_b['name']}: сравнение регионов — зарплата, население, цены"
    desc = (
        f"Сравнение регионов {region_a['name']} и {region_b['name']} по ключевым показателям "
        f"Росстата: {'; '.join(payload['summary_bits'][:3])}. Данные по годам, таблицы и графики."
    )

    compare_table = (
        f'<div class="seo-scroll"><table><thead><tr><th>Показатель</th><th>Год</th>'
        f"<th>{escape(region_a['name'])}</th><th>{escape(region_b['name'])}</th></tr></thead>"
        f"<tbody>{''.join(table_rows)}</tbody></table></div>"
    )

    og_path = f"/og/region-vs/{canon_a}-vs-{canon_b}.png"
    vs_alt = (f"Сравнение регионов {region_a['name']} и {region_b['name']}: "
              f"население, зарплата, ВРП, безработица — данные Росстата")
    figure_html = (
        f'<figure class="seo-chart"><img src="{escape(og_path)}" alt="{escape(vs_alt)}" '
        f'width="1200" height="630" loading="eager">'
        f"<figcaption>{escape(region_a['name'])} и {escape(region_b['name'])}: ключевые показатели. "
        f"Источник: Росстат. forecasteconomy.com</figcaption></figure>"
    )

    body = f"""<div class="seo-page">
<nav><a href="/">Главная</a> → <a href="/regions">Регионы</a> → {escape(region_a['name'])} vs {escape(region_b['name'])}</nav>
<p class="seo-eyebrow">Сравнение регионов России</p>
<h1>{escape(region_a['name'])} и {escape(region_b['name'])}: сравнение по ключевым показателям</h1>
<p>Официальные данные Росстата по двум субъектам РФ: население, заработная плата, безработица,
валовой региональный продукт, инвестиции, цены и доходы. По каждому показателю — значения за
последний доступный год и вывод, где значение выше.</p>
{figure_html}
<section class="seo-section"><h2>Сводная таблица</h2>{compare_table}</section>
{''.join(sections)}
<section class="seo-section"><h2>Профили регионов</h2>
<p>Все показатели каждого региона: <a href="/region/{escape(canon_a)}">{escape(region_a['name'])}</a> ·
<a href="/region/{escape(canon_b)}">{escape(region_b['name'])}</a>.
Интерактивное сравнение любых рядов — в разделе <a href="/compare">«Сравнение»</a>.</p></section>
</div>"""

    json_ld = [
        _breadcrumbs([
            ("/", "Главная"), ("/regions", "Регионы"),
            (canonical, f"{region_a['name']} vs {region_b['name']}"),
        ]),
        {
            "@context": "https://schema.org",
            "@type": "Dataset",
            "name": f"Сравнение регионов: {region_a['name']} и {region_b['name']}",
            "description": desc,
            "url": f"{DOMAIN}{canonical}",
            "inLanguage": "ru-RU",
            "creator": {"@type": "Organization", "name": "Росстат"},
            "spatialCoverage": f"{region_a['name']}; {region_b['name']}",
            "image": f"{DOMAIN}{og_path}",
        },
        {
            "@context": "https://schema.org",
            "@type": "ImageObject",
            "contentUrl": f"{DOMAIN}{og_path}",
            "url": f"{DOMAIN}{og_path}",
            "name": f"{region_a['name']} и {region_b['name']} — сравнение регионов",
            "description": vs_alt,
            "representativeOfPage": True,
            "width": 1200,
            "height": 630,
        },
    ]

    html = await build_document(
        title=title,
        description=desc,
        canonical_path=canonical,
        body=body,
        json_ld=json_ld,
        keywords=(
            f"{region_a['name']} или {region_b['name']}, сравнение {region_a['name']} {region_b['name']}, "
            f"{region_a['name']} {region_b['name']} зарплата, {region_a['name']} {region_b['name']} уровень жизни"
        ),
        og_image=f"{DOMAIN}{og_path}",
    )
    return 200, html
