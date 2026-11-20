"""Туризм в странах мира: МВФ, UN Tourism, ОЭСР, Евростат и национальные службы (20.11.2026).

Раздел «Туризм» у стран каталога `world_countries`. Описание рядов и разбор файлов издателей —
здесь; запросы и запись в базу — `world_tourism_ingest`. Модуль чистый: все функции принимают
текст или байты файла, поэтому сохранённые файлы издателей служат фикстурами тестов.

Издатели и что берём (почему именно это — `docs/data_sources.md`, раздел «Туризм в мире»):

- **МВФ, платёжный баланс** (`IMF.STA:BOP`) — статья «Поездки»: сколько иностранцы тратят в стране
  (кредит) и сколько жители страны тратят за рубежом (дебет); деловые и личные поездки, лечение,
  учёба. Квартал, если страна его публикует, иначе год. Значения издателя в долларах — делим на 10⁶.
- **UN Tourism** (Всемирная туристская организация ООН), единый архив статистики — прибытия
  иностранцев, внутренние и выездные поездки, гостиницы, доля туризма в ВВП, занятые в туризме.
  Год. Расходы туристов из этого архива не берём: тот же смысл, что у МВФ, а МВФ свежее.
- **ОЭСР** — доля туризма в занятости и в ВВП; прибытия туристов из России (страна — «ведущий рынок»).
- **Евростат** `bop_its6_det` — поездки в расчётах с Россией: траты жителей России в стране ЕС и
  траты жителей этой страны в России. Год, млн евро.
- **Национальные службы стран назначения** — туристы из России: Кипр (CYSTAT, месяц с 2002 года),
  Грузия (Geostat, квартал с 2014 года), Турция (Министерство культуры и туризма, год с 2010 года).

Ловушки сырья (проверено на файлах 20.11.2026):
- UN Tourism: коды стран — числовые M49; отметки качества лежат в отдельной колонке; файл гостиниц
  выложен дважды под разными именами — дубли схлопываются по (ряд, страна, год).
- CYSTAT: «u» — ненадёжная оценка по малой выборке, «...» — нет данных; обе отметки — пропуск.
- Geostat: значение — визиты **в среднем за месяц** квартала, тыс.; так и публикуем.
- ОЭСР: у одной страны бывает два источника (`TDS` — опрос туристов, `TSS` — гостиницы и граница):
  берём ряд с более поздней последней точкой, при равенстве — `TDS`.
- Россия в мировой каталог не входит (её ряды — в российском разделе), её строки пропускаются.
"""

from __future__ import annotations

import csv
import io
import math
import re
import zipfile
from dataclasses import dataclass, replace
from datetime import date
from typing import Iterable

import openpyxl

from app.services.world_intl_sources import IntlSeries, dedupe_points

TOURISM_CATEGORY_RU = "Туризм"
TOURISM_CATEGORY_EN = "Tourism"

IMF_PROVIDER = "imf_bop"
UNT_PROVIDER = "untourism"
OECD_PROVIDER = "oecd_tourism"
ESTAT_PROVIDER = "eurostat_travel"
CYSTAT_PROVIDER = "cystat"
GEOSTAT_PROVIDER = "geostat"
KTB_PROVIDER = "ktb_tr"

PROVIDERS = (
    IMF_PROVIDER, UNT_PROVIDER, OECD_PROVIDER, ESTAT_PROVIDER, CYSTAT_PROVIDER, GEOSTAT_PROVIDER, KTB_PROVIDER,
)

# Публичное имя издателя по машинному коду (RU; EN — через глоссарий).
SOURCE_BY_PROVIDER = {
    IMF_PROVIDER: "Международный валютный фонд",
    UNT_PROVIDER: "UN Tourism (Всемирная туристская организация ООН)",
    OECD_PROVIDER: "ОЭСР",
    ESTAT_PROVIDER: "Евростат",
    CYSTAT_PROVIDER: "Статистическая служба Кипра (CYSTAT)",
    GEOSTAT_PROVIDER: "Национальная статистическая служба Грузии (Geostat)",
    KTB_PROVIDER: "Министерство культуры и туризма Турции",
}

IMF_URL = (
    "https://api.imf.org/external/sdmx/2.1/data/IMF.STA,BOP/{countries}.CD_T+DB_T.{items}.USD.Q+A"
    "?startPeriod=1990"
)
UNT_PAGE_URL = "https://www.untourism.int/tourism-statistics/tourism-statistics-database"
UNT_ZIP_RE = re.compile(r"https?://[^\"'\s<>]+UN_Tourism_bulk_data_download[^\"'\s<>]*\.zip", re.IGNORECASE)
OECD_KEY_URL = "https://sdmx.oecd.org/public/rest/data/OECD.CFE.TOU,DSD_TOURISM_KEY@DF_KEY_IND_PC,/all"
OECD_INBOUND_RU_URL = "https://sdmx.oecd.org/public/rest/data/OECD.CFE.TOU,DSD_TOURISM_INTER@DF_INBOUND,/.RUS.TOP_MKT...."
ESTAT_URL = (
    "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/bop_its6_det/A.MIO_EUR.SD.CRE+DEB.RU."
    "?format=SDMX-CSV"
)
CYSTAT_URL = "https://cystatdb.cystat.gov.cy/api/v1/en/8.CYSTAT-DB/Tourism/Tourists/Monthly/2021010E.px"
GEOSTAT_PAGE_URL = "https://www.geostat.ge/en/modules/categories/102/inbound-tourism-statistics"
GEOSTAT_VISITS_RE = re.compile(r"https?://[^\"'\s<>]*0505EN0204[^\"'\s<>]*\.xlsx", re.IGNORECASE)


@dataclass(frozen=True)
class TourismSeries(IntlSeries):
    """Ряд раздела «Туризм»: поля `IntlSeries` плюс английские тексты и ключ ряда у издателя."""

    name_en_full: str = ""
    unit_en: str = ""
    description_en: str = ""
    methodology_en: str = ""
    scale: float = 1.0  # множитель к значению издателя (МВФ: доллары → млн долл.)


