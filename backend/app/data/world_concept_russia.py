"""Россия в межстрановом рейтинге/карте: смысл × единица.

Россия не входит в Eurostat-plane (`WorldCountry`). Сопоставимые ряды берутся
из национального каталога (`indicators`) и приводятся к единице рейтинга.
Единая точка для API и SSR — `app.services.world_russia_rank`.

Правило приёмки: значение в рейтинге = последнее значение связанного ряда
на карточке индикатора, в единице таблицы (YoY %, человек, …).
Если сопоставимого ряда нет — Россию в срез не включаем.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RussiaValueKind = Literal["level", "yoy_ready"]


@dataclass(frozen=True)
class RussiaConceptLink:
    """Связь curated world-concept → отечественный indicator.code."""

    indicator_code: str
    # level — сырой уровень (после scale); yoy_ready — уже изменение за год, %.
    value_kind: RussiaValueKind = "level"
    # Множитель к сырому значению (население Росстата — млн чел. → человек).
    scale: float = 1.0
    note_ru: str = ""
    note_en: str = ""
    # Пусто — «Росстат». Для МВФ-оверлея задаём явно, чтобы рейтинг не врал.
    source_ru: str | None = None
    source_en: str | None = None


# Только честно сопоставимые по смыслу и приводимые к единице таблицы.
RUSSIA_CONCEPT_LINKS: dict[str, RussiaConceptLink] = {
    "unemployment-rate": RussiaConceptLink(
        indicator_code="unemployment",
        value_kind="level",
        note_ru=(
            "Для России в рейтинг входит уровень безработицы по обследованию "
            "рабочей силы Росстата. Зарубежные значения — по гармонизированной "
            "методологии Евростата. Оба показателя близки по смыслу (доля "
            "безработных среди экономически активного населения), но возрастная "
            "база и детали обследования могут отличаться."
        ),
        note_en=(
            "For Russia the ranking uses the unemployment rate from Rosstat’s "
            "labour force survey. Foreign values follow Eurostat’s harmonised "
            "methodology. Both measures are close in meaning (share of unemployed "
            "in the labour force), but age coverage and survey details may differ."
        ),
    ),
    "hicp-index": RussiaConceptLink(
        indicator_code="cpi-yoy",
        value_kind="yoy_ready",
        note_ru=(
            "Для России сравнивается изменение потребительских цен за год по "
            "данным Росстата (индекс потребительских цен), для зарубежных стран — "
            "гармонизированный индекс Евростата или национальный индекс цен. "
            "Составы потребительских корзин различаются; сравнивается именно "
            "относительное изменение за год, а не уровень индекса и не изменение "
            "к предыдущему месяцу."
        ),
        note_en=(
            "For Russia the comparison uses year-on-year consumer price change "
            "from Rosstat (the consumer price index); for other countries — "
            "Eurostat’s harmonised index or a national price index. Basket "
            "compositions differ; the ranking compares the relative change over "
            "the year, not the index level and not the month-on-month change."
        ),
    ),
    "population": RussiaConceptLink(
        indicator_code="population",
        value_kind="level",
        scale=1_000_000.0,
        note_ru=(
            "Численность населения России — по данным Росстата (в публикации "
            "ведомства ряд ведётся в миллионах человек; в таблице приведена "
            "численность в человеках). Для зарубежных стран — данные их "
            "статистических ведомств или Евростата."
        ),
        note_en=(
            "Russia’s population is from Rosstat (the agency publishes the series "
            "in millions of people; the table shows headcount in persons). For "
            "other countries — their national statistical offices or Eurostat."
        ),
    ),
    "gdp-usd": RussiaConceptLink(
        indicator_code="weo-gdp-usd",
        value_kind="level",
        source_ru="Международный валютный фонд",
        source_en="International Monetary Fund",
        note_ru=(
            "Для России в рейтинг входит годовая оценка валового внутреннего "
            "продукта в текущих долларах США из публикации «Перспективы "
            "развития мировой экономики» Международного валютного фонда. "
            "Тот же выпуск используется для зарубежных стран. Это не оценка "
            "Росстата в рублях и не пересчёт национальной валюты по курсу "
            "Банка России."
        ),
        note_en=(
            "For Russia the ranking uses the IMF World Economic Outlook "
            "annual estimate of GDP in current US dollars. Other countries "
            "come from the same publication. This is not Rosstat’s ruble "
            "national-accounts series and not a conversion of local currency "
            "at the Bank of Russia exchange rate."
        ),
    ),
    "gdp-per-capita-usd": RussiaConceptLink(
        indicator_code="weo-gdp-per-capita-usd",
        value_kind="level",
        source_ru="Международный валютный фонд",
        source_en="International Monetary Fund",
        note_ru=(
            "Для России в рейтинг входит годовая оценка валового внутреннего "
            "продукта на душу населения в текущих долларах США из публикации "
            "«Перспективы развития мировой экономики» Международного валютного "
            "фонда. Тот же выпуск используется для зарубежных стран. Это не "
            "ряд Росстата и не пересчёт рублей по курсу Банка России."
        ),
        note_en=(
            "For Russia the ranking uses the IMF World Economic Outlook "
            "annual estimate of GDP per capita in current US dollars. Other "
            "countries come from the same publication. This is not a Rosstat "
            "series and not a conversion of rubles at the Bank of Russia "
            "exchange rate."
        ),
    ),
    # gdp-volume-* — национальная валюта, rating-поверхности нет.
    # budget-balance-gdp — % ВВП Евростата vs млрд руб. Минфина: не смешиваем.
    # government-debt-gdp — единица и охват S.13 не совпадают с рядом Минфина.
    # long-term-interest-rate — доходность облигаций ≠ ключевая ставка ЦБ.
    # activity-rate / gdp-per-capita-eu — нет честного отечественного аналога.
    # gdp-nominal российского каталога — рубли Росстата, не этот концепт.
}


RUSSIA_COUNTRY_PAYLOAD = {
    "code": "RU",
    "slug": "russia",
    "name": "Россия",
    "name_en": "Russia",
    "name_ru": "Россия",
    "region": "Европа",
    "region_ru": "Европа",
    "indicators_count": 0,
    "is_active": True,
}


def russia_list_country_payload(indicators_count: int, *, locale: str) -> dict:
    """Карточка России в каталоге стран: тот же счётчик «рядов», что у остальных.

    ``region`` подставляет вызывающий через ту же локализацию, что и Eurostat-страны.
    """
    n = int(indicators_count or 0)
    en = (locale or "").strip().lower() == "en"
    return {
        "code": RUSSIA_COUNTRY_PAYLOAD["code"],
        "slug": RUSSIA_COUNTRY_PAYLOAD["slug"],
        "name": RUSSIA_COUNTRY_PAYLOAD["name_en"] if en else RUSSIA_COUNTRY_PAYLOAD["name"],
        "name_en": RUSSIA_COUNTRY_PAYLOAD["name_en"],
        "indicators_count": n,
    }


def russia_link_for_concept(concept_slug: str) -> RussiaConceptLink | None:
    return RUSSIA_CONCEPT_LINKS.get(concept_slug)


def russia_eligible(concept_slug: str) -> bool:
    return concept_slug in RUSSIA_CONCEPT_LINKS
