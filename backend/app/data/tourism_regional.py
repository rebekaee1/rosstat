"""Туризм по регионам России: реестр рядов (20.11.2026, зона t2 «туризм»).

Что здесь. Все региональные ряды о туризме, собранные 20.11.2026 (``.artifacts/tourism-2026-11-20``), одним
реестром: гостиницы и прочие средства размещения (ЕМИСС, годовые с 2002 года и оперативные помесячно),
санатории, турфирмы и их туристы по странам, оценка турпотока по субъектам (Росстат), «Поездки» платёжного
баланса по субъектам (Банк России), туристический налог (ФНС, 1-НМ), реестр классифицированных средств
размещения (Росаккредитация), реестр турагентов (Минэкономразвития), платные услуги гостиниц, ИПЦ туристских
позиций, речные и морские пассажиры, автобусы и приближённый ряд СберИндекса.

Почему отдельный реестр, а не строки в ``emiss_quarterly``/``emiss_regional_sets``. Те реестры держат oid
позиций (``fixed_filters``), а 20.11.2026 fedstat с ~16:50 МСК отвечает 403 всем нашим адресам: oid новых наборов
узнать нельзя. Здесь ряд описан **названиями** (так их видит человек на странице набора и так они приходят в ответе);
загрузчик (``app.services.tourism_regional_loader``) при доступе читает страницу набора, сам находит oid по названиям
и запрашивает сетку. Поэтому наборы, которые ещё не скачаны (``seed=False``), догрузятся сами, когда бан снимут.
Уже скачанное лежит в ``app/data/regional/tourism_seed.csv.gz`` (собирает ``scripts/build_tourism_regional_seed.py``)
и пишется «только если точки нет»: живой ответ источника всегда главнее.

Подача (решения зоны t2, 20.11.2026):

- раздел регионального каталога 6 «Культура, отдых и туризм» — уже есть на сайте, туризм в нём; ИПЦ туристских
  позиций — в разделе 20 «Цены и тарифы» рядом с остальными ИПЦ, автобусы и общий итог речных перевозок —
  в разделе 16 «Транспорт»;
- ряды, которые уже есть из сборника «Регионы России» до 2024 года (число средств размещения, размещённые лица,
  число турфирм), ЕМИСС продлевает с 2025 года (``min_year``, ``own_metadata=False``): совпадение проверено —
  2024 год, размещённые 90 068,8 тыс. и в сборнике, и в наборе 31560;
- оперативные ряды ЕМИСС публикуются нарастающим итогом «январь–…»; на сайт идёт значение **за месяц**
  (разность соседних точек, январь как есть): так видна сезонность. Месяц без предыдущей точки или с
  отрицательной разностью не пишется. Исключение — туристический налог: его платят раз в квартал, разность
  месяцев ложная, поэтому ряд «с начала года», как турпоездки 62900;
- Россия: до 2022 года строка «Российская Федерация», с 2023 — «без учета новых субъектов» (одна страна, обе
  пишутся в ``russia``). «Крымский федеральный округ» (2014–2016) не берётся;
- оценка турпотока Росстата (файл Turpotok) по годам и кварталам — это **другой** показатель, чем «турпоездки с
  начала года» 62900 (170 и 92 млн поездок за 2025 год), поэтому названия и пояснения у них разные; помесячный
  лист Turpotok не берётся — третий «турпоток» на одном сайте путал бы;
- нули платёжного баланса ЦБ: в региональных файлах ноль бывает округлением (Чукотка), но ряд из одних нулей —
  непубликация; такой ряд региона не пишется.

Единицы на сайте: люди и ночёвки — тысячи, деньги — миллионы рублей (у ЦБ — миллионы долларов США).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------------------------------------------
# Источники: подпись для карточки и тексты «откуда данные» (ru/en). Первоисточник называется прямо; приближённые
# (СберИндекс) подписаны как таковые.

SOURCES: dict[str, dict[str, str]] = {
    "emiss": {
        "ru": "Росстат (ЕМИСС)",
        "en": "Rosstat (EMISS)",
        "about_ru": "Источник — система показателей Росстата (ЕМИСС). Обновляется после очередной публикации "
                    "Росстата; прошлые периоды Росстат иногда уточняет.",
        "about_en": "Source: Rosstat's statistical indicator system (EMISS). Updated after each Rosstat release; "
                    "Rosstat sometimes revises earlier periods.",
    },
    "rosstat_turpotok": {
        "ru": "Росстат, оценка туристского потока",
        "en": "Rosstat, tourist flow estimate",
        "about_ru": "Источник — оценка туристского потока Росстата по субъектам (раздел «Туризм» на сайте "
                    "Росстата). Оценка строится по данным гостиниц, мобильных операторов и опросов, поэтому "
                    "отличается от «турпоездок с начала года» из ЕМИСС.",
        "about_en": "Source: Rosstat's tourist flow estimate by region (Tourism section of the Rosstat website). "
                    "It combines accommodation, mobile network and survey data, so it differs from the EMISS "
                    "“tourist trips, year to date” series.",
    },
    "cbr": {
        "ru": "Банк России",
        "en": "Bank of Russia",
        "about_ru": "Источник — Банк России, экспорт и импорт услуг по субъектам Российской Федерации (статья "
                    "«Поездки» платёжного баланса). Данные квартальные, в миллионах долларов США; последние "
                    "кварталы Банк России уточняет.",
        "about_en": "Source: Bank of Russia, exports and imports of services by Russian region (the “Travel” item "
                    "of the balance of payments). Quarterly data in US$ million; the latest quarters are revised.",
    },
    "fns": {
        "ru": "ФНС России (отчёт 1-НМ)",
        "en": "Federal Tax Service (report 1-NM)",
        "about_ru": "Источник — ФНС России, отчёт 1-НМ о поступлении налогов по субъектам. Туристический налог "
                    "введён с 2025 года; в Москве и Крыму он в 2025 году не взимался.",
        "about_en": "Source: Federal Tax Service, report 1-NM on tax receipts by region. The tourist tax exists "
                    "since 2025; Moscow and Crimea did not levy it in 2025.",
    },
    "fsa": {
        "ru": "Росаккредитация, реестр классифицированных средств размещения",
        "en": "Rosaccreditation, register of classified accommodation",
        "about_ru": "Источник — реестр классифицированных средств размещения Росаккредитации "
                    "(tourism.fsa.gov.ru): гостиницы, базы отдыха, гостевые дома и санатории, прошедшие "
                    "классификацию. Ряд построен по датам внесения в реестр и по статусу записи.",
        "about_en": "Source: Rosaccreditation register of classified accommodation (tourism.fsa.gov.ru): hotels, "
                    "holiday centres, guest houses and sanatoriums that passed classification. The series is "
                    "built from registration dates and record status.",
    },
    "minec": {
        "ru": "Минэкономразвития, реестр туроператоров и турагентов",
        "en": "Ministry of Economic Development, register of tour operators and travel agents",
        "about_ru": "Источник — единый федеральный реестр туроператоров и турагентов Минэкономразвития. Регион — "
                    "по месту регистрации компании (код субъекта в ОГРН или ИНН), поэтому у сетевых компаний он "
                    "может не совпадать с местом работы офисов. Ряд — число записей реестра на конец месяца.",
        "about_en": "Source: Ministry of Economic Development, federal register of tour operators and travel "
                    "agents. The region is where the company is registered (region code in its registration or "
                    "taxpayer number), so for chains it may differ from where offices operate. The series is the "
                    "number of register entries at month end.",
    },
    "treasury": {
        "ru": "Казначейство России",
        "en": "Federal Treasury of Russia",
        "about_ru": "Источник — Казначейство России, годовые отчёты об исполнении консолидированных бюджетов "
                    "субъектов (форма 0503317, доход «курортный сбор»). Сбор взимали с 2018 по 2024 год в "
                    "Краснодарском, Ставропольском и Алтайском краях, с 2024 — в Санкт-Петербурге; с 2025 года его "
                    "заменил туристический налог.",
        "about_en": "Source: Federal Treasury of Russia, annual reports on regional consolidated budgets (form "
                    "0503317, “resort fee” revenue). The fee was levied in 2018–2024 in Krasnodar, Stavropol and "
                    "Altai territories and from 2024 in St Petersburg; the tourist tax replaced it in 2025.",
    },
    "rosstat_pub": {
        "ru": "Росстат",
        "en": "Rosstat",
        "about_ru": "Источник — Росстат, статистические сборники по субъектам («Туризм в России», «Платное "
                    "обслуживание населения», «Здравоохранение в России», «Торговля в России», «Инвестиции в "
                    "России»). Данные годовые, выходят с новым выпуском сборника.",
        "about_en": "Source: Rosstat statistical yearbooks by region (Tourism in Russia, Paid Services, Healthcare, "
                    "Trade, Investment in Russia). Annual data, updated with each new edition.",
    },
    "rosstat_calc": {
        "ru": "расчёт по данным Росстата",
        "en": "calculated from Rosstat data",
        "about_ru": "Это не официальный показатель Росстата, а расчёт сайта по его данным: ночёвки за год делятся "
                    "на число мест на конец года, умноженное на 365 дней. Места, работающие сезонно, расчёт считает "
                    "открытыми весь год, поэтому у курортных регионов загрузка получается ниже фактической.",
        "about_en": "Not an official Rosstat indicator but the site's calculation from Rosstat data: nights over the "
                    "year divided by year-end bed places times 365 days. Seasonal beds are treated as open all year, "
                    "so resort regions show lower occupancy than in season.",
    },
    "regions": {
        "ru": "оценки органов власти регионов",
        "en": "regional authorities' estimates",
        "about_ru": "Источник — оценка турпотока, которую публикует сам регион (министерство туризма, отчёт по "
                    "госпрограмме, открытые данные; часть лет — со слов чиновников в СМИ). У каждого региона своя "
                    "методика: одни считают только туристов с ночёвкой, другие — всех приезжих, включая однодневных, "
                    "третьи с какого-то года берут оценку Росстата. Регионы между собой не сравнимы; это не ряд "
                    "Росстата.",
        "about_en": "Source: the tourist-flow estimate published by the region itself (tourism ministry, state "
                    "programme report, open data; some years from officials quoted in the media). Each region uses "
                    "its own method: some count only overnight tourists, others all visitors including day "
                    "trippers, others switched to Rosstat's estimate. Regions are not comparable with each other; "
                    "this is not a Rosstat series.",
    },
    "mos": {
        "ru": "Комитет по туризму Москвы (открытые данные)",
        "en": "Moscow City Tourism Committee (open data)",
        "about_ru": "Источник — портал открытых данных Москвы (data.mos.ru): реестр классифицированных средств "
                    "размещения города. Точки — на дату обновления набора (2025 год — на 31 июля).",
        "about_en": "Source: Moscow open data portal (data.mos.ru), register of the city's classified "
                    "accommodation. Points are as of the dataset update date (2025: 31 July).",
    },
    "sber": {
        "ru": "СберИндекс (приближённая оценка)",
        "en": "SberIndex (approximate estimate)",
        "about_ru": "Источник — СберИндекс, оценка по обезличенным операциям клиентов Сбербанка. Это не "
                    "официальная статистика, а приближённая оценка; ряд остановлен источником в апреле 2022 года.",
        "about_en": "Source: SberIndex, an estimate from anonymised Sberbank card transactions. It is not official "
                    "statistics but an approximation; the source stopped the series in April 2022.",
    },
}

SECTION_TOURISM = (6, "Культура, отдых и туризм", "Culture, leisure and tourism")
SECTION_TRANSPORT = (16, "Транспорт", "Transport")
SECTION_PRICES = (20, "Цены и тарифы", "Prices and tariffs")
SECTION_TRADE = (15, "Торговля и услуги населению", "Trade and consumer services")

THOUSAND = 0.001  # человек → тысячи, тысячи рублей → миллионы рублей


@dataclass(frozen=True)
class Emiss:
    """Как ряд взять из набора ЕМИСС — названиями, без oid.

    ``match`` — альтернативы значений прочих измерений (кроме территории, года, периода, единицы): строка
    подходит, если все значения альтернативы есть в строке, а остальные её значения — «итоговые» («Всего»).
    Значение с префиксом ``re:`` — регулярное выражение (без учёта регистра). Первая подошедшая альтернатива
    главнее (у позиции, переименованной Росстатом, — новое название первым).
    """

    dataset: int
    src_unit: str                       # единица на странице набора; другая → набор пропускается (масштаб неверен)
    periods: str = "year"               # 'year' | 'month' | 'ytd' («январь», «январь-февраль», …)
    match: tuple[tuple[str, ...], ...] = ((),)
    seed: bool = True                   # скачано 20.11.2026 и лежит в tourism_seed.csv.gz
    territory_dim: str | None = None    # None — найти по названию («ОКАТО», «Субъекты РФ»)
    # Другие допустимые единицы страницы и масштаб к единице сайта (для наборов, не открытых до бана fedstat).
    alt_units: tuple[tuple[str, float], ...] = ()


@dataclass(frozen=True)
class TSeries:
    code: str
    layer: str                          # 'annual' | 'quarterly' | 'monthly'
    name_ru: str
    name_en: str
    unit_ru: str
    unit_en: str
    note_ru: str
    note_en: str
    source: str                         # ключ SOURCES
    table_code: str
    section: tuple[int, str, str] = SECTION_TOURISM
    transform: str = "level"            # 'level' | 'diff' (нарастающий итог → значение за период)
    scale: float = 1.0
    first_year: int = 2002
    min_year: int | None = None         # писать только с этого года (продление чужого ряда)
    own_metadata: bool = True           # False — метаданные у сборника «Регионы России»
    emiss: Emiss | None = None
    keywords: str = ""
    allow_negative: bool = False


# ---------------------------------------------------------------------------------------------------------------
# Гостиницы и прочие средства размещения: годовые ряды ЕМИСС.

_KSR_RU = ("Коллективные средства размещения — гостиницы, хостелы, базы отдыха, кемпинги, санатории и другие "
           "организации, где останавливаются приезжие. ")
_KSR_EN = ("Collective accommodation: hotels, hostels, holiday centres, campsites, sanatoriums and other places "
           "where visitors stay. ")

ANNUAL_KSR: tuple[TSeries, ...] = (
    TSeries("kollektivnye-sredstva-razmescheniya-chislo-kollektivnyh-sredstv-razmescheniya", "annual", "", "",
            "", "", "", "", "emiss", "6.7.1", first_year=2002, min_year=2025, own_metadata=False,
            emiss=Emiss(31579, "единица")),
    TSeries("kollektivnye-sredstva-razmescheniya-chislennost-razmeschennyh-lits", "annual", "", "",
            "", "", "", "", "emiss", "6.7.2", scale=THOUSAND, first_year=2002, min_year=2025, own_metadata=False,
            emiss=Emiss(31560, "человек")),
    TSeries("tour-ksr-mesta", "annual",
            "Число мест в гостиницах и прочих средствах размещения",
            "Bed places in hotels and other collective accommodation",
            "мест", "bed places",
            _KSR_RU + "Число мест (коек) на конец года.",
            _KSR_EN + "Number of bed places at year end.",
            "emiss", "6.t1", emiss=Emiss(31583, "единица"),
            keywords="сколько мест в гостиницах, коечный фонд, вместимость гостиниц"),
    TSeries("tour-ksr-nomera", "annual",
            "Число номеров в гостиницах и прочих средствах размещения",
            "Rooms in hotels and other collective accommodation",
            "номеров", "rooms",
            _KSR_RU + "Число номеров на конец года.",
            _KSR_EN + "Number of rooms at year end.",
            "emiss", "6.t2", emiss=Emiss(31586, "единица"),
            keywords="номерной фонд, число номеров в гостиницах"),
    TSeries("tour-ksr-nochevki", "annual",
            "Ночёвки в гостиницах и прочих средствах размещения",
            "Nights spent in hotels and other collective accommodation",
            "тысяч ночёвок", "thousand nights",
            _KSR_RU + "Сколько ночей за год провели постояльцы: один гость на три ночи — три ночёвки.",
            _KSR_EN + "Nights spent by guests during the year: one guest staying three nights counts as three.",
            "emiss", "6.t3", scale=THOUSAND, emiss=Emiss(31587, "единица"),
            keywords="ночевки в гостиницах, турпоток, загрузка гостиниц"),
    TSeries("tour-ksr-dohody", "annual",
            "Доходы гостиниц и прочих средств размещения",
            "Revenue of hotels and other collective accommodation",
            "миллионов рублей", "RUB million",
            _KSR_RU + "Доходы от услуг за год без НДС и акцизов.",
            _KSR_EN + "Revenue from services over the year, excluding VAT and excise.",
            "emiss", "6.t4", scale=THOUSAND, emiss=Emiss(31003, "тысяча рублей"),
            keywords="выручка гостиниц, доходы гостиничного бизнеса"),
    TSeries("tour-ksr-zatraty", "annual",
            "Затраты гостиниц и прочих средств размещения",
            "Costs of hotels and other collective accommodation",
            "миллионов рублей", "RUB million",
            _KSR_RU + "Затраты на оказание услуг за год.",
            _KSR_EN + "Costs of providing services over the year.",
            "emiss", "6.t5", scale=THOUSAND, emiss=Emiss(31040, "тысяча рублей")),
    # Не скачаны до бана fedstat 20.11.2026: загрузчик возьмёт их сам, когда доступ вернётся.
    TSeries("tour-ksr-rossiyane", "annual",
            "Граждане России, размещённые в гостиницах и прочих средствах размещения",
            "Russian residents staying in hotels and other collective accommodation",
            "тысяч человек", "thousand people",
            _KSR_RU + "Сколько россиян остановилось за год.",
            _KSR_EN + "Russian residents who stayed during the year.",
            "emiss", "6.t6", scale=THOUSAND, emiss=Emiss(44040, "человек", seed=False)),
    TSeries("tour-ksr-inostrancy", "annual",
            "Иностранцы, размещённые в гостиницах и прочих средствах размещения",
            "Foreign guests in hotels and other collective accommodation",
            "тысяч человек", "thousand people",
            _KSR_RU + "Сколько иностранных граждан остановилось за год.",
            _KSR_EN + "Foreign citizens who stayed during the year.",
            "emiss", "6.t7", scale=THOUSAND, emiss=Emiss(44042, "человек", seed=False),
            keywords="иностранные туристы, въездной туризм"),
    TSeries("tour-ksr-ploshchad-nomerov", "annual",
            "Площадь номерного фонда гостиниц и прочих средств размещения",
            "Floor area of rooms in collective accommodation",
            "тысяч м²", "thousand m²",
            _KSR_RU + "Общая площадь номеров на конец года.",
            _KSR_EN + "Total floor area of rooms at year end.",
            "emiss", "6.t8", emiss=Emiss(44041, "тысяча квадратных метров", seed=False,
                         alt_units=(("квадратный метр", 0.001),))),  # стенд 20.11: на странице «квадратный метр»
    TSeries("tour-gostinicy-nomera-vysshey-kategorii", "annual",
            "Номера высшей категории в гостиницах",
            "Top-category rooms in hotels",
            "номеров", "rooms",
            "Номера высшей категории (сюиты, апартаменты, люксы) в гостиницах на конец года.",
            "Top-category rooms (suites, apartments, de luxe) in hotels at year end.",
            "emiss", "6.t9", emiss=Emiss(57731, "единица", seed=False)),
    TSeries("tour-ksr-nomera-klassificirovannye", "annual",
            "Номера в средствах размещения, прошедших классификацию",
            "Rooms in classified accommodation",
            "номеров", "rooms",
            "Номера в гостиницах и других средствах размещения, которым присвоена категория (звёзды) или "
            "«без звёзд» по итогам классификации.",
            "Rooms in hotels and other accommodation that have been assigned a category (stars or “no stars”) "
            "through classification.",
            "emiss", "6.t10", emiss=Emiss(62159, "единица", seed=False,
                         alt_units=(("тысяча единиц", 1000.0),))),  # стенд 20.11: «тысяча единиц»
)

# ---------------------------------------------------------------------------------------------------------------
# Санатории.

_SAN_RU = "Санаторно-курортные организации — санатории, профилактории, курортные поликлиники и пансионаты с лечением. "
_SAN_EN = "Health resort organisations: sanatoriums, preventive care centres and resort clinics. "

ANNUAL_SANATORIUMS: tuple[TSeries, ...] = (
    TSeries("tour-sanatorii-razmeshcheno", "annual",
            "Отдыхающие в санаториях", "Guests at sanatoriums and health resorts",
            "тысяч человек", "thousand people",
            _SAN_RU + "Сколько человек размещено за год.",
            _SAN_EN + "People accommodated during the year.",
            "emiss", "6.t11", scale=THOUSAND, emiss=Emiss(42102, "человек"),
            keywords="санатории, сколько людей отдыхает в санаториях, санаторно-курортное лечение"),
    TSeries("tour-sanatorii-nochevki", "annual",
            "Ночёвки в санаториях", "Nights spent at sanatoriums and health resorts",
            "тысяч ночёвок", "thousand nights",
            _SAN_RU + "Сколько ночей провели отдыхающие за год.",
            _SAN_EN + "Nights spent by guests during the year.",
            "emiss", "6.t12", scale=THOUSAND, first_year=2005, emiss=Emiss(42103, "единица")),
    TSeries("tour-sanatorii-dohody", "annual",
            "Доходы санаториев", "Revenue of sanatoriums and health resorts",
            "миллионов рублей", "RUB million",
            _SAN_RU + "Доходы от услуг за год без НДС и акцизов.",
            _SAN_EN + "Revenue from services over the year, excluding VAT and excise.",
            "emiss", "6.t13", scale=THOUSAND, first_year=2003, emiss=Emiss(42101, "тысяча рублей")),
    TSeries("tour-sanatorii-nomera", "annual",
            "Число номеров в санаториях", "Rooms at sanatoriums and health resorts",
            "номеров", "rooms",
            _SAN_RU + "Число номеров на конец года.",
            _SAN_EN + "Number of rooms at year end.",
            "emiss", "6.t14", emiss=Emiss(42105, "единица")),
    TSeries("tour-sanatorii-chislo", "annual",
            "Число санаториев", "Number of sanatoriums and health resorts",
            "единиц", "units",
            _SAN_RU + "Число организаций на конец года.",
            _SAN_EN + "Number of organisations at year end.",
            "emiss", "6.t15", emiss=Emiss(42106, "единица", seed=False)),
    TSeries("tour-sanatorii-mesta", "annual",
            "Число мест в санаториях", "Bed places at sanatoriums and health resorts",
            "мест", "bed places",
            _SAN_RU + "Число мест (коек) на конец года.",
            _SAN_EN + "Number of bed places at year end.",
            "emiss", "6.t16", emiss=Emiss(42104, "единица", seed=False)),
)

# ---------------------------------------------------------------------------------------------------------------
# Турфирмы: число по видам деятельности (31615), туристы, отправленные в поездки, по странам (31591),
# иностранцы, принятые турфирмами (31598).

_FIRMS_RU = "Организации и предприниматели, которые продают туры, по данным их годовой отчётности. "
_FIRMS_EN = "Companies and sole proprietors selling tours, from their annual reporting. "


def _firms(code: str, kind: str, name_ru: str, name_en: str, table: str) -> TSeries:
    return TSeries(code, "annual", name_ru, name_en, "единиц", "units",
                   _FIRMS_RU + "Число на конец года.", _FIRMS_EN + "Number at year end.",
                   "emiss", table, first_year=2004, emiss=Emiss(31615, "единица", match=((kind,),)))


_TRAVELLERS_RU = ("Сколько жителей России отправили в поездки турфирмы региона за год, по данным годовой "
                  "отчётности турфирм. Самостоятельные поездки сюда не входят. ")
_TRAVELLERS_EN = ("Russian residents sent on trips by the region's tour companies during the year, from tour "
                  "company reporting. Independent travel is not included. ")


def _travellers(code: str, country: str, name_ru: str, name_en: str, table: str, extra_ru: str = "",
                extra_en: str = "", keywords: str = "") -> TSeries:
    return TSeries(code, "annual", name_ru, name_en, "тысяч человек", "thousand people",
                   _TRAVELLERS_RU + extra_ru, _TRAVELLERS_EN + extra_en, "emiss", table, scale=THOUSAND,
                   first_year=2004, emiss=Emiss(31591, "человек", match=((country,),)), keywords=keywords)


# Направления турфирм по странам (31591, ~250 стран). На сайт — страны, куда турфирмы отправили не меньше 10 тыс.
# человек в каком-то году 2023–2025 или не меньше 50 тыс. в каком-то году с 2004 (крупные направления до 2022 года:
# Греция, Испания, Кипр, Чехия…). Это 36 стран с первыми шестью; хвост из сотни стран с сотнями туристов на страницу
# региона не выносится — он есть в источнике. Сверка по строке России 20.11.2026. Подпись — как у Росстата.
# (slug, подпись Росстата, ru, en, «в …» для поиска, ключевые слова)
DESTINATIONS: tuple[tuple[str, str, str, str, str, str], ...] = (
    ("vetnam", "ВЬЕТНАМ", "Вьетнам", "Vietnam", "Вьетнам", "Нячанг, Фукуок"),
    ("maldivy", "МАЛЬДИВЫ", "Мальдивы", "Maldives", "на Мальдивы", "отдых на Мальдивах"),
    ("shri-lanka", "ШРИ-ЛАНКА", "Шри-Ланка", "Sri Lanka", "Шри-Ланку", "отдых на Шри-Ланке"),
    ("belarus", "БЕЛАРУСЬ", "Беларусь", "Belarus", "Беларусь", "туры в Белоруссию, Минск"),
    ("kuba", "КУБА", "Куба", "Cuba", "на Кубу", "отдых на Кубе"),
    ("indiya", "ИНДИЯ", "Индия", "India", "Индию", "Гоа"),
    ("katar", "КАТАР", "Катар", "Qatar", "Катар", "Доха"),
    ("indoneziya", "ИНДОНЕЗИЯ", "Индонезия", "Indonesia", "Индонезию", "Бали"),
    ("tunis", "ТУНИС", "Тунис", "Tunisia", "Тунис", "отдых в Тунисе"),
    ("kazahstan", "КАЗАХСТАН", "Казахстан", "Kazakhstan", "Казахстан", "туры в Казахстан"),
    ("saudovskaya-araviya", "САУДОВСКАЯ АРАВИЯ", "Саудовская Аравия", "Saudi Arabia", "Саудовскую Аравию",
     "хадж, умра"),
    ("italiya", "ИТАЛИЯ", "Италия", "Italy", "Италию", "отдых в Италии"),
    ("gruziya", "ГРУЗИЯ", "Грузия", "Georgia", "Грузию", "отдых в Грузии"),
    ("seyshely", "СЕЙШЕЛЫ", "Сейшелы", "Seychelles", "на Сейшелы", "отдых на Сейшелах"),
    ("azerbaydzhan", "АЗЕРБАЙДЖАН", "Азербайджан", "Azerbaijan", "Азербайджан", "Баку"),
    ("yaponiya", "ЯПОНИЯ", "Япония", "Japan", "Японию", "туры в Японию"),
    ("uzbekistan", "УЗБЕКИСТАН", "Узбекистан", "Uzbekistan", "Узбекистан", "Самарканд"),
    ("franciya", "ФРАНЦИЯ", "Франция", "France", "Францию", "Париж"),
    ("greciya", "ГРЕЦИЯ", "Греция", "Greece", "Грецию", "отдых в Греции"),
    ("ispaniya", "ИСПАНИЯ", "Испания", "Spain", "Испанию", "отдых в Испании"),
    ("kipr", "КИПР", "Кипр", "Cyprus", "на Кипр", "отдых на Кипре"),
    ("chehiya", "ЧЕХИЯ", "Чехия", "Czech Republic", "Чехию", "Прага"),
    ("bolgariya", "БОЛГАРИЯ", "Болгария", "Bulgaria", "Болгарию", "отдых в Болгарии"),
    ("ukraina", "УКРАИНА", "Украина", "Ukraine", "Украину", "туры на Украину до 2014 года"),
    ("dominikanskaya-respublika", "ДОМИНИКАНСКАЯ РЕСПУБЛИКА", "Доминиканская Республика", "Dominican Republic",
     "Доминикану", "отдых в Доминикане"),
    ("finlyandiya", "ФИНЛЯНДИЯ", "Финляндия", "Finland", "Финляндию", "туры в Финляндию"),
    ("germaniya", "ГЕРМАНИЯ", "Германия", "Germany", "Германию", "туры в Германию"),
    ("izrail", "ИЗРАИЛЬ", "Израиль", "Israel", "Израиль", "туры в Израиль"),
    ("horvatiya", "ХОРВАТИЯ", "Хорватия", "Croatia", "Хорватию", "отдых в Хорватии"),
    ("shveciya", "ШВЕЦИЯ", "Швеция", "Sweden", "Швецию", "туры в Швецию"),
)
# Страны, откуда турфирмы принимали не меньше 50 тыс. иностранцев в каком-то году (31598).
ORIGINS: tuple[tuple[str, str, str, str, str], ...] = (
    ("kitay", "КИТАЙ", "Китай", "China", "Китая"),
    ("ssha", "США,включая Гавайские острова", "США", "the United States", "США"),
    ("germaniya", "ГЕРМАНИЯ", "Германия", "Germany", "Германии"),
    ("finlyandiya", "ФИНЛЯНДИЯ", "Финляндия", "Finland", "Финляндии"),
    ("italiya", "ИТАЛИЯ", "Италия", "Italy", "Италии"),
    ("velikobritaniya", "СОЕДИНЕННОЕ КОРОЛЕВСТВО ВЕЛИКОБРИТАНИИ И СЕВЕРНОЙ ИРЛАНДИИ", "Великобритания",
     "the United Kingdom", "Великобритании"),
    ("franciya", "ФРАНЦИЯ", "Франция", "France", "Франции"),
)

ANNUAL_FIRMS: tuple[TSeries, ...] = (
    TSeries("turistskie-firmy-chislo-turistskih-firm", "annual", "", "", "", "", "", "", "emiss", "6.8.1",
            first_year=2004, min_year=2025, own_metadata=False,
            emiss=Emiss(31615, "единица", match=(("Всего",),))),
    _firms("tour-turfirmy-turoperatory", "Туроператорская", "Число туроператоров",
           "Number of tour operators", "6.t20"),
    _firms("tour-turfirmy-turagenty", "Турагентская", "Число турагентств", "Number of travel agencies", "6.t21"),
    _firms("tour-turfirmy-turoperatory-i-turagenty", "Туроператорская и турагентская",
           "Число турфирм, которые и формируют, и продают туры",
           "Number of companies acting as both tour operator and travel agent", "6.t22"),
    _firms("tour-turfirmy-ekskursii", "Экскурсионная деятельность", "Число экскурсионных фирм",
           "Number of excursion companies", "6.t23"),
    _travellers("tour-turisty-turfirm-vsego", "Всего по странам мира",
                "Туристы, отправленные турфирмами в поездки", "Tourists sent on trips by tour companies", "6.t24",
                "Все направления: по России и за рубеж.", "All destinations: within Russia and abroad.",
                keywords="сколько туристов, турпоток турфирм, проданные туры"),
    _travellers("tour-turisty-turfirm-po-rossii", "РОССИЯ",
                "Туристы, отправленные турфирмами в поездки по России",
                "Tourists sent on domestic trips by tour companies", "6.t25",
                keywords="внутренний туризм, туры по России"),
    _travellers("tour-turisty-turfirm-za-rubezh", "Всего по зарубежным странам",
                "Туристы, отправленные турфирмами за рубеж", "Tourists sent abroad by tour companies", "6.t26",
                keywords="выездной туризм, туры за границу"),
    _travellers("tour-turisty-turfirm-turciya", "ТУРЦИЯ", "Туристы, отправленные турфирмами в Турцию",
                "Tourists sent to Turkey by tour companies", "6.t27", keywords="туры в Турцию, туристы в Турцию"),
    _travellers("tour-turisty-turfirm-egipet", "ЕГИПЕТ", "Туристы, отправленные турфирмами в Египет",
                "Tourists sent to Egypt by tour companies", "6.t28", keywords="туры в Египет"),
    _travellers("tour-turisty-turfirm-oae", "ОБЪЕДИНЕННЫЕ АРАБСКИЕ ЭМИРАТЫ",
                "Туристы, отправленные турфирмами в ОАЭ", "Tourists sent to the UAE by tour companies", "6.t29",
                keywords="туры в ОАЭ, Дубай"),
    _travellers("tour-turisty-turfirm-tailand", "ТАИЛАНД", "Туристы, отправленные турфирмами в Таиланд",
                "Tourists sent to Thailand by tour companies", "6.t30", keywords="туры в Таиланд"),
    _travellers("tour-turisty-turfirm-kitay", "КИТАЙ", "Туристы, отправленные турфирмами в Китай",
                "Tourists sent to China by tour companies", "6.t31", keywords="туры в Китай"),
    _travellers("tour-turisty-turfirm-abhaziya", "АБХАЗИЯ", "Туристы, отправленные турфирмами в Абхазию",
                "Tourists sent to Abkhazia by tour companies", "6.t32", keywords="туры в Абхазию"),
    *(_travellers(f"tour-turisty-turfirm-{slug}", label, f"Туристы, отправленные турфирмами: {ru}",
                  f"Tourists sent by tour companies: {en}", f"6.t{100 + n}", keywords=f"туры в {ru_in}, {ru_kw}")
      for n, (slug, label, ru, en, ru_in, ru_kw) in enumerate(DESTINATIONS)),
    *(TSeries(f"tour-inostrancy-turfirm-{slug}", "annual", f"Иностранные туристы, принятые турфирмами: {ru}",
              f"Foreign tourists served by tour companies: {en}", "человек", "people",
              f"Сколько граждан страны «{ru}» обслужили турфирмы региона за год, по данным годовой отчётности "
              "турфирм.",
              f"Citizens of {en} served by the region's tour companies during the year, from tour company "
              "reporting.",
              "emiss", f"6.t{150 + n}", first_year=2004, emiss=Emiss(31598, "человек", match=((label,),)),
              keywords=f"туристы из {ru_from}, въездной туризм")
      for n, (slug, label, ru, en, ru_from) in enumerate(ORIGINS)),
    TSeries("tour-inostrancy-turfirm", "annual",
            "Иностранные туристы, принятые турфирмами", "Foreign tourists served by tour companies",
            "человек", "people",
            "Сколько иностранных граждан обслужили турфирмы региона за год, по данным годовой отчётности турфирм.",
            "Foreign citizens served by the region's tour companies during the year, from tour company reporting.",
            "emiss", "6.t33", first_year=2004,
            emiss=Emiss(31598, "человек", match=(("Всего по странам мира",),)),
            keywords="въездной туризм, иностранные туристы"),
)

# ---------------------------------------------------------------------------------------------------------------
# Прочие годовые наборы ЕМИСС, ещё не скачанные (бан fedstat 20.11.2026). Структура известна по каталогу ЕМИСС;
# измерения, которые здесь не названы, загрузчик берёт «итоговым» значением («Всего»).

ANNUAL_PENDING: tuple[TSeries, ...] = (
    # 62199 на странице — «миллион рублей» (стенд 20.11.2026): это сама валовая добавленная стоимость туриндустрии,
    # а доля в ВРП — соседний набор 62197 (каталог ЕМИСС: «ВДС туристской индустрии … и доля в ВРП», 62197/62199).
    # Если у 62197 единица окажется не «процент», загрузчик его пропустит и напишет в лог.
    TSeries("tour-vds-turindustrii", "annual",
            "Валовая добавленная стоимость туристской индустрии", "Gross value added of the tourism industry",
            "миллионов рублей", "RUB million",
            "Сколько стоимости за год создали в регионе гостиницы, общепит, турфирмы, перевозчики и другие "
            "отрасли, обслуживающие туристов (оценка Росстата).",
            "Value added during the year by the region's hotels, restaurants, tour companies, carriers and other "
            "industries serving tourists (Rosstat estimate).",
            "emiss", "6.t43", first_year=2019,
            emiss=Emiss(62199, "миллион рублей", seed=False, alt_units=(("тысяча рублей", 0.001),)),
            keywords="ВДС туризма, вклад туризма в экономику региона"),
    TSeries("tour-vds-turindustrii-dolya-vrp", "annual",
            "Доля туристской индустрии в экономике региона", "Tourism industry share of the regional economy",
            "% валового регионального продукта", "% of gross regional product",
            "Какую часть валового регионального продукта создают гостиницы, общепит, турфирмы, перевозчики и "
            "другие отрасли, обслуживающие туристов (оценка Росстата).",
            "Share of gross regional product created by hotels, restaurants, tour companies, carriers and other "
            "industries serving tourists (Rosstat estimate).",
            "emiss", "6.t40", first_year=2019, emiss=Emiss(62197, "процент", seed=False),
            keywords="доля туризма в ВРП, вклад туризма в экономику региона"),
    TSeries("tour-deti-organizacii-otdyha", "annual",
            "Число организаций отдыха и оздоровления детей", "Children's holiday and recreation organisations",
            "единиц", "units",
            "Сколько в регионе работало лагерей и других организаций отдыха и оздоровления детей за год "
            "(загородные, санаторные, палаточные, лагеря при школах). Продолжает закрытый в 2017 году ряд "
            "«детские оздоровительные лагеря».",
            "Children's holiday and recreation organisations operating in the region during the year (country, "
            "sanatorium, tent and school-based camps). Continues the children's camps series closed in 2017.",
            "emiss", "6.t42", first_year=2018, emiss=Emiss(59153, "единица", seed=False),
            keywords="детские лагеря, сколько детских лагерей, летний отдых детей"),
    TSeries("tour-deti-turpoezdki", "annual",
            "Доля школьников, совершивших туристские поездки", "Share of schoolchildren who went on tourist trips",
            "% детей", "% of children",
            "Доля детей, которые за год хотя бы раз съездили в туристскую или экскурсионную поездку, по данным "
            "Росстата и Минпросвещения.",
            "Share of children who went on at least one tourist or excursion trip during the year, Rosstat and "
            "Ministry of Education data.",
            "emiss", "6.t41", first_year=2019, emiss=Emiss(60944, "процент", seed=False)),
)

# ---------------------------------------------------------------------------------------------------------------
# Оперативные помесячные ряды ЕМИСС (нарастающий итог → значение за месяц).

_OPER_RU = " Оперативные данные Росстата; значение за месяц — разность нарастающих итогов «январь–…»."
_OPER_EN = " Preliminary Rosstat data; the monthly value is the difference between year-to-date totals."

MONTHLY_EMISS: tuple[TSeries, ...] = (
    TSeries("tour-ksr-nochevki-mes", "monthly",
            "Ночёвки в гостиницах и прочих средствах размещения за месяц",
            "Nights in hotels and other collective accommodation per month",
            "тысяч ночёвок", "thousand nights",
            _KSR_RU + "Сколько ночей провели постояльцы за месяц." + _OPER_RU,
            _KSR_EN + "Nights spent by guests during the month." + _OPER_EN,
            "emiss", "6.tm1", transform="diff", scale=THOUSAND, first_year=2023,
            emiss=Emiss(62301, "единица", periods="ytd"),
            keywords="загрузка гостиниц по месяцам, ночевки, турпоток по месяцам, сезонность туризма"),
    TSeries("tour-ksr-razmeshcheno-mes", "monthly",
            "Гости гостиниц и прочих средств размещения за месяц",
            "Guests in hotels and other collective accommodation per month",
            "тысяч человек", "thousand people",
            _KSR_RU + "Сколько человек остановилось за месяц." + _OPER_RU,
            _KSR_EN + "People who stayed during the month." + _OPER_EN,
            "emiss", "6.tm2", transform="diff", scale=THOUSAND, first_year=2023,
            emiss=Emiss(62073, "человек", periods="ytd", seed=False),
            keywords="сколько туристов в месяц, постояльцы гостиниц"),
    TSeries("tour-ksr-rossiyane-mes", "monthly",
            "Россияне в гостиницах и прочих средствах размещения за месяц",
            "Russian residents in collective accommodation per month",
            "тысяч человек", "thousand people",
            _KSR_RU + "Сколько граждан России остановилось за месяц." + _OPER_RU,
            _KSR_EN + "Russian residents who stayed during the month." + _OPER_EN,
            "emiss", "6.tm3", transform="diff", scale=THOUSAND, first_year=2023,
            emiss=Emiss(62300, "человек", periods="ytd", seed=False)),
    TSeries("tour-ksr-inostrancy-mes", "monthly",
            "Иностранцы в гостиницах и прочих средствах размещения за месяц",
            "Foreign guests in collective accommodation per month",
            "тысяч человек", "thousand people",
            _KSR_RU + "Сколько иностранных граждан остановилось за месяц." + _OPER_RU,
            _KSR_EN + "Foreign citizens who stayed during the month." + _OPER_EN,
            "emiss", "6.tm4", transform="diff", scale=THOUSAND, first_year=2023,
            emiss=Emiss(62279, "человек", periods="ytd", seed=False),
            keywords="иностранные туристы по месяцам"),
    TSeries("tour-ksr-dohody-mes", "monthly",
            "Доходы гостиниц и прочих средств размещения за месяц",
            "Revenue of collective accommodation per month",
            "миллионов рублей", "RUB million",
            _KSR_RU + "Доходы от услуг без НДС за месяц." + _OPER_RU,
            _KSR_EN + "Revenue from services excluding VAT during the month." + _OPER_EN,
            "emiss", "6.tm5", transform="diff", scale=THOUSAND, first_year=2023,
            emiss=Emiss(62299, "тысяча рублей", periods="ytd", seed=False)),
    TSeries("tour-sanatorii-razmeshcheno-mes", "monthly",
            "Отдыхающие в санаториях за месяц", "Guests at sanatoriums per month",
            "тысяч человек", "thousand people",
            _SAN_RU + "Сколько человек размещено за месяц." + _OPER_RU,
            _SAN_EN + "People accommodated during the month." + _OPER_EN,
            "emiss", "6.tm6", transform="diff", scale=THOUSAND, first_year=2023,
            emiss=Emiss(62074, "человек", periods="ytd", seed=False)),
    TSeries("tour-sanatorii-nochevki-mes", "monthly",
            "Ночёвки в санаториях за месяц", "Nights at sanatoriums per month",
            "тысяч ночёвок", "thousand nights",
            _SAN_RU + "Сколько ночей провели отдыхающие за месяц." + _OPER_RU,
            _SAN_EN + "Nights spent by guests during the month." + _OPER_EN,
            "emiss", "6.tm7", transform="diff", scale=THOUSAND, first_year=2023,
            emiss=Emiss(62302, "единица", periods="ytd", seed=False)),
    TSeries("tour-sanatorii-dohody-mes", "monthly",
            "Доходы санаториев за месяц", "Revenue of sanatoriums per month",
            "миллионов рублей", "RUB million",
            _SAN_RU + "Доходы от услуг без НДС за месяц." + _OPER_RU,
            _SAN_EN + "Revenue from services excluding VAT during the month." + _OPER_EN,
            "emiss", "6.tm8", transform="diff", scale=THOUSAND, first_year=2023,
            emiss=Emiss(62280, "тысяча рублей", periods="ytd", seed=False)),
    TSeries("obshchepit-oborot-mes", "monthly",
            "Оборот общественного питания за месяц", "Food service turnover per month",
            "миллионов рублей", "RUB million",
            "Сколько потратили в ресторанах, кафе, столовых и барах региона за месяц, по оценке Росстата. "
            "Годовой ряд того же показателя — в разделе «Торговля и услуги населению».",
            "Spending in the region's restaurants, cafés, canteens and bars during the month, Rosstat estimate. "
            "The annual series is in the Trade and consumer services section.",
            "emiss", "15.tm1", section=SECTION_TRADE, scale=THOUSAND, first_year=2017,
            emiss=Emiss(31258, "тысяча рублей", periods="month", seed=False,
                        alt_units=(("миллион рублей", 1.0), ("миллиард рублей", 1000.0))),
            keywords="оборот общепита по месяцам, рестораны, кафе"),
    # Платные услуги населению (57788): гостиницы и специализированные средства размещения (базы отдыха,
    # турбазы, санатории без лечения), миллионы рублей за месяц. У гостиниц Росстат в разные годы называл
    # позицию по-разному — обе подписи, новая первой.
    TSeries("tour-platnye-uslugi-gostinicy-mes", "monthly",
            "Платные услуги населению за месяц: гостиницы", "Paid services per month: hotels",
            "миллионов рублей", "RUB million",
            "Сколько жители и приезжие заплатили гостиницам и другим местам временного проживания за месяц. "
            "Оперативные данные Росстата.",
            "What residents and visitors paid hotels and other short-stay accommodation during the month. "
            "Preliminary Rosstat data.",
            "emiss", "6.tm9", scale=THOUSAND, first_year=2017,
            emiss=Emiss(57788, "тысяча рублей", periods="month", match=(
                ("Услуги гостиниц и аналогичные услуги по предоставлению временного жилья",),
                ("Услуги гостиниц и аналогичных средств размещения",))),
            keywords="услуги гостиниц, выручка гостиниц по месяцам, гостиничные услуги"),
    TSeries("tour-platnye-uslugi-specksr-mes", "monthly",
            "Платные услуги населению за месяц: базы отдыха и другие специализированные средства размещения",
            "Paid services per month: holiday centres and other specialised accommodation",
            "миллионов рублей", "RUB million",
            "Сколько заплатили базам и домам отдыха, турбазам, детским лагерям и другим специализированным "
            "средствам размещения за месяц. Оперативные данные Росстата.",
            "Payments to holiday centres, tourist bases, children's camps and other specialised accommodation "
            "during the month. Preliminary Rosstat data.",
            "emiss", "6.tm10", scale=THOUSAND, first_year=2017,
            emiss=Emiss(57788, "тысяча рублей", periods="month",
                        match=(("Услуги специализированных коллективных средств размещения",),)),
            keywords="базы отдыха, турбазы, дома отдыха"),
)

# ---------------------------------------------------------------------------------------------------------------
# Транспорт: речные и морские пассажиры (с 2025 года, нарастающий итог), автобусы (месяц).

_WATER_RU = "Пассажиры внутреннего водного (речного) транспорта, перевезённые за месяц; по субъекту, где начат рейс."
_WATER_EN = "Passengers carried by inland waterway (river) transport during the month, by region where the trip began."

MONTHLY_TRANSPORT: tuple[TSeries, ...] = (
    TSeries("tour-rechnye-passazhiry-turisticheskie", "monthly",
            "Пассажиры речных туристских маршрутов (круизы) за месяц",
            "River cruise passengers per month",
            "тысяч человек", "thousand people",
            _WATER_RU + " Туристские маршруты — многодневные круизы." + _OPER_RU,
            _WATER_EN + " Tourist routes are multi-day cruises." + _OPER_EN,
            "emiss", "6.tm11", transform="diff", scale=THOUSAND, first_year=2025,
            emiss=Emiss(62999, "человек", periods="ytd", match=(("Всего", "туристские"),)),
            keywords="речные круизы, сколько туристов в круизах, теплоходы"),
    TSeries("tour-rechnye-passazhiry-ekskursionnye", "monthly",
            "Пассажиры речных экскурсионно-прогулочных маршрутов за месяц",
            "River sightseeing passengers per month",
            "тысяч человек", "thousand people",
            _WATER_RU + " Экскурсионно-прогулочные маршруты — речные прогулки и экскурсии." + _OPER_RU,
            _WATER_EN + " Sightseeing routes are river walks and excursions." + _OPER_EN,
            "emiss", "6.tm12", transform="diff", scale=THOUSAND, first_year=2025,
            emiss=Emiss(62999, "человек", periods="ytd", match=(("Всего", "экскурсионно-прогулочные"),)),
            keywords="речные прогулки, теплоходные экскурсии"),
    TSeries("tour-rechnye-passazhiry", "monthly",
            "Пассажиры речного транспорта за месяц", "Inland waterway passengers per month",
            "тысяч человек", "thousand people",
            _WATER_RU + " Все маршруты: транспортные, туристские, экскурсионные." + _OPER_RU,
            _WATER_EN + " All routes: regular, tourist and sightseeing." + _OPER_EN,
            "emiss", "16.tm1", section=SECTION_TRANSPORT, transform="diff", scale=THOUSAND, first_year=2025,
            emiss=Emiss(62999, "человек", periods="ytd", match=(("Всего", "Всего"),))),
    TSeries("tour-morskie-passazhiry", "monthly",
            "Пассажиры морского транспорта за месяц", "Sea transport passengers per month",
            "тысяч человек", "thousand people",
            "Пассажиры морских судов (паромы, морские прогулки и круизы), перевезённые за месяц, по субъекту, "
            "где начат рейс." + _OPER_RU,
            "Passengers carried by sea (ferries, sea trips and cruises) during the month, by region where the trip "
            "began." + _OPER_EN,
            "emiss", "16.tm2", section=SECTION_TRANSPORT, transform="diff", scale=THOUSAND, first_year=2025,
            emiss=Emiss(63001, "человек", periods="ytd", match=(("Всего",),)),
            keywords="паромы, морские перевозки пассажиров"),
    TSeries("avtobusy-passazhiry-mes", "monthly",
            "Пассажиры автобусов регулярных маршрутов за месяц", "Scheduled bus passengers per month",
            "тысяч человек", "thousand people",
            "Сколько пассажиров перевезли автобусы по регулярным маршрутам (городским, пригородным, "
            "междугородным) за месяц. Данные Росстата.",
            "Passengers carried by scheduled buses (urban, suburban and intercity) during the month. Rosstat data.",
            "emiss", "16.tm3", section=SECTION_TRANSPORT, first_year=2017,
            emiss=Emiss(57714, "тысяча человек", periods="month"),
            keywords="перевозки пассажиров автобусами, автобусы"),
)

# ---------------------------------------------------------------------------------------------------------------
# ИПЦ туристских позиций (31074), «к тому же месяцу прошлого года». Набор не скачан до бана: подписи позиций
# взяты из средних цен 31448 (тот же справочник товаров и услуг 58273), поэтому сравнение — регулярным выражением
# по началу названия.

_CPI_KIND = "re:^к соответствующему периоду предыдущего года"
_CPI_RU = ("Во сколько процентов от цены год назад стоит услуга сейчас: 110 — подорожала на 10 % за год. "
           "Данные Росстата.")
_CPI_EN = "Current price as a percentage of the same month a year earlier: 110 means 10% dearer. Rosstat data."


def _cpi(code: str, pattern: str, name_ru: str, name_en: str, table: str, keywords: str) -> TSeries:
    return TSeries(code, "monthly", f"Индекс потребительских цен за год: {name_ru}",
                   f"Consumer price index, year on year: {name_en}",
                   "% к тому же месяцу прошлого года", "% of same month a year earlier",
                   _CPI_RU, _CPI_EN, "emiss", table, section=SECTION_PRICES, first_year=2017,
                   emiss=Emiss(31074, "процент", periods="month", match=((f"re:{pattern}", _CPI_KIND),), seed=False),
                   keywords=keywords)


MONTHLY_CPI: tuple[TSeries, ...] = (
    _cpi("tour-ipc-gostinicy", r"^услуги гостиниц", "гостиницы", "hotels", "20.ct1",
         "подорожание гостиниц, цены на гостиницы"),
    _cpi("tour-ipc-gostinica-3", r"^проживание в гостинице 3\*", "гостиница 3*", "3-star hotel", "20.ct2",
         "цена гостиницы 3 звезды"),
    _cpi("tour-ipc-sanatorii", r"^санаторно-оздоровительные услуги", "санаторно-оздоровительные услуги",
         "health resort services", "20.ct3", "подорожание санаториев, цены на санатории"),
    _cpi("tour-ipc-sanatoriy-den", r"^санаторий", "санаторий", "sanatorium", "20.ct4", "цена санатория"),
    _cpi("tour-ipc-ekskursii", r"^экскурсионн", "экскурсионные услуги", "excursions", "20.ct5",
         "цены на экскурсии"),
    _cpi("tour-ipc-chernomore", r"^поездка на черноморское побережье", "поездка на Черноморское побережье",
         "trip to the Black Sea coast", "20.ct6", "цена поездки на море, отдых на Черном море"),
    _cpi("tour-ipc-turciya", r"^поездка на отдых в турцию", "поездка в Турцию", "trip to Turkey", "20.ct7",
         "подорожание туров в Турцию"),
)

# ---------------------------------------------------------------------------------------------------------------
# Не ЕМИСС.

TURPOTOK: tuple[TSeries, ...] = (
    TSeries("tour-turpotok-poezdki", "annual",
            "Турпоток: число туристских поездок (оценка Росстата)", "Tourist flow: tourist trips (Rosstat estimate)",
            "тысяч поездок", "thousand trips",
            "Сколько туристских поездок с ночёвкой совершили в регион за год — жители других регионов и "
            "иностранцы, по оценке Росстата. Это другая оценка, чем «турпоездки с начала года» по месяцам: "
            "у неё шире охват (170 млн поездок по России за 2025 год против 92 млн).",
            "Overnight tourist trips to the region during the year by residents of other regions and foreigners, "
            "Rosstat estimate. This estimate is broader than the monthly “tourist trips, year to date” series "
            "(170 million trips across Russia in 2025 versus 92 million).",
            "rosstat_turpotok", "6.t50", scale=THOUSAND, first_year=2022,
            keywords="турпоток, туристический поток, сколько туристов приезжает, туристы в регионе за год"),
    TSeries("tour-turpotok-nochevki", "annual",
            "Турпоток: ночёвки туристов (оценка Росстата)", "Tourist flow: nights spent (Rosstat estimate)",
            "тысяч ночёвок", "thousand nights",
            "Сколько ночей провели в регионе туристы за год, по оценке Росстата (гостиницы, съёмное жильё, "
            "родственники и знакомые).",
            "Nights spent by tourists in the region during the year, Rosstat estimate (hotels, rentals, friends "
            "and relatives).",
            "rosstat_turpotok", "6.t51", scale=THOUSAND, first_year=2022, keywords="турпоток по ночевкам"),
    TSeries("tour-turpotok-poezdki-kv", "quarterly",
            "Турпоток за квартал: туристские поездки (оценка Росстата)",
            "Tourist flow per quarter: tourist trips (Rosstat estimate)",
            "тысяч поездок", "thousand trips",
            "Сколько туристских поездок с ночёвкой совершили в регион за квартал, по оперативной оценке Росстата "
            "(разность нарастающих итогов). Сумма кварталов может не совпадать с годовой оценкой: годовую Росстат "
            "считает позже и полнее.",
            "Overnight tourist trips to the region during the quarter, Rosstat preliminary estimate (difference of "
            "year-to-date totals). Quarters may not add up to the annual estimate, which is compiled later.",
            "rosstat_turpotok", "6.q1", transform="diff", scale=THOUSAND, first_year=2022,
            keywords="турпоток по кварталам, туристы летом"),
    TSeries("tour-turpotok-nochevki-kv", "quarterly",
            "Турпоток за квартал: ночёвки туристов (оценка Росстата)",
            "Tourist flow per quarter: nights spent (Rosstat estimate)",
            "тысяч ночёвок", "thousand nights",
            "Сколько ночей провели в регионе туристы за квартал, по оперативной оценке Росстата (разность "
            "нарастающих итогов).",
            "Nights spent by tourists in the region during the quarter, Rosstat preliminary estimate (difference "
            "of year-to-date totals).",
            "rosstat_turpotok", "6.q2", transform="diff", scale=THOUSAND, first_year=2023),
)

_CBR_EXP_RU = ("Сколько потратили в регионе иностранцы за квартал: проживание, питание, покупки, экскурсии и "
               "лечение во время поездок (экспорт услуг по статье «Поездки»). ")
_CBR_EXP_EN = ("Spending by foreign visitors in the region during the quarter: accommodation, food, shopping, "
               "excursions and treatment (exports of services, “Travel”). ")
_CBR_IMP_RU = ("Сколько потратили жители региона в зарубежных поездках за квартал (импорт услуг по статье "
               "«Поездки»). ")
_CBR_IMP_EN = "Spending by the region's residents on trips abroad during the quarter (imports of services, “Travel”). "


def _cbr(code: str, name_ru: str, name_en: str, lead_ru: str, lead_en: str, tail_ru: str, tail_en: str,
         table: str, keywords: str = "") -> TSeries:
    return TSeries(code, "quarterly", name_ru, name_en, "миллионов долларов США", "US$ million",
                   lead_ru + tail_ru, lead_en + tail_en, "cbr", table, first_year=2019, keywords=keywords)


QUARTERLY_CBR: tuple[TSeries, ...] = (
    _cbr("tour-cbr-poezdki-eksport", "Траты иностранцев в регионе", "Foreign visitors' spending in the region",
         _CBR_EXP_RU, _CBR_EXP_EN, "Все цели поездок.", "All purposes of travel.", "6.q10",
         "сколько тратят иностранные туристы, въездной туризм"),
    _cbr("tour-cbr-poezdki-eksport-delovye", "Траты иностранцев в регионе: деловые поездки",
         "Foreign visitors' spending in the region: business travel",
         _CBR_EXP_RU, _CBR_EXP_EN, "Только деловые поездки.", "Business travel only.", "6.q11"),
    _cbr("tour-cbr-poezdki-eksport-lichnye", "Траты иностранцев в регионе: личные поездки",
         "Foreign visitors' spending in the region: personal travel",
         _CBR_EXP_RU, _CBR_EXP_EN, "Личные поездки: отдых, лечение, учёба, к родственникам.",
         "Personal travel: holidays, treatment, study, visiting relatives.", "6.q12"),
    _cbr("tour-cbr-turuslugi-eksport", "Туристские услуги иностранцам в регионе",
         "Tourism services sold to foreigners in the region",
         "Сколько иностранцы заплатили турфирмам и гостиницам региона за туристские услуги за квартал "
         "(справочная строка статьи «Поездки»). ",
         "Payments by foreigners to the region's tour companies and hotels for tourism services during the "
         "quarter (memo line of “Travel”). ", "", "", "6.q13"),
    _cbr("tour-cbr-poezdki-import", "Траты жителей региона в зарубежных поездках",
         "The region's residents' spending on trips abroad",
         _CBR_IMP_RU, _CBR_IMP_EN, "Все цели поездок.", "All purposes of travel.", "6.q14",
         "сколько тратят туристы за границей, выездной туризм"),
    _cbr("tour-cbr-poezdki-import-delovye", "Траты жителей региона в зарубежных поездках: деловые",
         "The region's residents' spending abroad: business travel",
         _CBR_IMP_RU, _CBR_IMP_EN, "Только деловые поездки.", "Business travel only.", "6.q15"),
    _cbr("tour-cbr-poezdki-import-lichnye", "Траты жителей региона в зарубежных поездках: личные",
         "The region's residents' spending abroad: personal travel",
         _CBR_IMP_RU, _CBR_IMP_EN, "Личные поездки: отдых, лечение, учёба, к родственникам.",
         "Personal travel: holidays, treatment, study, visiting relatives.", "6.q16"),
    _cbr("tour-cbr-turuslugi-import", "Зарубежные туристские услуги, купленные жителями региона",
         "Foreign tourism services bought by the region's residents",
         "Сколько жители региона заплатили зарубежным турфирмам и гостиницам за туристские услуги за "
         "квартал (справочная строка статьи «Поездки»). ",
         "Payments by the region's residents to foreign tour companies and hotels during the quarter (memo line "
         "of “Travel”). ", "", "", "6.q17"),
)

TAX: tuple[TSeries, ...] = (
    TSeries("tour-nalog-s-nachala-goda", "monthly",
            "Туристический налог: поступило с начала года", "Tourist tax received, year to date",
            "миллионов рублей с начала года", "RUB million, year to date",
            "Сколько туристического налога поступило в бюджеты региона с начала года по указанный месяц. "
            "Гостиницы платят налог раз в квартал, поэтому ряд растёт ступеньками; сравнивайте с тем же месяцем "
            "прошлого года. Налог введён с 2025 года.",
            "Tourist tax paid into the region's budgets from the start of the year up to the month. "
            "Accommodation providers pay quarterly, so the series rises in steps; compare with the same month a "
            "year earlier. The tax exists since 2025.",
            "fns", "6.tm20", scale=THOUSAND, first_year=2025,
            keywords="туристический налог, турналог, сколько собрали туристического налога"),
    TSeries("tour-nalog-za-god", "annual",
            "Туристический налог за год", "Tourist tax received per year",
            "миллионов рублей", "RUB million",
            "Сколько туристического налога поступило в бюджеты региона за год. Налог введён с 2025 года "
            "вместо курортного сбора; в Москве и Крыму в 2025 году его не было.",
            "Tourist tax paid into the region's budgets during the year. The tax replaced the resort fee in 2025; "
            "Moscow and Crimea did not levy it in 2025.",
            "fns", "6.t60", scale=THOUSAND, first_year=2025, keywords="туристический налог за год"),
)

REGISTRIES: tuple[TSeries, ...] = (
    TSeries("tour-reestr-ksr", "monthly",
            "Классифицированные средства размещения в реестре", "Classified accommodation in the register",
            "объектов", "properties",
            "Сколько гостиниц, баз отдыха, гостевых домов, кемпингов и санаториев с действующей классификацией "
            "числится в реестре Росаккредитации на дату загрузки в этом месяце (у текущего месяца — на день "
            "последнего обновления, не на конец месяца). Работать без классификации средствам "
            "размещения закон не разрешает, поэтому число близко к легальному номерному фонду региона.",
            "Hotels, holiday centres, guest houses, campsites and sanatoriums with a valid classification in the "
            "Rosaccreditation register on the load date in that month (for the current month, the latest update, not "
            "month end). The law does not allow accommodation to operate without "
            "classification, so this is close to the region's legal accommodation stock.",
            "fsa", "6.tm30", first_year=2026, keywords="реестр гостиниц, сколько гостиниц в регионе, классификация гостиниц"),
    TSeries("tour-reestr-ksr-novye", "annual",
            "Новые записи в реестре средств размещения за год", "New accommodation register entries per year",
            "объектов", "properties",
            "Сколько гостиниц и других средств размещения внесли в реестр Росаккредитации за год (после "
            "классификации). Реестр ведётся с конца 2022 года.",
            "Hotels and other accommodation entered into the Rosaccreditation register during the year (after "
            "classification). The register started at the end of 2022.",
            "fsa", "6.t61", first_year=2023),
    TSeries("tour-reestr-turagenty", "monthly",
            "Турагенты в федеральном реестре", "Travel agents in the federal register",
            "организаций и предпринимателей", "companies and sole proprietors",
            "Сколько турагентов из региона числится в едином федеральном реестре на дату загрузки в этом месяце. "
            "Регион — по месту налогового учёта.",
            "Travel agents from the region listed in the federal register on the load date in that month. The region "
            "is where the agent is registered for tax.",
            "minec", "6.tm31", first_year=2026, keywords="реестр турагентов, сколько турагентств"),
    TSeries("tour-reestr-turoperatory", "monthly",
            "Туроператоры в федеральном реестре", "Tour operators in the federal register",
            "организаций", "companies",
            "Сколько туроператоров из региона числится в едином федеральном реестре на дату загрузки в этом "
            "месяце. Регион — по месту регистрации компании (код субъекта в ОГРН).",
            "Tour operators from the region listed in the federal register on the load date in that month. The "
            "region is where the company is registered (region code in its registration number).",
            "minec", "6.tm33", first_year=2026, keywords="реестр туроператоров, сколько туроператоров"),
    TSeries("tour-sber-vnutrennie-turisty", "monthly",
            "Внутренние туристы: изменение к прошлому году (СберИндекс)",
            "Domestic tourists, change on a year earlier (SberIndex)",
            "% к тому же месяцу прошлого года", "% change on same month a year earlier",
            "Насколько больше или меньше туристов из других регионов приехало, чем год назад, по оценке "
            "СберИндекса из обезличенных операций по картам. Приближённая оценка, не официальная статистика; "
            "источник остановил ряд в апреле 2022 года.",
            "How many more or fewer visitors from other regions came than a year earlier, SberIndex estimate from "
            "anonymised card transactions. An approximation, not official statistics; discontinued in April 2022.",
            "sber", "6.tm32", first_year=2019, allow_negative=True),
)

# ---------------------------------------------------------------------------------------------------------------
# Доработка 20.11.2026 (сборщик c4): курортный сбор, сборники Росстата по субъектам, расчёт загрузки мест.

_PUB = "rosstat_pub"


def _pub(code: str, name_ru: str, name_en: str, unit_ru: str, unit_en: str, note_ru: str, note_en: str, table: str,
         first_year: int, section: tuple[int, str, str] = SECTION_TOURISM, keywords: str = "",
         allow_negative: bool = False) -> TSeries:
    return TSeries(code, "annual", name_ru, name_en, unit_ru, unit_en, note_ru, note_en, _PUB, table,
                   section=section, first_year=first_year, keywords=keywords, allow_negative=allow_negative)


_IPC_DEC_RU = "Во сколько процентов от цены декабря прошлого года стоили услуги в декабре: 110 — подорожали на 10 %."
_IPC_DEC_EN = "December prices as a percentage of December a year earlier: 110 means 10% dearer."
_IFO_RU = ("Насколько изменился объём платных услуг за год без учёта роста цен: 105 — люди купили на 5 % больше "
           "услуг, чем годом раньше.")
_IFO_EN = "Change in paid services over the year at constant prices: 105 means 5% more services than a year earlier."

PUBLICATIONS: tuple[TSeries, ...] = (
    TSeries("tour-kurortnyy-sbor", "annual", "Курортный сбор", "Resort fee",
            "миллионов рублей", "RUB million",
            "Сколько курортного сбора поступило в бюджет региона за год. Сбор был экспериментом 2018–2024 годов "
            "(Краснодарский, Ставропольский и Алтайский края, с 2024 года — Санкт-Петербург); с 2025 года его "
            "заменил туристический налог. Поступления федеральной территории «Сириус» в ряды субъектов не входят.",
            "Resort fee paid into the region's budget during the year. The fee was an experiment in 2018–2024 "
            "(Krasnodar, Stavropol and Altai territories, St Petersburg from 2024); the tourist tax replaced it in "
            "2025. Receipts of the Sirius federal territory are not included in regional series.",
            "treasury", "6.t70", scale=1e-6, first_year=2018, keywords="курортный сбор, сколько собрали курортного сбора"),
    _pub("tour-gostinicy-chislo", "Число гостиниц", "Number of hotels", "единиц", "units",
         "Гостиницы, мотели и апарт-отели на конец года (без хостелов, санаториев и баз отдыха).",
         "Hotels, motels and apart-hotels at year end (excluding hostels, sanatoriums and holiday centres).",
         "6.t71", 2018, keywords="сколько гостиниц в регионе, отели"),
    _pub("tour-gostinicy-nomera", "Число номеров в гостиницах", "Hotel rooms", "номеров", "rooms",
         "Номера в гостиницах на конец года.", "Hotel rooms at year end.", "6.t72", 2018),
    _pub("tour-gostinicy-mesta", "Число мест в гостиницах", "Hotel bed places", "мест", "bed places",
         "Места (койки) в гостиницах на конец года.", "Hotel bed places at year end.", "6.t73", 2018),
    _pub("tour-hostely-chislo", "Число хостелов", "Number of hostels", "единиц", "units",
         "Хостелы на конец года.", "Hostels at year end.", "6.t74", 2018, keywords="хостелы"),
    _pub("tour-hostely-mesta", "Число мест в хостелах", "Hostel bed places", "мест", "bed places",
         "Места в хостелах на конец года.", "Hostel bed places at year end.", "6.t75", 2018),
    _pub("tour-organizacii-otdyha-chislo", "Число баз и домов отдыха", "Holiday centres and rest homes",
         "единиц", "units",
         "Организации отдыха — базы и дома отдыха, турбазы, пансионаты без лечения — на конец года.",
         "Holiday organisations (holiday centres, rest homes, tourist bases, boarding houses without treatment) at "
         "year end.", "6.t76", 2010, keywords="базы отдыха, дома отдыха, турбазы"),
    _pub("tour-organizacii-otdyha-mesta", "Число мест в базах и домах отдыха", "Bed places in holiday centres",
         "мест", "bed places", "Места в организациях отдыха на конец года.",
         "Bed places in holiday organisations at year end.", "6.t77", 2018),
    _pub("tour-sanatorii-v-uzkom-smysle", "Число санаториев (без профилакториев)",
         "Number of sanatoriums (excluding preventive care centres)", "единиц", "units",
         "Санатории как учреждения лечения на конец года, по данным сборника «Здравоохранение в России». "
         "Санаторно-курортных организаций в целом больше: туда входят профилактории и курортные поликлиники.",
         "Sanatoriums as treatment facilities at year end, from the Healthcare in Russia yearbook. Health resort "
         "organisations as a whole are more numerous: they include preventive care centres and resort clinics.",
         "6.t78", 2010),
    _pub("tour-sanatorii-detskie", "Число детских санаториев", "Number of children's sanatoriums", "единиц", "units",
         "Санатории для детей на конец года.", "Children's sanatoriums at year end.", "6.t79", 2010,
         keywords="детские санатории"),
    _pub("tour-sanatorii-profilaktorii", "Число санаториев-профилакториев", "Number of preventive care sanatoriums",
         "единиц", "units", "Санатории-профилактории (обычно при предприятиях) на конец года.",
         "Preventive care sanatoriums (usually run by employers) at year end.", "6.t80", 2010),
    _pub("tour-platnye-uslugi-gostinicy", "Платные услуги гостиниц за год", "Paid hotel services per year",
         "миллионов рублей", "RUB million",
         "Сколько жители и приезжие заплатили гостиницам и другим местам временного проживания за год.",
         "What residents and visitors paid hotels and other short-stay accommodation during the year.",
         "6.t81", 2010, keywords="выручка гостиниц за год"),
    _pub("tour-platnye-uslugi-sanatorii", "Платные услуги санаториев за год", "Paid health resort services per year",
         "миллионов рублей", "RUB million", "Сколько заплатили санаторно-курортным организациям за год.",
         "Payments to health resort organisations during the year.", "6.t82", 2010),
    _pub("tour-platnye-uslugi-specksr", "Платные услуги баз отдыха и других специализированных средств размещения "
         "за год", "Paid services of holiday centres and other specialised accommodation per year",
         "миллионов рублей", "RUB million",
         "Сколько заплатили базам и домам отдыха, турбазам, детским лагерям за год.",
         "Payments to holiday centres, tourist bases and children's camps during the year.", "6.t83", 2020),
    _pub("tour-platnye-turistskie-uslugi", "Платные туристские услуги за год", "Paid tourism services per year",
         "миллионов рублей", "RUB million",
         "Сколько население заплатило турфирмам и туроператорам за год (ряд Росстат вёл до 2022 года).",
         "Payments by the population to tour companies during the year (Rosstat kept the series until 2022).",
         "6.t84", 2010, keywords="турагентства, продажи туров"),
    _pub("tour-ifo-gostinicy", "Платные услуги гостиниц: изменение объёма за год", "Hotel services, volume change",
         "% к предыдущему году", "% of previous year", _IFO_RU, _IFO_EN, "6.t85", 2010),
    _pub("tour-ifo-sanatorii", "Платные услуги санаториев: изменение объёма за год",
         "Health resort services, volume change", "% к предыдущему году", "% of previous year", _IFO_RU, _IFO_EN,
         "6.t86", 2010),
    _pub("tour-ifo-specksr", "Платные услуги баз отдыха: изменение объёма за год",
         "Holiday centre services, volume change", "% к предыдущему году", "% of previous year", _IFO_RU, _IFO_EN,
         "6.t87", 2020),
    _pub("tour-ifo-turistskie", "Платные туристские услуги: изменение объёма за год",
         "Tourism services, volume change", "% к предыдущему году", "% of previous year", _IFO_RU, _IFO_EN,
         "6.t88", 2010),
    _pub("tour-ipc-gostinicy-dek", "Индекс цен на услуги гостиниц за год (декабрь к декабрю)",
         "Hotel price index, December on December", "% к декабрю прошлого года", "% of December a year earlier",
         _IPC_DEC_RU, _IPC_DEC_EN, "20.ct10", 2010, section=SECTION_PRICES, keywords="подорожание гостиниц за год"),
    _pub("tour-ipc-sanatorii-dek", "Индекс цен на санаторно-оздоровительные услуги за год (декабрь к декабрю)",
         "Health resort price index, December on December", "% к декабрю прошлого года",
         "% of December a year earlier", _IPC_DEC_RU, _IPC_DEC_EN, "20.ct11", 2010, section=SECTION_PRICES),
    _pub("tour-ipc-vnutrenniy-turizm-dek", "Индекс цен на внутренний туризм за год (декабрь к декабрю)",
         "Domestic tourism price index, December on December", "% к декабрю прошлого года",
         "% of December a year earlier", _IPC_DEC_RU, _IPC_DEC_EN, "20.ct12", 2022, section=SECTION_PRICES),
    _pub("tour-ipc-zarubezhnyy-turizm-dek", "Индекс цен на зарубежный туризм за год (декабрь к декабрю)",
         "Outbound tourism price index, December on December", "% к декабрю прошлого года",
         "% of December a year earlier", _IPC_DEC_RU, _IPC_DEC_EN, "20.ct13", 2022, section=SECTION_PRICES),
    _pub("obshchepit-restorany", "Число ресторанов, кафе и баров", "Restaurants, cafés and bars",
         "единиц", "units", "Рестораны, кафе и бары на конец года (сборник «Торговля в России»).",
         "Restaurants, cafés and bars at year end (Trade in Russia yearbook).", "15.t1", 2022, section=SECTION_TRADE,
         keywords="сколько ресторанов и кафе в регионе"),
    _pub("obshchepit-stolovye", "Число общедоступных столовых и закусочных", "Public canteens and snack bars",
         "единиц", "units", "Общедоступные столовые и закусочные на конец года.",
         "Public canteens and snack bars at year end.", "15.t2", 2022, section=SECTION_TRADE),
    _pub("obshchepit-rezultat-restorany", "Прибыль минус убыток ресторанов", "Restaurants' net financial result",
         "миллионов рублей", "RUB million",
         "Сальдированный финансовый результат организаций «рестораны и доставка еды» за год: прибыль "
         "прибыльных минус убыток убыточных.",
         "Net financial result of restaurant and food delivery companies over the year: profits minus losses.",
         "15.t3", 2020, section=SECTION_TRADE, allow_negative=True),
    _pub("tour-investicii-gostinicy-restorany", "Инвестиции в гостиницы и рестораны",
         "Investment in hotels and restaurants", "миллионов рублей", "RUB million",
         "Инвестиции в основной капитал по виду деятельности «гостиницы и общепит» за год.",
         "Fixed capital investment in accommodation and food services during the year.", "6.t92", 2022,
         keywords="инвестиции в туризм, строительство гостиниц"),
    TSeries("tour-cena-kupe-nefirmennyy", "monthly",
            "Средняя цена: проезд в купейном вагоне нефирменного скорого поезда, 100 км",
            "Average price: compartment car of a regular express train, per 100 km",
            "рублей за 100 км пути", "RUB per 100 km",
            "Средняя цена проезда в купе скорого нефирменного поезда дальнего следования в расчёте на 100 км, "
            "на конец месяца. Данные Росстата.",
            "Average fare in a compartment car of a regular long-distance express train per 100 km, at month end. "
            "Rosstat data.", _PUB, "20.ct20", section=SECTION_PRICES, first_year=2022,
            keywords="цена билета на поезд, купе"),
    TSeries("tour-cena-plackart-nefirmennyy", "monthly",
            "Средняя цена: проезд в плацкартном вагоне нефирменного скорого поезда, 100 км",
            "Average price: open-plan sleeper of a regular express train, per 100 km",
            "рублей за 100 км пути", "RUB per 100 km",
            "Средняя цена проезда в плацкарте скорого нефирменного поезда дальнего следования в расчёте на 100 "
            "км, на конец месяца. Данные Росстата.",
            "Average fare in an open-plan sleeper car of a regular long-distance express train per 100 km, at "
            "month end. Rosstat data.", _PUB, "20.ct21", section=SECTION_PRICES, first_year=2022,
            keywords="цена плацкарта"),
    TSeries("tour-ksr-zagruzka-mest", "annual", "Загрузка мест в гостиницах и прочих средствах размещения (расчёт)",
            "Bed occupancy in collective accommodation (calculated)", "% мест", "% of bed places",
            "Какая доля мест была занята в среднем за год. Формула: ночёвки за год во всех гостиницах, санаториях, "
            "базах отдыха и прочих коллективных средствах размещения (набор 31587) / (места на конец года, набор "
            "31583, × 365) × 100. Сезонные места считаются открытыми весь год, поэтому у курортов (Краснодарский "
            "край, Крым) загрузка в сезон занижена, а у городов с круглогодичным спросом — нет; сравнивать регионы "
            "по этому числу нельзя, рейтинга нет. Расчёт по данным Росстата, не официальный показатель.",
            "Average share of bed places occupied over the year. Formula: nights in all hotels, sanatoriums, holiday "
            "centres and other collective accommodation (dataset 31587) / (year-end bed places, dataset 31583, × 365) "
            "× 100. Seasonal beds are treated as open all year, so resorts (Krasnodar, Crimea) look underused while "
            "year-round cities do not; regions should not be compared by this figure and there is no ranking. "
            "Calculated from Rosstat data, not an official indicator.",
            "rosstat_calc", "6.t93", first_year=2002, keywords="загрузка гостиниц, заполняемость отелей"),
)

# Добор 20.11.2026 (g2): оценки турпотока самих регионов и реестр размещения Москвы. Сравнивать регионы по ним
# нельзя, поэтому рейтинга регионов у этих рядов нет (NOT_RANKED); методика региона — в tourism_region_methods.json.
REGIONAL_ESTIMATES: tuple[TSeries, ...] = (
    TSeries("tour-turpotok-ocenka-regiona", "annual", "Турпоток по оценке региона",
            "Tourist flow, regional estimate", "тысяч человек", "thousand people",
            "Сколько туристов приняли за год по оценке самого региона. Методика у каждого региона своя (с ночёвкой, "
            "все приезжие, оценка Росстата), её описание и годы смены методики — на странице региона. С оценкой "
            "турпотока Росстата и между регионами эти цифры не сравнимы. Москва — открытые данные Комитета по "
            "туризму.",
            "Tourists received during the year according to the region's own estimate. Each region has its own "
            "method (overnight stays, all visitors, Rosstat's estimate); the method and the years it changed are "
            "described on the region page. Not comparable with Rosstat's tourist flow or across regions. Moscow — "
            "open data of the City Tourism Committee.",
            "regions", "6.t95", scale=THOUSAND, first_year=2010,
            keywords="турпоток региона, сколько туристов приехало, туристов за год по данным региона"),
    TSeries("tour-moskva-reestr-obekty", "annual", "Гостиницы и прочие средства размещения в реестре Москвы",
            "Accommodation in the Moscow register", "объектов", "properties",
            "Сколько гостиниц, хостелов и апарт-отелей числится в реестре классифицированных средств размещения "
            "Москвы на дату обновления в году.",
            "Hotels, hostels and apart-hotels in Moscow's register of classified accommodation as of the update "
            "date in the year.", "mos", "6.t96", first_year=2018),
    TSeries("tour-moskva-reestr-nomera", "annual", "Номера в реестре средств размещения Москвы",
            "Rooms in the Moscow accommodation register", "номеров", "rooms",
            "Номера во всех средствах размещения из реестра Москвы.", "Rooms in all properties of the Moscow register.",
            "mos", "6.t97", first_year=2024),
    TSeries("tour-moskva-reestr-mesta", "annual", "Места в реестре средств размещения Москвы",
            "Bed places in the Moscow accommodation register", "мест", "bed places",
            "Места во всех средствах размещения из реестра Москвы.",
            "Bed places in all properties of the Moscow register.", "mos", "6.t98", first_year=2024),
)
NOT_RANKED = frozenset({*(s.code for s in REGIONAL_ESTIMATES), "tour-ksr-zagruzka-mest"})

SERIES: tuple[TSeries, ...] = (
    *ANNUAL_KSR, *ANNUAL_SANATORIUMS, *ANNUAL_FIRMS, *ANNUAL_PENDING, *MONTHLY_EMISS, *MONTHLY_TRANSPORT,
    *MONTHLY_CPI, *TURPOTOK, *QUARTERLY_CBR, *TAX, *REGISTRIES, *PUBLICATIONS, *REGIONAL_ESTIMATES,
)
SERIES_BY_CODE: dict[str, TSeries] = {s.code: s for s in SERIES}

# Средние цены туруслуг по субъектам (ЕМИСС 31448, ряды ``ceni-*`` реестра ``emiss_price_goods``): пока fedstat
# закрыт, их помесячно продлевают файлы Росстата ``sred_potreb_cen_*.xlsx`` (2022-01 — 2026-09, снимок c4 и живой
# файл). Пишутся только недостающие месяцы: ряд и метаданные остаются у реестра цен. Подпись столбца файла →
# код ряда; позиции вне туризма (продукты, одежда) здесь не трогаются.
PRICE_TOURISM_RX = (r"^(проживание в (гостинице|хостеле)|поездк|экскурс|речной круиз|санаторий|дом отдыха|"
                    r"полет в салоне|проезд в (купейном|плацкартном|сидячих))")


def price_tourism_codes() -> dict[str, str]:
    """«подпись, единица» (нижний регистр) → код ряда цен."""
    import re

    from app.data.emiss_price_goods import ALL_PRICE_GOODS

    rx = re.compile(PRICE_TOURISM_RX)
    return {f"{g.label.casefold().strip()}, {g.per.casefold().strip()}": g.code
            for g in ALL_PRICE_GOODS if rx.search(g.label.casefold().strip())}


def emiss_datasets() -> dict[int, list[TSeries]]:
    """Набор ЕМИСС → его ряды (по порядку реестра)."""
    out: dict[int, list[TSeries]] = {}
    for s in SERIES:
        if s.emiss is not None:
            out.setdefault(s.emiss.dataset, []).append(s)
    return out


def is_tourism_code(code: str) -> bool:
    """Свой ряд (метаданные у этого реестра); продлённые ряды сборника сюда не входят."""
    s = SERIES_BY_CODE.get(code)
    return s is not None and s.own_metadata


def source_of(code: str) -> dict[str, str] | None:
    s = SERIES_BY_CODE.get(code)
    return SOURCES[s.source] if s is not None and s.own_metadata else None


def source_note(s: TSeries) -> str:
    """Подпись источника в метаданных (``region_indicators.source_note``, до 200 символов)."""
    base = SOURCES[s.source]["ru"]
    return f"{base}, набор {s.emiss.dataset}" if s.emiss is not None else base


def copy_en() -> dict[str, dict[str, str | None]]:
    """Английские название, единица, пояснение и раздел — для ``REGION_INDICATORS_EN``."""
    return {s.code: {"name": s.name_en, "unit": s.unit_en, "note": s.note_en, "section": s.section[2]}
            for s in SERIES if s.own_metadata}


# SSR-карточки помесячного и квартального ряда: свои фразы источника (у ЦБ, ФНС, реестров — не Росстат).
def monthly_texts(code: str, locale: str) -> dict[str, str] | None:
    src = source_of(code)
    if src is None:
        return None
    en = locale == "en"
    about = src["about_en" if en else "about_ru"]
    name = src["en" if en else "ru"]
    if en:
        return {
            "faq_value_a": "In {month_prep}: {value}{unit}. Source: " + name + ".",
            "faq_source_a": about,
            "source_p": name + ". Values in {unit}. Observation period: {first} — {last}.",
            "description": ("{indicator} in {region}: {value} {unit} in {month_prep}. Monthly chart and table since "
                            "{first_year}, comparison with the Russian average. Source: " + name + "."),
        }
    return {
        "faq_value_a": "В {month_prep} — {value}{unit}. Источник — " + name + ".",
        "faq_source_a": about,
        "source_p": name + ". Значения приведены в единицах: {unit}. Период наблюдений: {first} — {last}.",
        "description": ("{indicator} в регионе {region}: {value} {unit} в {month_prep}. Динамика с {first_year} "
                        "года, график и таблица по месяцам, сравнение со средним по России. Источник — " + name + "."),
    }


_METHODS_PATH = None


def region_method(code: str, slug: str | None, locale: str = "ru") -> str | None:
    """Методика оценки турпотока конкретного региона и годы её смены (``regional/tourism_region_methods.json``)."""
    if code != "tour-turpotok-ocenka-regiona" or not slug:
        return None
    import json
    from pathlib import Path

    global _METHODS_PATH
    _METHODS_PATH = _METHODS_PATH or Path(__file__).resolve().parent / "regional" / "tourism_region_methods.json"
    m = json.loads(_METHODS_PATH.read_text(encoding="utf-8")).get(slug)
    if not m:
        return None
    lang = "en" if locale == "en" else "ru"
    breaks = ", ".join(map(str, m.get("breaks") or []))
    if lang == "en":
        text = f"Who is counted: {m['who_en']}. Method: {m['how_en']}."
        if breaks:
            text += f" The method changed in {breaks}: the series breaks there."
    else:
        text = f"Кого считают: {m['who_ru']}. Как считают: {m['how_ru']}."
        if breaks:
            many = len(m["breaks"]) > 1
            text += f" Методика менялась в {breaks} {'годах' if many else 'году'} — здесь ряд разрывается."
    caveat = m.get(f"caveat_{lang}")
    return f"{text} {caveat}" if caveat else text



# --- Адреса источников (круг наблюдателей 20.11.2026, правка №4): ссылка на конкретную публикацию, а не на раздел.
# rosstat.gov.ru на iPhone без сертификата Минцифры показывает предупреждение, поэтому где ряд есть в ЕМИСС —
# ведём в ЕМИСС; файлы Росстата — прямой ссылкой на файл.
SOURCE_URLS: dict[str, str] = {
    "rosstat_turpotok": "https://rosstat.gov.ru/storage/mediabank/Turpotok_2kv-2026.xlsx",
    "cbr": "https://www.cbr.ru/vfs/statistics/credit_statistics/trade/imp_services_reg_26.xlsx",
    "fns": "https://www.nalog.gov.ru/rn77/related_activities/statistics_and_analytics/forms/16619097/",
    "fsa": "https://tourism.fsa.gov.ru/ru/resorts/showcase/hotels",
    "minec": "https://ev.economy.gov.ru/lk_exp/registry/",
    "treasury": "https://roskazna.gov.ru/ispolnenie-byudzhetov/konsolidirovannye-byudzhety-subektov-rossijskoj-federacii/",
    # Сборники Росстата по субъектам в плоской выгрузке «Если быть точным» (там же — ссылки на выпуски Росстата).
    "rosstat_pub": "https://tochno.st/datasets/regions_collection",
    "rosstat_calc": "https://www.fedstat.ru/indicator/31587",
    "mos": "https://data.mos.ru/opendata/62056",
    "sber": "https://sberindex.ru/ru/dashboards/kolichestvo-vnutrennikh-turistov",
}
# Ряды из конкретного файла или сборника — точнее, чем адрес источника в целом.
_SERIES_URLS: dict[str, str] = {
    # «Туризм в России» 2024, раздел 5: на сайте Росстата файл снят (404) — копия web.archive.org.
    **{c: "https://web.archive.org/web/20250201063454/https://rosstat.gov.ru/storage/mediabank/R5-tur.xlsx" for c in (
        "tour-gostinicy-chislo", "tour-gostinicy-nomera", "tour-gostinicy-mesta", "tour-hostely-chislo",
        "tour-hostely-mesta", "tour-organizacii-otdyha-mesta")},
    "tour-cbr-poezdki-eksport": "https://www.cbr.ru/vfs/statistics/credit_statistics/trade/exp_services_reg_26.xlsx",
    "tour-cbr-poezdki-eksport-delovye": "https://www.cbr.ru/vfs/statistics/credit_statistics/trade/exp_services_reg_26.xlsx",
    "tour-cbr-poezdki-eksport-lichnye": "https://www.cbr.ru/vfs/statistics/credit_statistics/trade/exp_services_reg_26.xlsx",
    "tour-cbr-turuslugi-eksport": "https://www.cbr.ru/vfs/statistics/credit_statistics/trade/exp_services_reg_26.xlsx",
    "tour-cena-kupe-nefirmennyy": "https://rosstat.gov.ru/storage/mediabank/sred_potreb_cen_09-2026.xlsx",
    "tour-cena-plackart-nefirmennyy": "https://rosstat.gov.ru/storage/mediabank/sred_potreb_cen_09-2026.xlsx",
}


def source_url(code: str, slug: str | None = None) -> str | None:
    s = SERIES_BY_CODE.get(code)
    if s is None:
        return None
    if s.emiss is not None:
        return f"https://www.fedstat.ru/indicator/{s.emiss.dataset}"
    if code == "tour-turpotok-ocenka-regiona" and slug:
        return _region_method_entry(slug).get("url") or None
    return _SERIES_URLS.get(code) or SOURCE_URLS.get(s.source)


def _region_method_entry(slug: str) -> dict:
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parent / "regional" / "tourism_region_methods.json"
    return json.loads(path.read_text(encoding="utf-8")).get(slug) or {}


def api_source(code: str, slug: str | None, locale: str) -> dict | None:
    """Поле ``source`` карточек API регионов: подпись, адрес, что важно знать о данных, методика региона.

    Отрисовку делает страница показателя (z2); здесь — только данные."""
    s = SERIES_BY_CODE.get(code)
    if s is None or not s.own_metadata:
        return None
    lang = "en" if locale == "en" else "ru"
    src = SOURCES[s.source]
    out = {"name": src[lang], "url": source_url(code, slug), "about": src[f"about_{lang}"],
           "dataset": s.emiss.dataset if s.emiss is not None else None,
           "calculated": s.source == "rosstat_calc", "approximate": s.source == "sber",
           "ranked": code not in NOT_RANKED}
    method = region_method(code, slug, lang)
    if method:
        out["region_method"] = method
    return out


# Туристический налог: ноль — не «−100 %». Ноль за весь год в отчёте ФНС — налога в регионе нет (поступлений не
# было); ноль в отдельные месяцы — платёж за квартал ещё не пришёл. Москва налог в 2025–2026 годах не вводила
# (в отчётах Казначейства строки Москвы нет, в 1-НМ — нули), остальным годовым нулям даётся нейтральный статус.
ZERO_NOT_CHANGE = frozenset({"tour-nalog-s-nachala-goda", "tour-nalog-za-god", "tour-kurortnyy-sbor"})
TAX_NOT_INTRODUCED: dict[str, frozenset[int]] = {"moskva": frozenset({2025, 2026})}


# Круг наблюдателей 20.11.2026 (№37): городские автобусы и общепит — не туризм. Коды без «tour-», общепит — в разделе
# 15 «Торговля и услуги населению». Старые коды уже стояли на стенде: миграция 20261120_region_data_updated и
# ``ensure_indicators`` переименовывают их на месте (точки сохраняются).
RENAMED: dict[str, str] = {
    "tour-avtobusy-passazhiry": "avtobusy-passazhiry-mes",
    "tour-obshchepit-oborot-mes": "obshchepit-oborot-mes",
    "tour-obshchepit-restorany": "obshchepit-restorany",
    "tour-obshchepit-stolovye": "obshchepit-stolovye",
    "tour-obshchepit-rezultat-restorany": "obshchepit-rezultat-restorany",
}
# Блок «Ещё в разделе» у туристических рядов: без театров, музеев, спорта, библиотек и газет (таблицы 6.1–6.4).
_NON_TOURISM_TABLES = ("6.1.", "6.2.", "6.3.", "6.4")


def is_tourism_sibling(code: str, table_code: str | None) -> bool:
    if code in SERIES_BY_CODE:
        return True
    t = table_code or ""
    return not (t.startswith(_NON_TOURISM_TABLES) or t == "6.4")