def _imf(item: str, entry: str, suffix: str, name_ru: str, name_en: str, desc_ru: str, desc_en: str,
         keywords: str) -> TourismSeries:
    side_ru = (
        "Кредит платёжного баланса: деньги, которые нерезиденты оставили в стране."
        if entry == "CD_T" else
        "Дебет платёжного баланса: деньги, которые жители страны потратили за её пределами."
    )
    side_en = (
        "Balance-of-payments credit: money non-residents spent in the country."
        if entry == "CD_T" else
        "Balance-of-payments debit: money residents spent outside the country."
    )
    return TourismSeries(
        provider=IMF_PROVIDER, dataset_id="bop", series_id=f"{entry}.{item}", code_suffix=suffix,
        concept_slug=suffix, name_ru=name_ru, name_en=name_en, unit="MIO_USD", unit_ru="млн долл. США",
        frequency="quarterly", category_ru=TOURISM_CATEGORY_RU, source_ru=SOURCE_BY_PROVIDER[IMF_PROVIDER],
        source_url="https://data.imf.org/en/datasets/IMF.STA:BOP",
        description_ru=desc_ru,
        methodology_ru=(
            "Статья «Поездки» платёжного баланса: товары и услуги, которые путешественники покупают в "
            "чужой стране, — проживание, еда, транспорт внутри страны, покупки, лечение, учёба. Билеты на "
            "международный перелёт сюда не входят. " + side_ru + " Страна сдаёт данные в "
            "Международный валютный фонд по единому стандарту, поэтому страны можно сравнивать между собой. "
            "Квартальные значения не очищены от сезонности: летом туристов больше. Если страна публикует "
            "только годовые данные, ряд годовой. Значения в миллионах долларов США по курсу периода."
        ),
        keywords_ru=keywords, unit_en="million US dollars", description_en=desc_en,
        methodology_en=(
            "The travel item of the balance of payments covers goods and services travellers buy in "
            "another country: accommodation, food, local transport, shopping, medical care and education. "
            "International passenger fares are excluded. " + side_en + " Countries report to the "
            "International Monetary Fund under one standard, so the figures are comparable across "
            "countries. Quarterly values are not seasonally adjusted. Where a country publishes only "
            "annual data, the series is annual. Values are in millions of US dollars at the period's "
            "exchange rate."
        ),
        scale=1e-6,
    )


IMF_SERIES: tuple[TourismSeries, ...] = (
    _imf("SD", "CD_T", "imf-travel-receipts",
         "Траты иностранных путешественников в стране", "Travel receipts from foreign visitors",
         "Сколько денег иностранцы тратят в стране во время поездок: проживание, еда, покупки, "
         "транспорт, лечение и учёба. Главная мера доходов страны от въездного туризма.",
         "How much foreign travellers spend in the country: accommodation, food, shopping, local "
         "transport, medical care and education. The main measure of a country's income from inbound tourism.",
         "доходы от туризма {country}, траты иностранных туристов {country}, поступления от туризма {country}"),
    _imf("SD", "DB_T", "imf-travel-payments",
         "Траты жителей страны в зарубежных поездках", "Travel spending abroad by residents",
         "Сколько денег жители страны тратят в зарубежных поездках: отдых, командировки, лечение, учёба.",
         "How much the country's residents spend on trips abroad: holidays, business trips, medical "
         "care and education.",
         "расходы на зарубежные поездки {country}, выездной туризм {country}, траты туристов за рубежом {country}"),
    _imf("SDA", "CD_T", "imf-travel-business-receipts",
         "Траты иностранцев в деловых поездках", "Business travel receipts",
         "Сколько тратят в стране иностранцы, приехавшие по работе: командировки, переговоры, выставки.",
         "Spending in the country by foreign business travellers: work trips, meetings and trade fairs.",
         "деловой туризм {country}, командировки иностранцев {country}"),
    _imf("SDA", "DB_T", "imf-travel-business-payments",
         "Траты жителей страны в деловых поездках за рубежом", "Business travel spending abroad",
         "Сколько жители страны тратят в зарубежных командировках.",
         "Spending abroad by the country's residents on business trips.",
         "зарубежные командировки {country}, деловые поездки {country}"),
    _imf("SDB", "CD_T", "imf-travel-personal-receipts",
         "Траты иностранцев в личных поездках", "Personal travel receipts",
         "Сколько тратят в стране иностранцы, приехавшие не по работе: отдых, визиты к родным, лечение, учёба.",
         "Spending in the country by foreigners on personal trips: holidays, family visits, medical care, study.",
         "иностранные туристы {country}, отдых иностранцев {country}"),
    _imf("SDB", "DB_T", "imf-travel-personal-payments",
         "Траты жителей страны в личных поездках за рубежом", "Personal travel spending abroad",
         "Сколько жители страны тратят в зарубежных поездках не по работе: отдых, визиты к родным, "
         "лечение, учёба.",
         "Spending abroad by residents on personal trips: holidays, family visits, medical care, study.",
         "отдых за рубежом {country}, туристические поездки {country}"),
    _imf("SDB1", "CD_T", "imf-travel-health-receipts",
         "Траты иностранцев на лечение в стране", "Health-related travel receipts",
         "Сколько иностранцы тратят на лечение и проживание во время медицинских поездок в страну.",
         "Spending by foreigners on medical care and their stay during health-related trips to the country.",
         "медицинский туризм {country}, лечение иностранцев {country}"),
    _imf("SDB1", "DB_T", "imf-travel-health-payments",
         "Траты жителей страны на лечение за рубежом", "Health-related travel spending abroad",
         "Сколько жители страны тратят на лечение и проживание во время медицинских поездок за границу.",
         "Spending by residents on medical care and their stay during health-related trips abroad.",
         "лечение за рубежом {country}, медицинские поездки {country}"),
    _imf("SDB2", "CD_T", "imf-travel-education-receipts",
         "Траты иностранных студентов в стране", "Education-related travel receipts",
         "Сколько иностранные студенты тратят в стране на учёбу и жизнь во время учёбы.",
         "Spending by foreign students in the country on tuition and living costs.",
         "иностранные студенты {country}, образовательный туризм {country}"),
    _imf("SDB2", "DB_T", "imf-travel-education-payments",
         "Траты жителей страны на учёбу за рубежом", "Education-related travel spending abroad",
         "Сколько жители страны тратят на учёбу и жизнь во время учёбы за границей.",
         "Spending by residents on tuition and living costs while studying abroad.",
         "учёба за рубежом {country}, студенты за границей {country}"),
)

