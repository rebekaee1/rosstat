"""Реестр квартальных и годовых рядов ЕМИСС по регионам (19.11.2026, зона D круга Пульса).

Наборы (страница набора — ``https://www.fedstat.ru/indicator/{id}``):

- 31452 — средняя цена 1 м² квартир, первичный и вторичный рынок, все типы и четыре типа квартир, с 2000 года;
- 30925 — индексы цен на рынке жилья; берём один вид из пяти: «к соответствующему кварталу предыдущего года»
  (рост за год, понятен без пояснений; остальные виды — служебные пересчёты того же индекса);
- 61781 — средняя цена 1 м² квартир в центре субъекта (областном городе), с 2021 года, все типы квартир;
- 58537 — доходы на человека к прожиточному минимуму, %, поквартально с 1992 года;
- 30957 — прожиточный минимум по группам населения. Поквартально он устанавливался до 2020 года, с 2021 года —
  на год вперёд, поэтому ряд годовой (``layer='annual'``, период «значение показателя за год»). Плановые годы
  (в источнике уже есть 2027) отрезаются: год точки не позже текущего.

«Все население» 30957 продолжает уже существующий годовой ряд сборника «Регионы России» (таблица 3.11,
2021–2024): ЕМИСС дописывает только годы с 2025 (``min_year``), метаданные остаются за сборником
(``own_metadata=False``). Остальные ряды заводит сам загрузчик — он умеет начать с пустой базы.

Названия — человеческие (правило R4-D), без «ЕМИСС», номеров наборов и канцелярита; номер набора — в ``note``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

QUARTER_OIDS = {"1540222": 1, "1540224": 2, "1540226": 3, "1540227": 4}
YEAR_VALUE_OID = "1558883"  # «значение показателя за год»
RUBLE = "950351"
PERCENT = "950473"

RUSSIA_LEGACY = "Российская Федерация"
RUSSIA_WITHOUT_NEW = "Российская Федерация без учета новых субъектов (с 01.01.2023)"

MARKET_DIM = "63148"
PRIMARY, SECONDARY = "1855614", "1855615"
FLAT_DIM = "58849"
ALL_FLATS, LOW, TYPICAL, IMPROVED, ELITE = "1752264", "1752263", "1752262", "1752261", "1752260"

SECTION_PRICES = (20, "Цены и тарифы", "Prices and tariffs")
SECTION_LIVING = (3, "Уровень жизни населения", "Living standards")


@dataclass(frozen=True)
class QSeries:
    """Один ряд сайта: ``key`` — значения измерений строки ответа (в порядке ``Dataset.line_dims``)."""

    code: str
    key: tuple[str, ...]
    name_ru: str
    name_en: str
    table_code: str
    min_year: int | None = None
    own_metadata: bool = True


@dataclass(frozen=True)
class Dataset:
    id: int
    layer: str  # 'quarterly' | 'annual'
    unit_oid: str
    unit_ru: str
    unit_en: str
    note_ru: str
    note_en: str
    section: tuple[int, str, str]
    first_year: int
    line_dims: tuple[str, ...]
    fixed_filters: tuple[str, ...]
    series: tuple[QSeries, ...]
    # Территории вне общего справочника, которые здесь означают субъект целиком: название → (oid, slug).
    # Точка под основным названием субъекта приоритетнее.
    aliases: dict[str, tuple[str, str]] = field(default_factory=dict)
    # Зона F (19.11.2026). Измерение территорий: 57831 — ОКАТО Росстата; 30628 — межведомственный ОКАТО
    # (наборы Соцфонда), его oid берутся из ``regional/emiss_social_territories.json`` по ключу ``territories_key``.
    territory_dim: str = "57831"
    territories_key: str | None = None
    # Свои периоды набора: oid → номер квартала (квартальный слой) или единственный oid годового значения.
    # Пусто — «I–IV квартал» (QUARTER_OIDS) или «значение показателя за год».
    periods: dict[str, int] = field(default_factory=dict)
    # Значение «на 1-е число» квартала (пенсия на 1 октября = IV квартал): известно уже в текущем квартале.
    at_quarter_start: bool = False
    # Верхняя граница здравого смысла (у 34158 встречается заглушка 1 000 000 тыс. га); None — без границы.
    max_value: float | None = None

    @property
    def period_map(self) -> dict[str, int]:
        if self.periods:
            return self.periods
        return {YEAR_VALUE_OID: 0} if self.layer == "annual" else QUARTER_OIDS

    @property
    def period_oids(self) -> tuple[str, ...]:
        return tuple(self.period_map)


_MARKET = {PRIMARY: "Первичный рынок жилья", SECONDARY: "Вторичный рынок жилья"}
_FLATS = {
    ALL_FLATS: "Все типы квартир", LOW: "Низкого качества", TYPICAL: "Квартиры среднего качества (типовые)",
    IMPROVED: "Улучшенного качества", ELITE: "Элитные квартиры",
}

# (market, flat, суффикс кода, ru-хвост названия, en-хвост названия)
_PRICE_ROWS = (
    (PRIMARY, ALL_FLATS, "pervichnyy", "первичный рынок", "new homes"),
    (SECONDARY, ALL_FLATS, "vtorichnyy", "вторичный рынок", "existing homes"),
    (PRIMARY, TYPICAL, "pervichnyy-tipovye", "первичный рынок, типовые квартиры", "new homes, standard flats"),
    (PRIMARY, IMPROVED, "pervichnyy-uluchshennye", "первичный рынок, квартиры улучшенного качества",
     "new homes, improved flats"),
    (PRIMARY, ELITE, "pervichnyy-elitnye", "первичный рынок, элитные квартиры", "new homes, luxury flats"),
    (SECONDARY, LOW, "vtorichnyy-nizkogo-kachestva", "вторичный рынок, квартиры низкого качества",
     "existing homes, low-quality flats"),
    (SECONDARY, TYPICAL, "vtorichnyy-tipovye", "вторичный рынок, типовые квартиры", "existing homes, standard flats"),
    (SECONDARY, IMPROVED, "vtorichnyy-uluchshennye", "вторичный рынок, квартиры улучшенного качества",
     "existing homes, improved flats"),
    (SECONDARY, ELITE, "vtorichnyy-elitnye", "вторичный рынок, элитные квартиры", "existing homes, luxury flats"),
)

HOUSING_PRICES = Dataset(
    id=31452, layer="quarterly", unit_oid=RUBLE, unit_ru="рублей за м²", unit_en="RUB per m²",
    note_ru="Средняя цена 1 м² общей площади квартир за квартал по сделкам на рынке жилья. Источник: Росстат.",
    note_en="Average price per square metre of total floor area over the quarter. Source: Rosstat.",
    section=SECTION_PRICES, first_year=2000,
    line_dims=("57831", MARKET_DIM, FLAT_DIM, "3"),
    fixed_filters=(f"{MARKET_DIM}_{PRIMARY}", f"{MARKET_DIM}_{SECONDARY}",
                   *(f"{FLAT_DIM}_{oid}" for oid in _FLATS)),
    series=tuple(
        QSeries(f"cena-m2-zhilya-{suffix}", (_MARKET[market], _FLATS[flat]),
                f"Цена 1 м² жилья, {ru}", f"Housing price per m², {en}", f"20.q{n}")
        for n, (market, flat, suffix, ru, en) in enumerate(_PRICE_ROWS, 1)
    ),
)

HOUSING_INDEX = Dataset(
    id=30925, layer="quarterly", unit_oid=PERCENT,
    unit_ru="% к тому же кварталу прошлого года", unit_en="% of the same quarter a year earlier",
    note_ru="Во сколько процентов от цены год назад стоит жильё сейчас: 107 — подорожало на 7 % за год. "
            "Индекс учитывает разный состав сделок, поэтому может расходиться с изменением средней цены. "
            "Источник: Росстат.",
    note_en="Current housing prices as a percentage of the same quarter a year earlier: 107 means 7% dearer. "
            "The index adjusts for the mix of deals, so it can differ from the change in the average price. "
            "Source: Rosstat.",
    section=SECTION_PRICES, first_year=2000,
    line_dims=("57831", MARKET_DIM, "3"),
    fixed_filters=("57937_1698421", f"{MARKET_DIM}_{PRIMARY}", f"{MARKET_DIM}_{SECONDARY}",
                   f"{FLAT_DIM}_{ALL_FLATS}"),
    series=(
        QSeries("indeks-cen-zhilya-pervichnyy-god", (_MARKET[PRIMARY],),
                "Рост цен на жильё за год, первичный рынок", "Housing price growth over a year, new homes", "20.q10"),
        QSeries("indeks-cen-zhilya-vtorichnyy-god", (_MARKET[SECONDARY],),
                "Рост цен на жильё за год, вторичный рынок", "Housing price growth over a year, existing homes",
                "20.q11"),
    ),
)

CITY_PRICES = Dataset(
    id=61781, layer="quarterly", unit_oid=RUBLE, unit_ru="рублей за м²", unit_en="RUB per m²",
    note_ru="Средняя цена 1 м² общей площади квартир в административном центре субъекта (областном, краевом "
            "городе, столице республики) за квартал, все типы квартир. Источник: Росстат.",
    note_en="Average price per square metre of total floor area in the region's administrative centre "
            "(its capital city) over the quarter, all flat types. Source: Rosstat.",
    section=SECTION_PRICES, first_year=2021,
    line_dims=("57831", MARKET_DIM, "3"),
    fixed_filters=("61782_1846504", f"{MARKET_DIM}_{PRIMARY}", f"{MARKET_DIM}_{SECONDARY}",
                   f"{FLAT_DIM}_{ALL_FLATS}"),
    series=(
        QSeries("cena-m2-zhilya-centr-pervichnyy", (_MARKET[PRIMARY],),
                "Цена 1 м² жилья в главном городе региона, первичный рынок",
                "Housing price per m² in the regional capital, new homes", "20.q12"),
        QSeries("cena-m2-zhilya-centr-vtorichnyy", (_MARKET[SECONDARY],),
                "Цена 1 м² жилья в главном городе региона, вторичный рынок",
                "Housing price per m² in the regional capital, existing homes", "20.q13"),
    ),
    # Центр субъекта один и тот же: Архангельск и Тюмень в источнике подписаны «областью без округов».
    aliases={
        "Архангельская область (кроме Ненецкого автономного округа)": ("1692939", "arhangelskaya-oblast"),
        "Тюменская область (кроме Ханты-Мансийского автономного округа-Югры и Ямало-Ненецкого автономного округа)":
            ("1692940", "tyumenskaya-oblast"),
    },
)

INCOME_TO_MINIMUM = Dataset(
    id=58537, layer="quarterly", unit_oid=PERCENT, unit_ru="% от прожиточного минимума",
    unit_en="% of the subsistence minimum",
    note_ru="Средний денежный доход на человека за квартал в процентах от прожиточного минимума: 300 — доход "
            "втрое выше минимума. Источник: Росстат.",
    note_en="Average money income per person over the quarter as a percentage of the subsistence minimum: "
            "300 means three times the minimum. Source: Rosstat.",
    section=SECTION_LIVING, first_year=1992,
    line_dims=("57831", "3"),
    fixed_filters=(),
    series=(
        QSeries("dohody-k-prozhitochnomu-minimumu", (),
                "Доходы к прожиточному минимуму", "Income relative to the subsistence minimum", "3.q1"),
    ),
)

LIVING_MINIMUM = Dataset(
    id=30957, layer="annual", unit_oid=RUBLE, unit_ru="рублей в месяц", unit_en="RUB per month",
    note_ru="Прожиточный минимум, установленный в регионе на год, на человека в месяц. Источник: Росстат.",
    note_en="Subsistence minimum set in the region for the year, per person per month. Source: Rosstat.",
    section=SECTION_LIVING, first_year=1992,
    line_dims=("57831", "58812", "3"),
    fixed_filters=("58812_1750834", "58812_1754441", "58812_1754442", "58812_1754443"),
    series=(
        QSeries("velichina-prozhitochnogo-minimuma-ustanovlennaya-v-tselom-po-3-11", ("Все население",),
                "", "", "3.11", min_year=2025, own_metadata=False),
        QSeries("prozhitochnyy-minimum-deti", ("Дети",),
                "Прожиточный минимум для детей", "Subsistence minimum for children", "3.a1"),
        QSeries("prozhitochnyy-minimum-pensionery", ("Пенсионеры",),
                "Прожиточный минимум для пенсионеров", "Subsistence minimum for pensioners", "3.a2"),
        QSeries("prozhitochnyy-minimum-trudosposobnye", ("Трудоспособное население",),
                "Прожиточный минимум для трудоспособных", "Subsistence minimum for working-age adults", "3.a3"),
    ),
)

# --- Зона F (19.11.2026): пенсии по видам, итоги сева и уборки ---------------------------------------------

SECTION_AGRO = (13, "Сельское хозяйство", "Agriculture")
_ALL_PENSIONERS, _NOT_WORKING = "Работающие и неработающие", "Неработающие"
_PENSION_KINDS = {
    "1844327": "По старости", "1844328": "По инвалидности", "1844329": "По случаю потери кормильца",
    "1844331": "Социальные пенсии",
}

# 62164: Соцфонд, «на 1 января / апреля / июля / октября» — значение на начало квартала. Вид «Всего» не берём:
# средняя пенсия всех видов уже идёт помесячно (61699, зона B). «За выслугу лет» не берём: по регионам почти пусто
# (4 территории), у строки России значения около 950 тыс. — не размер пенсии (живой запрос 19.11.2026).
# Измерение территорий — межведомственный ОКАТО.
PENSIONS_BY_KIND = Dataset(
    id=62164, layer="quarterly", unit_oid=RUBLE, unit_ru="рублей в месяц", unit_en="RUB per month",
    note_ru="Средний размер назначенной пенсии на начало квартала: I квартал — на 1 января, II — на 1 апреля, "
            "III — на 1 июля, IV — на 1 октября. Источник: Социальный фонд России, публикует Росстат.",
    note_en="Average pension awarded, at the start of the quarter: Q1 — on 1 January, Q2 — 1 April, "
            "Q3 — 1 July, Q4 — 1 October. Source: Social Fund of Russia, published by Rosstat.",
    section=SECTION_LIVING, first_year=2021,
    line_dims=("30628", "61834", "61609", "3"),
    fixed_filters=(*(f"61834_{oid}" for oid in _PENSION_KINDS), "61609_1839064", "61609_1839066"),
    territory_dim="30628", territories_key="61699",
    periods={"1540248": 1, "1540238": 2, "1540240": 3, "1540245": 4}, at_quarter_start=True,
    max_value=1_000_000.0,
    series=(
        QSeries("pensiya-po-starosti", ("По старости", _ALL_PENSIONERS),
                "Средняя пенсия по старости", "Average old-age pension", "3.q2"),
        QSeries("pensiya-po-starosti-nerabotayuschih", ("По старости", _NOT_WORKING),
                "Средняя пенсия по старости у неработающих пенсионеров",
                "Average old-age pension of non-working pensioners", "3.q3"),
        QSeries("pensiya-po-invalidnosti", ("По инвалидности", _ALL_PENSIONERS),
                "Средняя пенсия по инвалидности", "Average disability pension", "3.q4"),
        QSeries("pensiya-po-potere-kormiltsa", ("По случаю потери кормильца", _ALL_PENSIONERS),
                "Средняя пенсия по потере кормильца", "Average survivor's pension", "3.q5"),
        QSeries("pensiya-socialnaya", ("Социальные пенсии", _ALL_PENSIONERS),
                "Средняя социальная пенсия", "Average social pension", "3.q6"),
    ),
)

# 34165/34158: ход уборки и сева «на 1-е число» месяца сезона, с 2023 года. Людям нужен итог сезона, поэтому
# берётся одна дата — последняя в сезоне: урожай на 1 ноября, яровой сев на 1 июня. Годовой слой, как у
# сборника «Регионы России» (там посевные и сбор заканчиваются 2024 годом). Год без итоговой даты пропускается,
# а не заменяется промежуточной: в ряду только сопоставимые значения.
HARVEST = Dataset(
    id=34165, layer="annual", unit_oid="950311", unit_ru="тысяч тонн", unit_en="thousand tonnes",
    note_ru="Сколько урожая собрали к 1 ноября, хозяйства всех категорий. Оперативные данные: вес при первом "
            "учёте, до сушки и очистки, поэтому окончательный валовой сбор, который Росстат публикует весной, "
            "обычно немного отличается. Источник: Росстат.",
    note_en="Harvest gathered by 1 November, all types of farms. Preliminary data in weight at first "
            "recording, before drying and cleaning, so the final gross harvest published in spring usually "
            "differs slightly. Source: Rosstat.",
    section=SECTION_AGRO, first_year=2023,
    line_dims=("57831", "58745", "3"),
    fixed_filters=("58423_1750642", "58745_1752004", "58745_1754678", "58745_1754679", "58745_1836903"),
    periods={"1540244": 0}, max_value=500_000.0,
    series=(
        QSeries("urozhay-zerno-1-noyabrya", ("Зерновые и зернобобовые культуры",),
                "Сбор урожая к 1 ноября: зерно", "Grain harvested by 1 November", "13.a1"),
        QSeries("urozhay-podsolnechnik-1-noyabrya", ("Подсолнечник на зерно",),
                "Сбор урожая к 1 ноября: подсолнечник", "Sunflower harvested by 1 November", "13.a2"),
        QSeries("urozhay-svekla-1-noyabrya", ("Сахарная свекла",),
                "Сбор урожая к 1 ноября: сахарная свёкла", "Sugar beet harvested by 1 November", "13.a3"),
        QSeries("urozhay-kartofel-1-noyabrya", ("Картофель",),
                "Сбор урожая к 1 ноября: картофель", "Potatoes harvested by 1 November", "13.a4"),
    ),
)

SPRING_SOWING = Dataset(
    id=34158, layer="annual", unit_oid="950283", unit_ru="тысяч гектаров", unit_en="thousand hectares",
    note_ru="Сколько гектаров яровых культур посеяли к 1 июня, хозяйства всех категорий. Яровые сеют весной; "
            "озимые, посеянные осенью, сюда не входят. Оперативные данные. Источник: Росстат.",
    note_en="Spring crops sown by 1 June, all types of farms, thousand hectares. Winter crops sown in autumn "
            "are not included. Preliminary data. Source: Rosstat.",
    section=SECTION_AGRO, first_year=2023,
    line_dims=("57831", "58745", "3"),
    fixed_filters=("58423_1750642", "58745_1751996", "58745_1752004", "58745_1750395", "58745_1752006",
                   "58745_1751993"),
    periods={"1540241": 0}, max_value=100_000.0,
    series=(
        QSeries("yarovoy-sev-vsego-1-iyunya", ("ВСЕГО",),
                "Посевные площади яровых к 1 июня: все культуры", "Spring crops sown by 1 June: all crops", "13.a5"),
        QSeries("yarovoy-sev-zernovye-1-iyunya", ("Зерновые и зернобобовые культуры",),
                "Посевные площади яровых к 1 июня: зерновые", "Spring crops sown by 1 June: grain", "13.a6"),
        QSeries("yarovoy-sev-pshenica-1-iyunya", ("Пшеница",),
                "Посевные площади яровых к 1 июня: пшеница", "Spring wheat sown by 1 June", "13.a7"),
        QSeries("yarovoy-sev-kukuruza-1-iyunya", ("Кукуруза на зерно",),
                "Посевные площади яровых к 1 июня: кукуруза на зерно", "Grain maize sown by 1 June", "13.a8"),
        QSeries("yarovoy-sev-podsolnechnik-1-iyunya", ("Подсолнечник",),
                "Посевные площади яровых к 1 июня: подсолнечник", "Sunflower sown by 1 June", "13.a9"),
    ),
)

DATASETS: tuple[Dataset, ...] = (
    HOUSING_PRICES, HOUSING_INDEX, CITY_PRICES, INCOME_TO_MINIMUM, LIVING_MINIMUM,
    PENSIONS_BY_KIND, HARVEST, SPRING_SOWING,
)


def all_series() -> list[tuple[Dataset, QSeries]]:
    return [(ds, s) for ds in DATASETS for s in ds.series]


def copy_en(ds: Dataset, s: QSeries) -> dict[str, str | None]:
    """Английские название, единица, пояснение и раздел — для ``REGION_INDICATORS_EN``."""
    return {"name": s.name_en, "unit": ds.unit_en, "note": ds.note_en, "section": ds.section[2]}
