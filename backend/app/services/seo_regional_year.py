"""SSR-рендер годовых лендингов регионов: /russia/region/{slug}/{code}/{year}.

Программатик-страницы под спрос вида «население Москвы 2024», «зарплата
в Татарстане по годам 2019»: значение выбранного года, изменение к прошлому
доступному году, МЕСТО РЕГИОНА ИМЕННО ЗА ЭТОТ ГОД (главное отличие от карточки,
которая ранжирует по последнему году), сравнение со средним по России,
динамика соседних лет и ссылка на живую карточку.

Слои в ответственности модуля: только рендер. Роуты в API, OG-картинки
(/og/russia/region/{slug}/{code}/{year}.png) и sitemap-секция подключаются
отдельными правками (см. docs/backlog.md).

Тексты — публичный язык (методология без жаргона), русская типографика,
без mid-dot. EN-локаль: тело страницы полностью покрывается локальным
словарём _YEAR_TEMPLATES_EN (отсутствующий ключ → русский fallback в месте
использования); имена региона/показателя — из общих EN-каталогов (regions_en,
region_indicators_en), ранг-фразы — из REGIONAL_TEMPLATES_EN через
`_rank_phrase`, источник — translate_source(); числа — display-форматтер
(format_number_ru) с EN-типографикой. Общий seo_en.py не трогается.
"""

from __future__ import annotations

from datetime import date
from html import escape

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.region_indicator_polarity import (
    region_rating_is_achievement,
    region_rating_order_by,
)
from app.models import Region, RegionDataPoint, RegionIndicator
from app.services import breadcrumbs as crumbs
from app.services import site_paths as paths
from app.services.display import format_number_ru
from app.services.index_policy import regional_year_min
from app.services.locale import get_locale
from app.services.seo_i18n import (
    region_display_name,
    region_indicator_copy,
    translate_source,
)
from app.services.seo_regional import (
    _fmt,
    _icopy,
    _pct,
    _rank_phrase,
    _region,
    _rt,
)
from app.services.seo_renderer import (
    _absolute,
    _breadcrumbs,
    _breadcrumbs_nav,
    _link,
    _links_list,
    _seo_chart_figure,
    _site_json_ld,
    build_document,
    neighbor_year_window,
)

_ALLOWED_REGION_KINDS = ("region", "district", "country")

# Сколько последних лет показывать ссылками «Другие годы».
_OTHER_YEARS_LIMIT = 15
# Начиная с такой длины ряда страница получает контрольные годы каждые пять лет
# и точную таблицу последнего десятилетия вместо одной полной таблицы.
_LONG_SERIES_THRESHOLD = 16

# EN-ключи только этого рендера (общий словарь seo_en.py — чужая зона
# владения). Отсутствующий ключ → русский fallback в месте использования.
_YEAR_TEMPLATES_EN = {
    "h1": "{indicator} in {region}, {year}: value and dynamics",
    "alt": (
        "{indicator} in {region}, {year}: value {value}{unit}, "
        "place among Russian regions, source {source}"
    ),
    "caption": "{indicator} in {region}, {year}. Source: {source}.",
    "desc_main": "{indicator} in {region} in {year}: {value}{unit}.",
    "change_vs": "Change versus {prev_year}: {abs}{unit}.",
    "change_vs_pct": "Change versus {prev_year}: {abs}{unit} (indicator {pct}).",
    "rf_h2": "Comparison with the Russian average",
    "rf_para": "The Russian average in {year} was {value}{unit}.",
    "rf_above": " The region's value is above the national average.",
    "rf_below": " The region's value is below the national average.",
    "rf_level": " The region's value is in line with the national average.",
    "rank_h2": "Place among Russian regions",
    "rank_full_link": "full regional ranking",
    "rank_sentence": "In {year}, {region} {rank_phrase}{rating_ref}.",
    "dyn_h2_by_year": "{indicator} in {region} by year",
    "dyn_h2_neighbors": "Dynamics over neighbouring years",
    "checkpoints_h2": "Checkpoint years",
    "checkpoint_item": "{year} — {value}{unit}",
    "decade_h2": "The last ten years",
    "cta_h2": "Chart and full data",
    "cta_link": "{indicator} in {region}",
    "cta_p": (
        "Full history, an interactive chart and data for all regions — "
        "on the {_link} page."
    ),
    "other_years_h2": "Other years",
    "other_year_link": "{indicator} in {year}",
    "trail_last": "{indicator} in {region}, {year}",
    "rank_desc": " The region holds place {position} of {total} federal subjects.",
    "rank_desc_none": " Regional rankings and values by year.",
    "jsonld_name": "{indicator} — {region}, {year}",
    "keywords": (
        "{indicator} {region} {year}, {indicator} {region} by year, "
        "{indicator} {region} ranking, {region} statistics {year}"
    ),
}