_UNT_METHOD_RU = (
    "UN Tourism (Всемирная туристская организация ООН) собирает данные у национальных статистических "
    "служб, министерств туризма и центральных банков и приводит их к единым определениям. Турист — "
    "посетитель, который провёл в месте поездки хотя бы одну ночь; однодневный посетитель — без ночёвки. "
    "Страны считают по-разному (на границе, в гостиницах, опросами), поэтому сравнивать уровни разных "
    "стран надо осторожно; динамика одной страны надёжна. Данные годовые и выходят с задержкой в год-два."
)
_UNT_METHOD_EN = (
    "UN Tourism (the World Tourism Organization) collects data from national statistical offices, tourism "
    "ministries and central banks and harmonises the definitions. A tourist is a visitor who stays at least "
    "one night; a same-day visitor does not stay overnight. Countries measure differently (at the border, "
    "in hotels or by surveys), so compare levels across countries with care; the trend within one country "
    "is reliable. Data are annual and published with a lag of one to two years."
)


def _unt(code: str, suffix: str, name_ru: str, name_en: str, unit: str, unit_ru: str, unit_en: str,
         desc_ru: str, desc_en: str, keywords: str, *, scale: float = 1.0, extra_ru: str = "",
         extra_en: str = "") -> TourismSeries:
    return TourismSeries(
        provider=UNT_PROVIDER, dataset_id="bulk", series_id=code, code_suffix=suffix, concept_slug=suffix,
        name_ru=name_ru, name_en=name_en, unit=unit, unit_ru=unit_ru, frequency="annual",
        category_ru=TOURISM_CATEGORY_RU, source_ru=SOURCE_BY_PROVIDER[UNT_PROVIDER],
        source_url=UNT_PAGE_URL, description_ru=desc_ru,
        methodology_ru=(_UNT_METHOD_RU + (" " + extra_ru if extra_ru else "")),
        keywords_ru=keywords, unit_en=unit_en, description_en=desc_en,
        methodology_en=(_UNT_METHOD_EN + (" " + extra_en if extra_en else "")), scale=scale,
    )


UNT_SERIES: tuple[TourismSeries, ...] = (
    _unt("INBD_TRIP_TOTL_TOTL_TOUR", "unt-inbound-tourists", "Прибытия иностранных туристов",
         "International tourist arrivals", "THS", "тыс. поездок", "thousand trips",
         "Сколько раз иностранцы приезжали в страну с ночёвкой за год. Один человек, приехавший дважды, "
         "считается дважды.",
         "How many times foreigners arrived in the country and stayed at least one night during the year. "
         "A person who came twice counts twice.",
         "туристы {country}, турпоток {country}, сколько туристов посетили {country}, въездной туризм {country}"),
    _unt("INBD_TRIP_TOTL_TOTL_VSTR", "unt-inbound-visitors", "Прибытия иностранных посетителей",
         "International visitor arrivals", "THS", "тыс. поездок", "thousand trips",
         "Все приезды иностранцев в страну за год — и с ночёвкой, и однодневные, включая пассажиров круизов.",
         "All arrivals of foreigners during the year, overnight and same-day, including cruise passengers.",
         "иностранные посетители {country}, въезд иностранцев {country}"),
    _unt("INBD_ACCM_HOTL_GUES", "unt-inbound-hotel-guests", "Иностранные гости гостиниц",
         "Non-resident guests in hotels", "THS_PER", "тыс. человек", "thousand guests",
         "Сколько иностранцев заселились в гостиницы и похожие средства размещения страны за год.",
         "How many non-residents checked in to hotels and similar establishments during the year.",
         "иностранцы в гостиницах {country}, гости отелей {country}"),
    _unt("INBD_ACCM_HOTL_NGHT", "unt-inbound-hotel-nights", "Ночёвки иностранцев в гостиницах",
         "Nights spent by non-residents in hotels", "THS", "тыс. ночёвок", "thousand nights",
         "Сколько ночей иностранцы провели в гостиницах и похожих средствах размещения страны за год.",
         "Nights spent by non-residents in hotels and similar establishments during the year.",
         "ночёвки иностранцев {country}, загрузка отелей иностранцами {country}"),
    _unt("DOMC_TRIP_TOTL_TOTL_TOUR", "unt-domestic-trips", "Внутренние туристские поездки",
         "Domestic tourism trips", "THS", "тыс. поездок", "thousand trips",
         "Сколько поездок с ночёвкой жители страны совершили по своей стране за год.",
         "Overnight trips residents made within their own country during the year.",
         "внутренний туризм {country}, поездки по стране {country}"),
    _unt("DOMC_ACCM_HOTL_NGHT", "unt-domestic-hotel-nights", "Ночёвки жителей страны в гостиницах",
         "Nights spent by residents in hotels", "THS", "тыс. ночёвок", "thousand nights",
         "Сколько ночей жители страны провели в гостиницах своей страны за год.",
         "Nights residents spent in hotels and similar establishments in their own country during the year.",
         "внутренний туризм гостиницы {country}, ночёвки в отелях {country}"),
    _unt("OUTB_TRIP_TOTL_TOTL_TOUR", "unt-outbound-tourists", "Выездные туристские поездки",
         "Outbound tourism trips", "THS", "тыс. поездок", "thousand trips",
         "Сколько поездок с ночёвкой жители страны совершили за границу за год.",
         "Overnight trips residents made abroad during the year.",
         "выездной туризм {country}, поездки за границу {country}"),
    _unt("OUTB_TRIP_TOTL_TOTL_VSTR", "unt-outbound-visitors", "Все выезды жителей за границу",
         "Outbound visitor departures", "THS", "тыс. поездок", "thousand trips",
         "Все поездки жителей страны за границу за год — и с ночёвкой, и однодневные.",
         "All trips residents made abroad during the year, overnight and same-day.",
         "выезд за границу {country}, выездные поездки {country}"),
    _unt("CPTY_ACCM_HOTL_ESTB", "unt-hotels", "Число гостиниц", "Number of hotels", "NR", "единиц", "units",
         "Сколько гостиниц и похожих средств размещения работает в стране.",
         "Number of hotels and similar establishments in the country.",
         "сколько гостиниц {country}, число отелей {country}"),
    _unt("CPTY_ACCM_HOTL_ROOM", "unt-hotel-rooms", "Номера в гостиницах", "Hotel rooms", "NR", "единиц", "units",
         "Сколько номеров во всех гостиницах и похожих средствах размещения страны.",
         "Number of rooms in hotels and similar establishments.",
         "номерной фонд {country}, гостиничные номера {country}"),
    _unt("CPTY_ACCM_HOTL_BEDS", "unt-hotel-beds", "Места в гостиницах", "Hotel bed places", "NR",
         "мест", "bed places",
         "Сколько спальных мест во всех гостиницах и похожих средствах размещения страны.",
         "Number of bed places in hotels and similar establishments.",
         "койко-места {country}, вместимость гостиниц {country}"),
    _unt("CPTY_ACCM_HOTL_ROOM_RATE", "unt-hotel-occupancy", "Загрузка номеров в гостиницах",
         "Hotel room occupancy rate", "PC", "% номеров", "% of rooms",
         "Какая доля гостиничных номеров была занята в среднем за год.",
         "Average share of hotel rooms occupied during the year.",
         "загрузка отелей {country}, заполняемость гостиниц {country}"),
    _unt("CPTY_ACCM_HOTL_STAY_AVRG", "unt-hotel-stay", "Средняя продолжительность пребывания в гостиницах",
         "Average length of stay in hotels", "NGHT", "ночей", "nights",
         "Сколько ночей в среднем гость проводит в гостинице за одно заселение.",
         "Average number of nights a guest stays in a hotel per visit.",
         "сколько дней туристы {country}, длительность пребывания {country}"),
    _unt("ST_GDP_ZS", "tourism-gdp-share", "Доля туризма в ВВП", "Tourism direct GDP, share of GDP",
         "PC_GDP", "% ВВП", "% of GDP",
         "Какую часть экономики страны прямо создаёт туризм: гостиницы, общепит, перевозки и другие услуги "
         "туристам.",
         "The share of the economy directly generated by tourism: hotels, restaurants, transport and other "
         "services to visitors.",
         "доля туризма в ВВП {country}, вклад туризма в экономику {country}",
         extra_ru=("Показатель цели устойчивого развития ООН 8.9.1. Считается по туристскому "
                   "вспомогательному счёту страны; где его нет, страна даёт оценку по добавленной стоимости."),
         extra_en=("UN Sustainable Development Goal indicator 8.9.1, based on the country's tourism satellite "
                   "account or, where there is none, on tourism value added.")),
    _unt("EMPL_TOTL_TOTL_TOTL_TOTL_PRSN", "unt-tourism-employment", "Занятые в отраслях туризма",
         "Employment in tourism industries", "THS_PER", "тыс. человек", "thousand people",
         "Сколько людей работает в отраслях, которые обслуживают туристов: гостиницы, общепит, перевозки, "
         "турфирмы, культура и спорт.",
         "People employed in industries serving visitors: accommodation, food service, transport, travel "
         "agencies, culture and sport.",
         "занятость в туризме {country}, работники туризма {country}",
         scale=1e-3,
         extra_ru="Показатель цели устойчивого развития ООН 8.9.2; часть стран передаёт данные через МОТ.",
         extra_en="UN Sustainable Development Goal indicator 8.9.2; some countries report via the ILO."),
)

