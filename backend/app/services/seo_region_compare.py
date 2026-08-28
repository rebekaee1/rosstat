"""SSR-страницы сравнения двух регионов: /russia/region-vs/{slugA}-vs-{slugB}.

Под спрос вида «зарплата москва или санкт-петербург», «сравнить регионы».
Пары — сочетания топ-регионов по численности населения (спрос концентрируется
на крупных субъектах). Канонический порядок пары — по алфавиту slug'ов;
обратный порядок отдаёт ту же страницу с canonical на упорядоченную пару.
"""

from __future__ import annotations

from app.services import breadcrumbs as crumbs
from app.services import site_paths as paths

from html import escape

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Region, RegionDataPoint, RegionIndicator
from app.services.region_compare_data import build_region_compare_payload
from app.services.seo_i18n import regional_template
from app.services.seo_regional import _fmt
from app.services.seo_renderer import _absolute, _breadcrumbs, _breadcrumbs_nav, build_document

_POPULATION_TABLE = "1.1"
TOP_REGIONS_LIMIT = 20


def _rt(key: str, **kwargs) -> str | None:
    tpl = regional_template(key)
    if not tpl:
        return None
    return tpl.format(**kwargs) if kwargs else tpl


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
    dynamics_tpl = _rt("region_vs.section_dynamics")
    rating_link = _rt("region_vs.rating_link") or "Рейтинг всех регионов"
    for row in payload["rows"]:
        unit = row["unit"]
        va, vb = row["a"]["value"], row["b"]["value"]
        common_year = row["year"]
        ind_name = row["name"]
        ind_code = row["code"]
        verdict = row["verdict"]
        dyn_a = (
            dynamics_tpl.format(region=region_a["name"])
            if dynamics_tpl
            else f"Динамика — {region_a['name']}"
        )
        dyn_b = (
            dynamics_tpl.format(region=region_b["name"])
            if dynamics_tpl
            else f"Динамика — {region_b['name']}"
        )
        sections.append(
            f"<section class=\"seo-section\"><h2>{escape(ind_name)} ({common_year})</h2>"
            f"<p>{escape(region_a['name'])}: <strong>{escape(_vu(va, unit))}</strong>; "
            f"{escape(region_b['name'])}: <strong>{escape(_vu(vb, unit))}</strong>. "
            f"{escape(verdict) + '.' if dynamics_tpl else 'Показатель ' + escape(verdict) + '.'}</p>"
            f"<p><a href=\"{escape(paths.region_indicator(canon_a, ind_code))}\">{escape(dyn_a)}</a>, "
            f"<a href=\"{escape(paths.region_indicator(canon_b, ind_code))}\">{escape(dyn_b)}</a>, "
            f"<a href=\"{escape(paths.region_rating(ind_code))}\">{escape(rating_link)}</a></p></section>"
        )
        table_rows.append(
            f"<tr><td>{escape(ind_name)}</td><td>{common_year}</td>"
            f"<td>{escape(_vu(va, unit))}</td><td>{escape(_vu(vb, unit))}</td></tr>"
        )

    title = _rt(
        "region_vs.title",
        region_a=region_a["name"],
        region_b=region_b["name"],
    ) or (
        f"{region_a['name']} или {region_b['name']}: сравнение регионов — зарплата, население, цены"
    )
    desc = _rt(
        "region_vs.description",
        region_a=region_a["name"],
        region_b=region_b["name"],
    ) or (
        f"Сравнение регионов {region_a['name']} и {region_b['name']} по ключевым показателям "
        f"Росстата: {'; '.join(payload['summary_bits'][:3])}. Данные по годам, таблицы и графики."
    )
    h1 = _rt(
        "region_vs.h1",
        region_a=region_a["name"],
        region_b=region_b["name"],
    ) or (
        f"{region_a['name']} и {region_b['name']}: сравнение по ключевым показателям"
    )

    th_ind = _rt("region_vs.th_indicator") or "Показатель"
    th_year = _rt("region_vs.th_year") or "Год"
    compare_table = (
        f'<div class="seo-scroll"><table><thead><tr><th>{escape(th_ind)}</th><th>{escape(th_year)}</th>'
        f"<th>{escape(region_a['name'])}</th><th>{escape(region_b['name'])}</th></tr></thead>"
        f"<tbody>{''.join(table_rows)}</tbody></table></div>"
    )

    og_path = paths.og_region_vs(canon_a, canon_b)
    vs_alt = _rt(
        "region_vs.alt",
        region_a=region_a["name"],
        region_b=region_b["name"],
    ) or (
        f"Сравнение регионов {region_a['name']} и {region_b['name']}: "
        f"население, зарплата, ВРП, безработица — данные Росстата"
    )
    caption = _rt(
        "region_vs.caption",
        region_a=region_a["name"],
        region_b=region_b["name"],
    ) or (
        f"{region_a['name']} и {region_b['name']}: ключевые показатели. "
        f"Источник: Росстат. forecasteconomy.com"
    )
    figure_html = (
        f'<figure class="seo-chart"><a class="seo-chart-link" '
        f'href="{escape(paths.region_vs(canon_a, canon_b))}#chart">'
        f'<img src="{escape(og_path)}" alt="{escape(vs_alt)}" '
        f'width="1200" height="630" loading="eager"></a>'
        f"<figcaption>{escape(caption)}</figcaption></figure>"
    )

    vs_label = f"{region_a['name']} vs {region_b['name']}"
    vs_trail = crumbs.region_vs_trail(vs_label, canonical)
    eyebrow = _rt("region_vs.eyebrow") or "Сравнение регионов России"
    intro = _rt("region_vs.intro") or (
        "Официальные данные Росстата по двум субъектам РФ: население, заработная плата, безработица, "
        "валовой региональный продукт, инвестиции, цены и доходы. По каждому показателю — значения за "
        "последний доступный год и вывод, где значение выше."
    )
    table_h2 = _rt("region_vs.table_h2") or "Сводная таблица"
    profiles_h2 = _rt("region_vs.profiles_h2") or "Профили регионов"
    profiles_p = _rt(
        "region_vs.profiles_p",
        href_a=escape(paths.region(canon_a)),
        href_b=escape(paths.region(canon_b)),
        region_a=escape(region_a["name"]),
        region_b=escape(region_b["name"]),
    ) or (
        f'Все показатели каждого региона: <a href="{escape(paths.region(canon_a))}">{escape(region_a["name"])}</a>, '
        f'<a href="{escape(paths.region(canon_b))}">{escape(region_b["name"])}</a>. '
        f'Интерактивное сравнение любых рядов — в разделе <a href="/compare">«Сравнение»</a>.'
    )
    body = f"""<div class="seo-page">
{_breadcrumbs_nav(vs_trail)}
<p class="seo-eyebrow">{escape(eyebrow)}</p>
<h1>{escape(h1)}</h1>
<p>{escape(intro)}</p>
{figure_html}
<section class="seo-section"><h2>{escape(table_h2)}</h2>{compare_table}</section>
{''.join(sections)}
<section class="seo-section"><h2>{escape(profiles_h2)}</h2>
<p>{profiles_p}</p></section>
</div>"""

    from app.services.locale import in_language

    json_ld = [
        _breadcrumbs(vs_trail),
        {
            "@context": "https://schema.org",
            "@type": "Dataset",
            "name": _rt(
                "region_vs.jsonld_name",
                region_a=region_a["name"],
                region_b=region_b["name"],
            ) or f"Сравнение регионов: {region_a['name']} и {region_b['name']}",
            "description": desc,
            "url": _absolute(canonical),
            "inLanguage": in_language(),
            "creator": {
                "@type": "Organization",
                "name": "Rosstat" if _rt("region_vs.intro") else "Росстат",
            },
            "spatialCoverage": f"{region_a['name']}; {region_b['name']}",
            "image": _absolute(og_path),
        },
        {
            "@context": "https://schema.org",
            "@type": "ImageObject",
            "contentUrl": _absolute(og_path),
            "url": _absolute(og_path),
            "name": _rt(
                "region_vs.image_name",
                region_a=region_a["name"],
                region_b=region_b["name"],
            ) or f"{region_a['name']} и {region_b['name']} — сравнение регионов",
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
        keywords=_rt(
            "region_vs.keywords",
            region_a=region_a["name"],
            region_b=region_b["name"],
        ) or (
            f"{region_a['name']} или {region_b['name']}, сравнение {region_a['name']} {region_b['name']}, "
            f"{region_a['name']} {region_b['name']} зарплата, {region_a['name']} {region_b['name']} уровень жизни"
        ),
        og_image=_absolute(og_path),
    )
    return 200, html