_RF_TAIL_RU = {
    "above": " Значение региона выше среднероссийского.",
    "below": " Значение региона ниже среднероссийского.",
    "level": " Значение региона на уровне общероссийского.",
}


def _t(key: str, **kwargs) -> str | None:
    """EN-шаблон этого рендера; на RU-локали или без ключа — None."""
    if get_locale() != "en":
        return None
    tpl = _YEAR_TEMPLATES_EN.get(key)
    return tpl.format(**kwargs) if tpl else None


def _fmt_locale(value: float) -> str:
    """Число в типографике локали: RU — `_fmt`, EN — display-форматтер."""
    if get_locale() == "en":
        return format_number_ru(value)
    return _fmt(value)


def _h1(indicator: str, region: str, year: int) -> str:
    return (
        _t("h1", indicator=indicator, region=region, year=year)
        or f"{indicator} в регионе {region}, {year}: значение и динамика"
    )


def _title(indicator: str, region: str, year: int, value: str, unit: str) -> str:
    """EN — через общий ключ карточки (есть {year}-слот), иначе русский."""
    tpl = _rt(
        "region_indicator.title",
        indicator=indicator,
        region=region,
        value=value,
        unit=unit,
        year=year,
    )
    if tpl:
        return tpl
    unit_part = f": {value} {unit}" if unit else f": {value}"
    return f"{indicator} — {region}, {year}{unit_part}"


def _signed_text(delta: float) -> str:
    """«+124,3» / «+124.3» — системный display-форматтер знает локаль."""
    return format_number_ru(delta, signed=True)


def _pct_en(cur: float, base: float) -> str | None:
    """EN-фраза динамики: те же шаблоны карточки из REGIONAL_TEMPLATES_EN,
    но числа в EN-типографике (общая `_pct` держит русскую `_fmt`)."""
    if base is None or cur is None or base == 0:
        return None
    pct = (cur - base) / abs(base) * 100
    if abs(pct) < 0.05:
        return _rt("region_indicator.pct_flat") or "was virtually unchanged"
    verb = (
        (_rt("region_indicator.pct_up") or "rose")
        if pct > 0
        else (_rt("region_indicator.pct_down") or "fell")
    )
    if pct >= 200 and base > 0:
        return f"{verb} {format_number_ru(round(cur / base, 1))}-fold"
    by = format_number_ru(round(abs(pct), 1))
    return f"{verb}{(_rt('region_indicator.pct_by') or ' by {pct}%').format(pct=by)}"


def _rel_rf_word(cur: float, rf: float) -> str:
    """Отношение к среднему по России: ключ above / below / level."""
    if abs(cur - rf) / (abs(rf) or 1) < 0.005:
        return "level"
    return "above" if cur > rf else "below"