_OECD_METHOD_RU = (
    "ОЭСР собирает данные у национальных статистических служб и министерств туризма стран-участниц "
    "и партнёров. Доля туризма считается по туристскому вспомогательному счёту страны: сколько добавленной "
    "стоимости и рабочих мест приходится на покупки туристов. Данные годовые."
)
_OECD_METHOD_EN = (
    "The OECD compiles data from national statistical offices and tourism ministries of members and partners. "
    "Tourism shares come from the country's tourism satellite account: the value added and jobs generated by "
    "visitor spending. Data are annual."
)

OECD_EMP_SHARE = TourismSeries(
    provider=OECD_PROVIDER, dataset_id="key_ind", series_id="EMP_SH", code_suffix="oecd-tourism-employment-share",
    concept_slug="tourism-employment-share", name_ru="Доля туризма в занятости",
    name_en="Tourism share of employment", unit="PC_EMP", unit_ru="% занятых", frequency="annual",
    category_ru=TOURISM_CATEGORY_RU, source_ru=SOURCE_BY_PROVIDER[OECD_PROVIDER],
    source_url="https://data-explorer.oecd.org/", description_ru="Какая доля всех работающих в стране занята "
    "обслуживанием туристов.", methodology_ru=_OECD_METHOD_RU,
    keywords_ru="занятость в туризме {country}, доля туризма в занятости {country}",
    unit_en="% of employment", description_en="Share of all employed people working to serve visitors.",
    methodology_en=_OECD_METHOD_EN,
)
OECD_GDP_SHARE = TourismSeries(
    provider=OECD_PROVIDER, dataset_id="key_ind", series_id="GDP_SH", code_suffix="tourism-gdp-share",
    concept_slug="tourism-gdp-share", name_ru="Доля туризма в ВВП", name_en="Tourism direct GDP, share of GDP",
    unit="PC_GDP", unit_ru="% ВВП", frequency="annual", category_ru=TOURISM_CATEGORY_RU,
    source_ru=SOURCE_BY_PROVIDER[OECD_PROVIDER], source_url="https://data-explorer.oecd.org/",
    description_ru=("Какую часть экономики страны прямо создаёт туризм: гостиницы, общепит, перевозки и другие "
                    "услуги туристам."),
    methodology_ru=_OECD_METHOD_RU, keywords_ru="доля туризма в ВВП {country}, вклад туризма в экономику {country}",
    unit_en="% of GDP",
    description_en=("The share of the economy directly generated by tourism: hotels, restaurants, transport and "
                    "other services to visitors."),
    methodology_en=_OECD_METHOD_EN,
)

_RU_ARRIVALS_DESC_RU = "Сколько туристов из России приехало в страну за период."
_RU_ARRIVALS_DESC_EN = "How many tourists from Russia arrived in the country during the period."
_RU_ARRIVALS_KEYWORDS = (
    "туристы из России {country}, сколько россиян посетили {country}, турпоток из России {country}, "
    "россияне {country}"
)

OECD_RU_ARRIVALS = TourismSeries(
    provider=OECD_PROVIDER, dataset_id="inbound", series_id="TOP_MKT:RUS", code_suffix="tour-arrivals-russia",
    concept_slug="tour-arrivals-russia", name_ru="Туристы из России", name_en="Tourist arrivals from Russia",
    unit="PER", unit_ru="человек", frequency="annual", category_ru=TOURISM_CATEGORY_RU,
    source_ru=SOURCE_BY_PROVIDER[OECD_PROVIDER], source_url="https://data-explorer.oecd.org/",
    description_ru=_RU_ARRIVALS_DESC_RU,
    methodology_ru=("ОЭСР публикует прибытия туристов из главных стран-поставщиков по данным самой страны "
                    "назначения: пограничного учёта, опроса туристов или регистрации в гостиницах. Учитываются "
                    "туристы с ночёвкой, по стране проживания. Если страна считает и на границе, и в гостиницах, "
                    "берётся более свежий ряд. Год."),
    keywords_ru=_RU_ARRIVALS_KEYWORDS, unit_en="people", description_en=_RU_ARRIVALS_DESC_EN,
    methodology_en=("The OECD publishes arrivals from the main source markets as reported by the destination "
                    "country: border counts, visitor surveys or hotel registrations. Overnight tourists by country "
                    "of residence. Where a country reports both border and hotel counts, the more recent series "
                    "is used. Annual."),
)

_ESTAT_METHOD_RU = (
    "Евростат публикует платёжный баланс стран Европы с разбивкой по странам-партнёрам. Статья «Поездки» — "
    "товары и услуги, которые путешественники покупают в чужой стране: проживание, еда, транспорт внутри "
    "страны, покупки, лечение, учёба. Авиабилеты между странами не входят. Год, млн евро. Часть стран не "
    "раскрывает значение по отдельному партнёру — тогда в ряду пропуск."
)
_ESTAT_METHOD_EN = (
    "Eurostat publishes the balance of payments of European countries by partner country. The travel item "
    "covers goods and services travellers buy in another country: accommodation, food, local transport, "
    "shopping, medical care and education. International fares are excluded. Annual, million euro. Some "
    "countries withhold partner detail, which leaves gaps."
)
ESTAT_RU_CREDIT = TourismSeries(
    provider=ESTAT_PROVIDER, dataset_id="bop_its6_det", series_id="SD:CRE:RU",
    code_suffix="estat-travel-russia-receipts", concept_slug="travel-russia-receipts",
    name_ru="Траты жителей России в поездках в страну", name_en="Travel spending by Russian residents in the country",
    unit="MIO_EUR", unit_ru="млн евро", frequency="annual", category_ru=TOURISM_CATEGORY_RU,
    source_ru=SOURCE_BY_PROVIDER[ESTAT_PROVIDER],
    source_url="https://ec.europa.eu/eurostat/databrowser/view/bop_its6_det/default/table",
    description_ru="Сколько жители России потратили в этой стране во время поездок за год.",
    methodology_ru=_ESTAT_METHOD_RU,
    keywords_ru="российские туристы {country}, траты россиян {country}, туристы из России {country}",
    unit_en="million euro", description_en="How much Russian residents spent in the country on trips during the year.",
    methodology_en=_ESTAT_METHOD_EN,
)
ESTAT_RU_DEBIT = replace(
    ESTAT_RU_CREDIT, series_id="SD:DEB:RU", code_suffix="estat-travel-russia-payments",
    concept_slug="travel-russia-payments", name_ru="Траты жителей страны в поездках в Россию",
    name_en="Residents' travel spending in Russia",
    description_ru="Сколько жители этой страны потратили во время поездок в Россию за год.",
    keywords_ru="поездки в Россию {country}, туристы в Россию из {country}",
    description_en="How much the country's residents spent on trips to Russia during the year.",
)

CYSTAT_RU_ARRIVALS = TourismSeries(
    provider=CYSTAT_PROVIDER, dataset_id="2021010E", series_id="Russia", code_suffix="tour-arrivals-russia",
    concept_slug="tour-arrivals-russia", name_ru="Туристы из России", name_en="Tourist arrivals from Russia",
    unit="PER", unit_ru="человек", frequency="monthly", category_ru=TOURISM_CATEGORY_RU,
    source_ru=SOURCE_BY_PROVIDER[CYSTAT_PROVIDER], source_url="https://cystatdb.cystat.gov.cy/",
    description_ru=_RU_ARRIVALS_DESC_RU,
    methodology_ru=("Статистическая служба Кипра считает туристов по опросу на границе в аэропортах и портах "
                    "республики: учитываются приезжие, которые живут в другой стране и остаются хотя бы на одну "
                    "ночь, — по стране постоянного проживания. Месяц. Если выборка слишком мала и служба "
                    "помечает значение как ненадёжное, в ряду пропуск."),
    keywords_ru=_RU_ARRIVALS_KEYWORDS, unit_en="people", description_en=_RU_ARRIVALS_DESC_EN,
    methodology_en=("The Statistical Service of Cyprus counts tourists through a border survey at the airports and "
                    "ports of the Republic: non-residents staying at least one night, by country of usual "
                    "residence. Monthly. Where the sample is too small and the value is flagged unreliable, the "
                    "month is left blank."),
)
CYSTAT_TOTAL_ARRIVALS = replace(
    CYSTAT_RU_ARRIVALS, series_id="TOTAL", code_suffix="tour-arrivals-total", concept_slug="tour-arrivals-total",
    name_ru="Прибытия туристов", name_en="Tourist arrivals",
    description_ru="Сколько иностранных туристов приехало в страну за месяц.",
    keywords_ru="туристы {country}, сколько туристов {country}, турпоток {country}",
    description_en="How many foreign tourists arrived in the country during the month.",
)

_GEOSTAT_METHOD_RU = (
    "Национальная статистическая служба Грузии проводит ежеквартальный опрос приезжих старше 15 лет на "
    "границе. Значение — среднее число визитов в месяц за квартал, тыс.; визит — одна поездка в Грузию, "
    "человек, приехавший дважды, даёт два визита. Гражданство — по паспорту."
)
_GEOSTAT_METHOD_EN = (
    "The National Statistics Office of Georgia runs a quarterly border survey of visitors aged 15 and over. "
    "The value is the average monthly number of visits in the quarter, in thousands; a person who came twice "
    "makes two visits. Citizenship is by passport."
)
GEOSTAT_RU_VISITS = TourismSeries(
    provider=GEOSTAT_PROVIDER, dataset_id="0505EN0204", series_id="Russia", code_suffix="tour-visits-russia",
    concept_slug="tour-visits-russia", name_ru="Визиты граждан России", name_en="Visits by citizens of Russia",
    unit="THS", unit_ru="тыс. визитов в месяц", frequency="quarterly", category_ru=TOURISM_CATEGORY_RU,
    source_ru=SOURCE_BY_PROVIDER[GEOSTAT_PROVIDER], source_url=GEOSTAT_PAGE_URL,
    description_ru="Сколько раз граждане России приезжали в страну — в среднем за месяц квартала.",
    methodology_ru=_GEOSTAT_METHOD_RU,
    keywords_ru="россияне {country}, туристы из России {country}, сколько россиян посетили {country}",
    unit_en="thousand visits per month", description_en="Visits by Russian citizens, monthly average for the quarter.",
    methodology_en=_GEOSTAT_METHOD_EN,
)
GEOSTAT_TOTAL_VISITS = replace(
    GEOSTAT_RU_VISITS, series_id="Total", code_suffix="tour-visits-total", concept_slug="tour-visits-total",
    name_ru="Визиты иностранных посетителей", name_en="Inbound visits",
    description_ru="Сколько раз иностранные посетители приезжали в страну — в среднем за месяц квартала.",
    keywords_ru="туристы {country}, сколько туристов {country}, турпоток {country}",
    description_en="Inbound visits, monthly average for the quarter.",
)