def _table(values: list[tuple[int, float]], year: int, unit_head: str) -> str:
    """Таблица «год — значение», выбранная строка выделена, свежие сверху."""
    en = get_locale() == "en"
    head_year = "Year" if en else "Год"
    head_value = unit_head or ("Value" if en else "Значение")
    rows = "".join(
        (
            f"<tr><td><strong>{y}</strong></td>"
            f"<td><strong>{_fmt_locale(v)}</strong></td></tr>"
            if y == year
            else f"<tr><td>{y}</td><td>{_fmt_locale(v)}</td></tr>"
        )
        for y, v in values
    )
    return (
        f"<table><thead><tr><th>{head_year}</th>"
        f"<th>{escape(head_value)}</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def _checkpoint_items(series: list[tuple[int, float]]) -> list[int]:
    """Контрольные годы: каждый пятый от начала ряда (для длинных серий)."""
    if not series:
        return []
    first_year = series[0][0]
    return [y for y, _v in series if (y - first_year) % 5 == 0]


async def render_region_indicator_year_html(
    slug: str, code: str, year: int, db: AsyncSession
) -> tuple[int, str]:
    """Годовая landing-страница региона-показателя: значение года, ранг года,
    сравнение с Россией, соседние годы, переход на карточку."""
    year = int(year)

    region = await _region(db, slug)
    if region is None or region.kind not in _ALLOWED_REGION_KINDS:
        return 404, "Not found"
    indicator = (await db.execute(
        select(RegionIndicator).where(RegionIndicator.code == code)
    )).scalar_one_or_none()
    if indicator is None:
        return 404, "Not found"

    rows = (await db.execute(
        select(RegionDataPoint.year, RegionDataPoint.value)
        .where(RegionDataPoint.indicator_id == indicator.id,
               RegionDataPoint.region_id == region.id)
        .order_by(RegionDataPoint.year)
    )).all()
    series = [(int(y), float(v)) for y, v in rows]
    by_year = dict(series)
    # Страница существует ровно на точки данных: выбранный год обязан быть в ряду.
    if year not in by_year:
        return 404, "Not found"
    value = by_year[year]
    years = [y for y, _v in series]

    region_name = region_display_name(region.slug, region.name)
    icopy = _icopy(indicator)
    ind_name = icopy["name"] or indicator.name
    unit = (icopy["unit"] or indicator.unit or "").strip()
    section_name = icopy["section"] or indicator.section_name
    unit_sfx = f" {escape(unit)}" if unit else ""

    en = get_locale() == "en"
    src_label = translate_source("Росстат")

    # Средний уровень по России за тот же год
    rf_value: float | None = None
    if region.slug != "russia":
        rf = await _region(db, "russia")
        if rf is not None:
            rf_value = (await db.execute(
                select(RegionDataPoint.value)
                .where(RegionDataPoint.indicator_id == indicator.id,
                       RegionDataPoint.region_id == rf.id,
                       RegionDataPoint.year == year)
            )).scalar_one_or_none()

    # Рейтинг ВСЕХ субъектов именно за выбранный год
    achievement = region_rating_is_achievement(indicator.code, indicator.table_code)
    rank_rows = (await db.execute(
        select(Region.slug, RegionDataPoint.value)
        .join(Region, Region.id == RegionDataPoint.region_id)
        .where(RegionDataPoint.indicator_id == indicator.id,
               RegionDataPoint.year == year,
               Region.kind == "region")
        .order_by(region_rating_order_by(
            RegionDataPoint.value, indicator.code, indicator.table_code
        ))
    )).all()
    position = next(
        (i for i, (s, _v) in enumerate(rank_rows, 1) if s == region.slug), None
    )
    total_regions = len(rank_rows)
    rank_available = position is not None and total_regions >= 2

    prev_year = max((y for y in years if y < year), default=None)
    prev_value = by_year.get(prev_year) if prev_year is not None else None
    change_abs = value - prev_value if prev_value is not None else None
    change_pct = _pct(value, prev_value) if prev_value is not None else None

    # --- видимый график ---
    alt = _t(
        "alt", indicator=ind_name, region=region_name, year=year,
        value=_fmt_locale(value), unit=unit_sfx, source=src_label,
    ) or (
        f"{ind_name} — {region_name}, {year}: "
        f"значение {_fmt_locale(value)}{unit_sfx}, "
        f"место среди регионов, источник Росстат"
    )
    caption = _t(
        "caption", indicator=ind_name, region=region_name, year=year,
        source=src_label,
    ) or f"{ind_name} в регионе {region_name}, {year} год. Источник: Росстат."
    figure_html = _seo_chart_figure(
        paths.og_region_year(slug, code, year),
        alt,
        caption,
        href=paths.region_indicator(slug, code),
        loading="eager",
    )

    # --- абзацы контента ---
    desc_main = _t(
        "desc_main", indicator=ind_name, region=region_name, year=year,
        value=_fmt_locale(value), unit=unit_sfx,
    ) or (
        f"{ind_name} в регионе {region_name} в {year} году — "
        f"{_fmt_locale(value)}{unit_sfx}."
    )
    paragraphs = [f"<p>{desc_main}</p>"]

    if change_abs is not None:
        signed = _signed_text(change_abs)
        if en:
            pct_phrase = _pct_en(value, prev_value) if prev_value is not None else None
            core = (
                _t("change_vs_pct", prev_year=prev_year, abs=signed,
                   unit=unit_sfx, pct=pct_phrase)
                if pct_phrase
                else _t("change_vs", prev_year=prev_year, abs=signed, unit=unit_sfx)
            )
            paragraphs.append(f"<p>{core}</p>")
        else:
            core = f"Изменение к {prev_year} году: {signed}{unit_sfx}"
            if change_pct:
                paragraphs.append(f"<p>{core} (показатель {change_pct}).</p>")
            else:
                paragraphs.append(f"<p>{core}.</p>")

    rf_paragraph = ""
    if rf_value is not None:
        rel = _rel_rf_word(value, float(rf_value))
        if en:
            rf_paragraph = (
                f"<section class=\"seo-section\">"
                f"<h2>{escape(_t('rf_h2') or '')}</h2>"
                f"<p>{_t('rf_para', year=year, value=_fmt_locale(float(rf_value)), unit=unit_sfx)}"
                f"{_t(f'rf_{rel}') or ''}</p></section>"
            )
        else:
            rf_paragraph = (
                f"<section class=\"seo-section\"><h2>Сравнение со средним по России</h2>"
                f"<p>В среднем по России в {year} году — {_fmt(float(rf_value))}"
                f"{unit_sfx}.{_RF_TAIL_RU[rel]}</p></section>"
            )

    rank_section = ""
    if rank_available:
        assert position is not None
        rank_phrase = _rank_phrase(position, total_regions, achievement=achievement)
        rating_ref = ""
        if total_regions >= 10:
            rating_label = _t("rank_full_link") or (
                "full regional ranking" if en else "полный рейтинг регионов"
            )
            rating_ref = (
                f' (<a href="{escape(paths.region_rating(code))}">'
                f"{escape(rating_label)}</a>)"
            )
        if en:
            rank_section = (
                f"<section class=\"seo-section\">"
                f"<h2>{escape(_t('rank_h2') or '')}</h2>"
                f"<p>{_t('rank_sentence', year=year, region=escape(region_name), rank_phrase=rank_phrase, rating_ref=rating_ref)}</p></section>"
            )
        else:
            rank_section = (
                f"<section class=\"seo-section\"><h2>Место среди регионов России</h2>"
                f"<p>В {year} году {escape(region_name)} {rank_phrase}"
                f"{rating_ref}.</p></section>"
            )

    # --- динамика по годам ---
    def _to_point(s: tuple[int, float]) -> tuple[int, float, date]:
        return s[0], s[1], date(s[0], 1, 1)

    points = [_to_point(s) for s in series]
    dyn_unit = unit or ("Value" if en else "Значение")
    if len(points) < _LONG_SERIES_THRESHOLD:
        shown = sorted(points, key=lambda t: t[0], reverse=True)
        dyn_table = _table([(y, v) for y, v, _d in shown], year, dyn_unit)
        dyn_h2 = _t("dyn_h2_by_year", indicator=ind_name, region=region_name) or (
            f"{ind_name} в регионе {region_name} по годам"
        )
        extra_dyn_sections = ""
    else:
        window = list(reversed(neighbor_year_window(points, year, size=10)))
        window_table = _table([(y, v) for y, v, _d in window], year, dyn_unit)
        dec_late = sorted(points[-10:], key=lambda t: t[0], reverse=True)
        decade_table = _table([(y, v) for y, v, _d in dec_late], year, dyn_unit)
        dyn_table = window_table
        dyn_h2 = _t("dyn_h2_neighbors") or "Динамика соседних лет"
        cp_years = _checkpoint_items(series)
        extra_dyn_sections = ""
        if len(cp_years) >= 3:
            shown_years = {y for y in cp_years if y != year}
            shown_years.add(year)
            cp_list = "".join(
                "<li>{}</li>".format(
                    _t("checkpoint_item", year=y,
                       value=_fmt_locale(by_year[y]), unit=unit_sfx)
                    or f"{y} год — {_fmt_locale(by_year[y])}{unit_sfx}"
                )
                for y in sorted(shown_years)
            )
            extra_dyn_sections += (
                f"<section class=\"seo-section\">"
                f"<h2>{escape(_t('checkpoints_h2') or 'Контрольные годы')}</h2>"
                f"<ul>{cp_list}</ul></section>"
            )
        extra_dyn_sections += (
            f"<section class=\"seo-section\">"
            f"<h2>{escape(_t('decade_h2') or 'Последние десять лет')}</h2>"
            f"{decade_table}</section>"
        )

    card_href = paths.region_indicator(slug, code)
    if en:
        card_label = _t("cta_link", indicator=ind_name, region=region_name) or (
            f"{ind_name} in {region_name}"
        )
        anchor = _link(card_href, card_label)
        cta_p = _t("cta_p", _link=anchor) or (
            "Full history, an interactive chart and data for all regions — "
            f"on the {anchor} page."
        )
    else:
        anchor = (
            f"<a href=\"{escape(card_href)}\">"
            f"{escape(ind_name)} в регионе {escape(region_name)}</a>"
        )
        cta_p = (
            "Полная история, интерактивный график и данные по всем регионам — "
            f"на странице {anchor}."
        )

    others = sorted(
        (y for y in years if y != year and y >= regional_year_min()),
        reverse=True,
    )[:_OTHER_YEARS_LIMIT]
    other_links = _links_list([
        (
            paths.region_indicator_year(slug, code, y),
            _t("other_year_link", indicator=ind_name, year=y)
            or f"{ind_name} в {y} году",
        )
        for y in others
    ])

    # --- хлебные крошки ---
    trail = crumbs.region_indicator_trail(
        region_name, paths.region(slug), ind_name,
        paths.region_indicator(slug, code),
    )
    trail.append((
        paths.region_indicator_year(slug, code, year),
        _t("trail_last", indicator=ind_name, region=region_name, year=year)
        or f"{ind_name} в регионе {region_name}, {year}",
    ))

    # --- мета ---
    canonical = paths.region_indicator_year(slug, code, year)
    og_path = paths.og_region_year(slug, code, year)
    title = _title(ind_name, region_name, year, _fmt_locale(value), unit)
    if rank_available:
        assert position is not None
        rank_desc = _t("rank_desc", position=position, total=total_regions) or (
            f" Регион занимает {position}-е место из {total_regions} субъектов РФ."
        )
    else:
        rank_desc = _t("rank_desc_none") or " Рейтинг регионов и значения по годам."
    desc = f"{desc_main}{rank_desc}"

    json_ld = [
        _site_json_ld(),
        _breadcrumbs(trail),
        {
            "@context": "https://schema.org",
            "@type": "Dataset",
            "name": _t("jsonld_name", indicator=ind_name, region=region_name,
                       year=year)
            or f"{ind_name} — {region_name}, {year}",
            "description": desc,
            "url": _absolute(canonical),
            "creator": {"@type": "Organization", "name": src_label},
            "temporalCoverage": f"{year}-01-01/{year}-12-31",
            "spatialCoverage": region_name,
            "variableMeasured": f"{ind_name}, {unit}" if unit else ind_name,
            "license": "https://creativecommons.org/licenses/by/4.0/",
            "image": _absolute(og_path),
        },
        {
            "@context": "https://schema.org",
            "@type": "ImageObject",
            "contentUrl": _absolute(og_path),
            "url": _absolute(og_path),
            "width": 1200,
            "height": 630,
            "caption": caption,
            "representativeOfPage": True,
        },
    ]

    cta_h2 = _t("cta_h2") or "График и полные данные"
    other_h2 = _t("other_years_h2") or "Другие годы"
    body = f"""<div class="seo-page">
{_breadcrumbs_nav(trail)}
<p class="seo-eyebrow">{escape(f"{section_name} — {region_name}") if section_name else escape(region_name)}</p>
<h1>{escape(_h1(ind_name, region_name, year))}</h1>
{figure_html}
{''.join(paragraphs)}
{rank_section}
{rf_paragraph}
<section class="seo-section"><h2>{escape(dyn_h2)}</h2>
{dyn_table}
</section>
{extra_dyn_sections}
<section class="seo-section"><h2>{escape(cta_h2)}</h2>
<p>{cta_p}</p></section>
<section class="seo-section"><h2>{escape(other_h2)}</h2>
{other_links}
</section>
</div>"""

    html = await build_document(
        title=title,
        description=desc,
        canonical_path=canonical,
        body=body,
        json_ld=json_ld,
        keywords=(
            _t("keywords", indicator=ind_name, region=region_name, year=year)
            or (
                f"{ind_name} {region_name} {year}, {ind_name} {region_name} по годам, "
                f"{ind_name} {region_name} рейтинг, {region_name} статистика {year}"
            )
        ),
        og_image=_absolute(og_path),
        include_app=False,
    )
    return 200, html