_KTB_METHOD_RU = (
    "Министерство культуры и туризма Турции публикует пограничную статистику: сколько иностранцев въехало в "
    "страну, по гражданству. Учитывается каждое пересечение границы на въезд, кроме однодневных посетителей "
    "из соседних стран. Год."
)
_KTB_METHOD_EN = (
    "The Ministry of Culture and Tourism of Türkiye publishes border statistics: foreign arrivals by "
    "nationality. Every entry is counted. Annual."
)
KTB_RU_ARRIVALS = TourismSeries(
    provider=KTB_PROVIDER, dataset_id="sinir_yillik", series_id="Rusya Fed.", code_suffix="tour-arrivals-russia",
    concept_slug="tour-arrivals-russia", name_ru="Туристы из России", name_en="Tourist arrivals from Russia",
    unit="PER", unit_ru="человек", frequency="annual", category_ru=TOURISM_CATEGORY_RU,
    source_ru=SOURCE_BY_PROVIDER[KTB_PROVIDER], source_url="https://yigm.ktb.gov.tr/",
    description_ru="Сколько граждан России въехало в страну за год.", methodology_ru=_KTB_METHOD_RU,
    keywords_ru=_RU_ARRIVALS_KEYWORDS, unit_en="people",
    description_en="How many Russian citizens entered the country during the year.", methodology_en=_KTB_METHOD_EN,
)
KTB_TOTAL_ARRIVALS = replace(
    KTB_RU_ARRIVALS, series_id="TOPLAM", code_suffix="tour-arrivals-total", concept_slug="tour-arrivals-total",
    name_ru="Прибытия иностранных посетителей", name_en="Foreign visitor arrivals",
    description_ru="Сколько иностранцев въехало в страну за год.",
    keywords_ru="туристы {country}, сколько туристов {country}, турпоток {country}",
    description_en="How many foreigners entered the country during the year.",
)

ALL_SERIES: tuple[TourismSeries, ...] = (
    IMF_SERIES + UNT_SERIES
    + (OECD_EMP_SHARE, OECD_GDP_SHARE, OECD_RU_ARRIVALS, ESTAT_RU_CREDIT, ESTAT_RU_DEBIT,
       CYSTAT_RU_ARRIVALS, CYSTAT_TOTAL_ARRIVALS, GEOSTAT_RU_VISITS, GEOSTAT_TOTAL_VISITS,
       KTB_RU_ARRIVALS, KTB_TOTAL_ARRIVALS)
)
TOURISM_PROVIDERS = frozenset(item.provider for item in ALL_SERIES)
_SERIES_BY_KEY = {(item.provider, item.code_suffix): item for item in ALL_SERIES}
# Национальный ряд важнее ряда ОЭСР того же смысла и вытесняет его у страны (ADR-0012).
NATIONAL_RU_ARRIVALS = {"CY": CYSTAT_PROVIDER, "TR": KTB_PROVIDER}


def series_for_indicator(provider: str | None, code: str | None) -> TourismSeries | None:
    """Описание туристского ряда по карточке: английские тексты и единица для EN-страниц."""
    prov = (provider or "").strip().lower()
    if prov not in TOURISM_PROVIDERS or not code or "-" not in code:
        return None
    return _SERIES_BY_KEY.get((prov, code.split("-", 1)[1]))


def curated_copy_en(provider: str | None, code: str | None) -> dict[str, str] | None:
    series = series_for_indicator(provider, code)
    if series is None:
        return None
    return {
        "unit_en": series.unit_en,
        "description_en": series.description_en,
        "methodology_en": series.methodology_en,
    }


# ---------------------------------------------------------------------------
# Коды стран
# ---------------------------------------------------------------------------

# ISO-3 (МВФ, ОЭСР) → код каталога. Греция и Великобритания в каталоге — EL и UK; Косово у МВФ — KOS.
ISO3_TO_CATALOG: dict[str, str] = {
    "ALB": "AL", "ARM": "AM", "AUT": "AT", "AUS": "AU", "AZE": "AZ", "BIH": "BA", "BEL": "BE", "BGR": "BG",
    "BRA": "BR", "CAN": "CA", "CHE": "CH", "CHN": "CN", "CYP": "CY", "CZE": "CZ", "DEU": "DE", "DNK": "DK",
    "EST": "EE", "GRC": "EL", "ESP": "ES", "FIN": "FI", "FRA": "FR", "GEO": "GE", "HRV": "HR", "HUN": "HU",
    "IRL": "IE", "ISR": "IL", "IND": "IN", "ISL": "IS", "ITA": "IT", "JPN": "JP", "KOR": "KR", "LTU": "LT",
    "LUX": "LU", "LVA": "LV", "MDA": "MD", "MNE": "ME", "MKD": "MK", "MLT": "MT", "MEX": "MX", "NLD": "NL",
    "NOR": "NO", "NZL": "NZ", "POL": "PL", "PRT": "PT", "ROU": "RO", "SRB": "RS", "SWE": "SE", "SVN": "SI",
    "SVK": "SK", "TUR": "TR", "UKR": "UA", "GBR": "UK", "USA": "US", "ZAF": "ZA", "KOS": "XK", "XKX": "XK",
}
# Числовые коды ООН (M49) — UN Tourism.
M49_TO_CATALOG: dict[int, str] = {
    8: "AL", 51: "AM", 40: "AT", 36: "AU", 31: "AZ", 70: "BA", 56: "BE", 100: "BG", 76: "BR", 124: "CA",
    756: "CH", 156: "CN", 196: "CY", 203: "CZ", 276: "DE", 208: "DK", 233: "EE", 300: "EL", 724: "ES",
    246: "FI", 250: "FR", 268: "GE", 191: "HR", 348: "HU", 372: "IE", 376: "IL", 356: "IN", 352: "IS",
    380: "IT", 392: "JP", 410: "KR", 440: "LT", 442: "LU", 428: "LV", 498: "MD", 499: "ME", 807: "MK",
    470: "MT", 484: "MX", 528: "NL", 578: "NO", 554: "NZ", 616: "PL", 620: "PT", 642: "RO", 688: "RS",
    752: "SE", 705: "SI", 703: "SK", 792: "TR", 804: "UA", 826: "UK", 840: "US", 710: "ZA",
}
# Евростат: две буквы, как в каталоге (EL, UK); прочее совпадает с ISO-2.
ESTAT_GEO_TO_CATALOG = {"GR": "EL", "GB": "UK"}

Points = list[tuple[date, float]]
Parsed = dict[tuple[str, str], Points]  # (суффикс ряда, код страны каталога) → точки


def _num(raw) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        value = float(raw)
    else:
        text = str(raw).strip().replace(" ", "").replace(" ", "").replace(",", ".")
        if not text or not re.fullmatch(r"-?\d+(\.\d+)?([eE][-+]?\d+)?", text):
            return None
        value = float(text)
    return value if math.isfinite(value) else None


def _period(raw: str) -> tuple[date, str] | None:
    """«2025», «2025-Q3», «2025Q3», «2025-07», «2025M07» → (первый день периода, частота)."""
    text = str(raw or "").strip()
    if re.fullmatch(r"\d{4}", text):
        return date(int(text), 1, 1), "annual"
    match = re.fullmatch(r"(\d{4})-?Q([1-4])", text)
    if match:
        return date(int(match.group(1)), 3 * int(match.group(2)) - 2, 1), "quarterly"
    match = re.fullmatch(r"(\d{4})[-M](\d{2})", text)
    if match and 1 <= int(match.group(2)) <= 12:
        return date(int(match.group(1)), int(match.group(2)), 1), "monthly"
    return None


def _finish(raw: dict[tuple[str, str], list[tuple[date, float]]]) -> Parsed:
    return {key: dedupe_points(points) for key, points in raw.items() if points}


# ---------------------------------------------------------------------------
# МВФ
# ---------------------------------------------------------------------------

def parse_imf_bop_csv(text: str) -> tuple[Parsed, dict[tuple[str, str], str]]:
    """CSV МВФ → ({(суффикс, страна): точки}, {(суффикс, страна): частота}).

    Квартальный ряд важнее годового; годовой берётся, только если кварталов у страны по статье нет.
    """
    by_key = {(item.series_id): item for item in IMF_SERIES}
    quarterly: dict[tuple[str, str], list] = {}
    annual: dict[tuple[str, str], list] = {}
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    for row in reader:
        series = by_key.get(f"{(row.get('BOP_ACCOUNTING_ENTRY') or '').strip()}.{(row.get('INDICATOR') or '').strip()}")
        country = ISO3_TO_CATALOG.get((row.get("COUNTRY") or "").strip().upper())
        if series is None or country is None or (row.get("UNIT") or "").strip() != "USD":
            continue
        value = _num(row.get("OBS_VALUE"))
        parsed = _period(row.get("TIME_PERIOD") or "")
        if value is None or parsed is None:
            continue
        when, freq = parsed
        target = quarterly if freq == "quarterly" else annual if freq == "annual" else None
        if target is None:
            continue
        target.setdefault((series.code_suffix, country), []).append((when, value * series.scale))
    out: dict[tuple[str, str], list] = {}
    freqs: dict[tuple[str, str], str] = {}
    for key in set(quarterly) | set(annual):
        if quarterly.get(key):
            out[key], freqs[key] = quarterly[key], "quarterly"
        else:
            out[key], freqs[key] = annual[key], "annual"
    return _finish(out), freqs


# ---------------------------------------------------------------------------
# UN Tourism
# ---------------------------------------------------------------------------

def _unt_rows(workbook_bytes: bytes) -> Iterable[dict]:
    wb = openpyxl.load_workbook(io.BytesIO(workbook_bytes), read_only=True, data_only=True)
    try:
        sheet = wb["Data"] if "Data" in wb.sheetnames else wb[wb.sheetnames[-1]]
        rows = sheet.iter_rows(values_only=True)
        header = None
        for row in rows:
            if header is None:
                if row and "indicator_code" in row:
                    header = [str(cell) if cell is not None else "" for cell in row]
                continue
            yield dict(zip(header, row))
    finally:
        wb.close()


def parse_untourism_workbooks(workbooks: Iterable[bytes]) -> Parsed:
    """Книги архива UN Tourism (лист «Data», длинный формат) → ряды стран каталога."""
    by_code = {item.series_id: item for item in UNT_SERIES}
    out: dict[tuple[str, str], list] = {}
    for blob in workbooks:
        for row in _unt_rows(blob):
            series = by_code.get(str(row.get("indicator_code") or "").strip())
            if series is None:
                continue
            partner = row.get("partner_area_code")
            if partner not in (None, "", 999, "999"):
                continue
            try:
                country = M49_TO_CATALOG.get(int(row.get("reporter_area_code")))
                year = int(row.get("year"))
            except (TypeError, ValueError):
                continue
            value = _num(row.get("value"))
            if country is None or value is None:
                continue
            out.setdefault((series.code_suffix, country), []).append((date(year, 1, 1), value * series.scale))
    return _finish(out)


def untourism_zip_link(page_html: str) -> str | None:
    match = UNT_ZIP_RE.search(page_html or "")
    return match.group(0) if match else None


def untourism_workbooks_from_zip(blob: bytes) -> list[bytes]:
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        return [archive.read(name) for name in archive.namelist() if name.lower().endswith(".xlsx")]


# ---------------------------------------------------------------------------
# ОЭСР
# ---------------------------------------------------------------------------

def parse_oecd_key_csv(text: str) -> Parsed:
    """Ключевые показатели ОЭСР: доля туризма в занятости и в ВВП."""
    wanted = {"EMP_SH": OECD_EMP_SHARE, "GDP_SH": OECD_GDP_SHARE}
    out: dict[tuple[str, str], list] = {}
    for row in csv.DictReader(io.StringIO(text.lstrip("﻿"))):
        series = wanted.get((row.get("MEASURE") or "").strip())
        country = ISO3_TO_CATALOG.get((row.get("REF_AREA") or "").strip().upper())
        value = _num(row.get("OBS_VALUE"))
        parsed = _period(row.get("TIME_PERIOD") or "")
        if series is None or country is None or value is None or parsed is None:
            continue
        out.setdefault((series.code_suffix, country), []).append((parsed[0], value))
    return _finish(out)


def parse_oecd_inbound_russia_csv(text: str) -> Parsed:
    """Прибытия туристов из России (ведущие рынки ОЭСР); из двух источников страны — более свежий."""
    by_source: dict[tuple[str, str], list] = {}
    for row in csv.DictReader(io.StringIO(text.lstrip("﻿"))):
        if (row.get("COUNTERPART_AREA") or "").strip() != "RUS" or (row.get("MEASURE") or "").strip() != "TOP_MKT":
            continue
        if (row.get("VISITOR_TYPE") or "").strip() not in ("OVERNIGHT", "_T"):
            continue
        country = ISO3_TO_CATALOG.get((row.get("REF_AREA") or "").strip().upper())
        value = _num(row.get("OBS_VALUE"))
        parsed = _period(row.get("TIME_PERIOD") or "")
        if country is None or value is None or parsed is None:
            continue
        by_source.setdefault((country, (row.get("SOURCE") or "").strip()), []).append((parsed[0], value))
    best: dict[str, tuple[tuple, list]] = {}
    for (country, source), points in by_source.items():
        points = dedupe_points(points)
        rank = (points[-1][0], source == "TDS", len(points))
        if country not in best or rank > best[country][0]:
            best[country] = (rank, points)
    return {(OECD_RU_ARRIVALS.code_suffix, country): points for country, (_, points) in best.items()}


# ---------------------------------------------------------------------------
# Евростат
# ---------------------------------------------------------------------------

def parse_estat_travel_russia_csv(text: str) -> Parsed:
    """`bop_its6_det`, статья «Поездки», партнёр — Россия: кредит и дебет по странам."""
    series_by_flow = {"CRE": ESTAT_RU_CREDIT, "DEB": ESTAT_RU_DEBIT}
    out: dict[tuple[str, str], list] = {}
    for row in csv.DictReader(io.StringIO(text.lstrip("﻿"))):
        if (row.get("bop_item") or "").strip() != "SD" or (row.get("partner") or "").strip() != "RU":
            continue
        if (row.get("currency") or "").strip() != "MIO_EUR":
            continue
        series = series_by_flow.get((row.get("stk_flow") or "").strip())
        geo = (row.get("geo") or "").strip().upper()
        country = ESTAT_GEO_TO_CATALOG.get(geo, geo)
        value = _num(row.get("OBS_VALUE"))
        parsed = _period(row.get("TIME_PERIOD") or "")
        if series is None or country not in M49_TO_CATALOG.values() or value is None or parsed is None:
            continue
        out.setdefault((series.code_suffix, country), []).append((parsed[0], value))
    return _finish(out)


# ---------------------------------------------------------------------------
# Кипр, Грузия, Турция
# ---------------------------------------------------------------------------

def parse_cystat_csv(text: str) -> Parsed:
    """Широкая таблица CYSTAT: строка — страна проживания, колонки «2002M01»…; «u» и «...» — пропуск."""
    wanted = {"russia": CYSTAT_RU_ARRIVALS, "total": CYSTAT_TOTAL_ARRIVALS}
    reader = csv.reader(io.StringIO(text.lstrip("﻿")))
    header = next(reader, None) or []
    periods = [_period(cell) for cell in header]
    out: dict[tuple[str, str], list] = {}
    for row in reader:
        if not row:
            continue
        series = wanted.get(row[0].strip().lower())
        if series is None:
            continue
        for cell, parsed in zip(row[1:], periods[1:]):
            value = _num(cell)
            if parsed is None or value is None:
                continue
            out.setdefault((series.code_suffix, "CY"), []).append((parsed[0], value))
    return _finish(out)


_ROMAN_QUARTER = {"I": 1, "II": 2, "III": 3, "IV": 4}


def parse_geostat_visits_xlsx(blob: bytes) -> Parsed:
    """Geostat 0505EN0204, лист «Quarterly figures»: год пишется только у первого квартала года."""
    wb = openpyxl.load_workbook(io.BytesIO(blob), read_only=True, data_only=True)
    try:
        sheet = wb["Quarterly figures"] if "Quarterly figures" in wb.sheetnames else wb[wb.sheetnames[0]]
        header: list[str] | None = None
        year: int | None = None
        out: dict[tuple[str, str], list] = {}
        for row in sheet.iter_rows(values_only=True):
            if header is None:
                if row and str(row[0] or "").strip() == "Year":
                    header = [str(cell or "").strip() for cell in row]
                continue
            if row[0] not in (None, ""):
                try:
                    year = int(str(row[0]).strip()[:4])
                except ValueError:
                    continue
            quarter = _ROMAN_QUARTER.get(str(row[1] or "").strip().rstrip("*"))
            if year is None or quarter is None:
                continue
            when = date(year, 3 * quarter - 2, 1)
            for series in (GEOSTAT_RU_VISITS, GEOSTAT_TOTAL_VISITS):
                if series.series_id not in header:
                    continue
                value = _num(row[header.index(series.series_id)])
                if value is not None:
                    out.setdefault((series.code_suffix, "GE"), []).append((when, value))
        return _finish(out)
    finally:
        wb.close()


def geostat_visits_link(page_html: str) -> str | None:
    match = GEOSTAT_VISITS_RE.search(page_html or "")
    return match.group(0) if match else None


def parse_ktb_yearly_xlsx(blob: bytes) -> Parsed:
    """Годовой пограничный бюллетень Турции, лист «C-…»: иностранцы по гражданству, колонки — годы."""
    wb = openpyxl.load_workbook(io.BytesIO(blob), read_only=True, data_only=True)
    try:
        name = next((sheet for sheet in wb.sheetnames if sheet.startswith("C-")), None)
        if name is None:
            return {}
        years: list[int | None] | None = None
        out: dict[tuple[str, str], list] = {}
        for row in wb[name].iter_rows(values_only=True):
            cells = list(row)
            label_idx = next((i for i, cell in enumerate(cells) if isinstance(cell, str) and cell.strip()), None)
            if label_idx is None:
                continue
            label = cells[label_idx].strip()
            if years is None:
                if label.upper().startswith("MİLLİYET") or label.upper().startswith("MILLIYET"):
                    years = [int(c) if isinstance(c, (int, float)) and 1990 < c < 2100 else None for c in cells]
                continue
            series = KTB_RU_ARRIVALS if label == KTB_RU_ARRIVALS.series_id else (
                KTB_TOTAL_ARRIVALS if label.upper() == KTB_TOTAL_ARRIVALS.series_id else None
            )
            if series is None:
                continue
            for year, cell in zip(years, cells):
                value = _num(cell)
                if year is not None and value is not None:
                    out.setdefault((series.code_suffix, "TR"), []).append((date(year, 1, 1), value))
        return _finish(out)
    finally:
        wb.close()


def series_lookup(provider: str, suffix: str) -> TourismSeries:
    return _SERIES_BY_KEY[(provider, suffix)]
