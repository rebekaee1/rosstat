"""Туризм по России в целом: реестр федеральных рядов раздела «Туризм» (20.11.2026).

Один реестр для seed, английских текстов, SEO, семейств режимов, прогнозов и групп срезов. Ряды:

- Банк России, статья «Поездки» внешней торговли услугами: траты иностранцев в России (экспорт), траты
  россиян за рубежом (импорт) и сальдо — квартал из платёжного баланса с 1994 года и месяц из
  ``trade_monthly.xlsx`` с 2018 года; деловые и личные поездки — квартал с 1999 года. Строки «туруслуги»,
  «лечение», «учёба», «прочие поездки» в платёжном балансе — нули за всю историю (не публикуются) и не берутся.
- Росстат по данным пограничной службы ФСБ России (файл ``Poezdki``): въездные поездки иностранцев и выездные
  поездки россиян по кварталам с 2015 года, въезд по месяцам с 2022 года, 24 главные страны.
- Росстат: добавленная стоимость туристской индустрии, её доля в ВВП и реальный рост (2017+).
- ЕМИСС: перевозки авиакомпаний (Росавиация, 2009+), шесть крупнейших аэропортов (2018+), железная дорога
  (2016+), гостиницы и прочие средства размещения (2002+), санатории, турфирмы; ночёвки по месяцам (2023+).
- Россияне в Египте, Таиланде, Узбекистане и Казахстане по статистике этих стран (своих страниц у стран нет;
  Кипр, Грузия и Турция — на страницах стран).

Не взяты (решение по качеству данных): турпоток Росстата (``Turpotok``) — в одном файле три разных итога России за
2025 год (170,0 / 168,0 / 173,7 млн) рядом с 92 млн у размещённых в гостиницах, ряды начинаются с 2022 года; РЖД из
пресс-релизов (40 пропущенных месяцев, нарастающие итоги вперемешку); квартальные ряды ЕМИСС по средствам размещения
(обрываются на 2022 году и не сходятся с годовыми по охвату).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

CATEGORY = "Туризм"
CATEGORY_EN = "Tourism"

CBR_TRAVEL_URL = "https://www.cbr.ru/statistics/macro_itm/external_sector/ets/"  # прежний /svs/ отвечает 404 (21.11.2026)
CBR_MONTHLY_URL = "https://www.cbr.ru/statistics/macro_itm/external_sector/ets/"
ROSSTAT_TOURISM_URL = "https://rosstat.gov.ru/statistics/turizm"
FEDSTAT = "https://www.fedstat.ru/indicator/{}"

SRC_CBR = "Банк России"
SRC_ROSSTAT = "Росстат"
SRC_FSB = "Росстат по данным ФСБ России"
SRC_FAVT = "Росавиация (ЕМИСС)"


@dataclass(frozen=True)
class TourSeries:
    code: str
    name: str
    name_en: str
    unit: str
    unit_en: str
    frequency: str                      # monthly / quarterly / annual
    source: str
    source_url: str
    parser_type: str
    cfg: dict
    description: str
    description_en: str
    methodology: str
    methodology_en: str
    keywords: str
    seo_title: str
    seo_description: str
    family: str | None = None           # шаблон FamilyDef (T6/T7/T9/T9s/T10/T10a/T2y)
    yoy_unit: str | None = None
    forecast: str | None = None         # monthly_auto / generic_quarterly / signed_quarterly / annual_auto
    listed: bool = True
    min_value: float | None = 0.0
    extra_cfg: dict = field(default_factory=dict)


# ── Тексты методологии ────────────────────────────────────────────────────────

_M_CBR = (
    "Банк России считает статью «Поездки» по методологии платёжного баланса. Экспорт — товары и услуги, которые "
    "иностранцы купили в России за время поездок (проживание, питание, транспорт внутри страны, покупки, "
    "лечение, учёба). Импорт — то же самое, купленное россиянами за границей. Билеты на международные рейсы "
    "сюда не входят: они учитываются в транспортных услугах. Оценка строится по данным банков о платежах "
    "картами и переводах, по числу поездок пограничной службы и обследованиям. Последние месяцы — оценка, "
    "Банк России уточняет её в следующих выпусках."
)
_M_CBR_EN = (
    "The Bank of Russia compiles the travel item under balance of payments methodology. Exports are goods and "
    "services bought in Russia by foreign visitors during their trips (accommodation, food, local transport, "
    "shopping, medical care, education). Imports are the same purchases made by Russian residents abroad. "
    "International air tickets are excluded; they are recorded under transport services. Estimates combine "
    "bank card and transfer data, border crossing counts and surveys. The latest months are preliminary and "
    "are revised in later releases."
)

_M_FSB = (
    "Росстат оценивает число туристских поездок по сведениям пограничной службы ФСБ России о пересечении "
    "границы. Туристская поездка — путешествие на срок меньше года с деловой, личной целью или для отдыха; "
    "поездки на работу по найму, экипажи транспорта, дипломаты и военные не учитываются. Один человек может "
    "совершить несколько поездок. Росстат публикует нарастающие итоги с начала года; на сайте квартал — "
    "разность соседних итогов. С 2022 года данные о выезде неполные (так помечено у Росстата)."
)
_M_FSB_EN = (
    "Rosstat estimates tourist trips from border crossing records of the Border Service of the FSB of Russia. "
    "A tourist trip is travel for less than a year for business, personal reasons or leisure; work under "
    "contract, transport crews, diplomats and military staff are excluded. One person may make several trips. "
    "Rosstat publishes cumulative year-to-date totals; on this site a quarter is the difference between "
    "consecutive totals. From 2022 outbound data are incomplete, as noted by Rosstat."
)
_M_FSB_MONTHLY = (
    "Месячная оценка Росстата по методике национального проекта «Туризм и индустрия гостеприимства» на основе "
    "сведений пограничной службы ФСБ России. Росстат публикует итог с начала года в миллионах поездок, с 2023 "
    "года — с точностью до 10 тыс.; месяц на сайте — разность соседних итогов, поэтому у отдельного месяца "
    "погрешность округления около 10 тыс. поездок."
)
_M_FSB_MONTHLY_EN = (
    "Monthly Rosstat estimate under the methodology of the national project on tourism, based on FSB border "
    "service records. Rosstat publishes the year-to-date total in million trips, rounded to 10 thousand since "
    "2023; a month on this site is the difference between consecutive totals, so a single month carries a "
    "rounding error of about 10 thousand trips."
)

_M_GVA = (
    "Туристская индустрия у Росстата — все виды деятельности, которые обслуживают туристов: гостиницы и другие "
    "средства размещения, общественное питание, пассажирский транспорт, турагентства и туроператоры, "
    "санатории, культура и развлечения. Добавленная стоимость — выпуск этих отраслей за вычетом затрат, в "
    "текущих ценах; учитывается только доля, приходящаяся на туристов. Данные за 2017–2024 годы пересчитаны по "
    "методологии 2025 года; с 2022 года — без учёта новых субъектов Российской Федерации."
)
_M_GVA_EN = (
    "Rosstat defines the tourism industry as all activities that serve visitors: hotels and other "
    "accommodation, food services, passenger transport, travel agencies and tour operators, health resorts, "
    "culture and recreation. Gross value added is the output of these industries less intermediate "
    "consumption, at current prices, counting only the part attributable to visitors. Data for 2017-2024 were "
    "recalculated under the 2025 methodology; from 2022 the data exclude the territories identified by Rosstat "
    "as new constituent entities."
)

_M_AIR = (
    "Росавиация собирает отчёты всех российских авиакомпаний о коммерческих перевозках: регулярных рейсах по "
    "расписанию и нерегулярных (чартерах). Внутренние перевозки — полёты между городами России, международные "
    "— рейсы за рубеж и обратно. Пассажир считается один раз на каждый оплаченный перелёт. Иностранные "
    "авиакомпании не учитываются."
)
_M_AIR_EN = (
    "The Federal Air Transport Agency collects reports from all Russian airlines on commercial traffic: "
    "scheduled flights and non-scheduled (charter) flights. Domestic traffic covers flights between Russian "
    "cities; international traffic covers flights abroad and back. A passenger is counted once per paid "
    "flight. Foreign airlines are not included."
)

_M_AIRPORT = (
    "Росавиация публикует число пассажиров шести крупнейших аэропортов России: сколько человек улетело и "
    "прилетело на регулярных и чартерных рейсах, внутренних и международных. Транзитный пассажир с пересадкой "
    "учитывается при прилёте и при вылете."
)
_M_AIRPORT_EN = (
    "The Federal Air Transport Agency publishes passenger numbers for Russia's six largest airports: departing "
    "and arriving passengers on scheduled and charter, domestic and international flights. A transfer "
    "passenger is counted both on arrival and on departure."
)

_M_RAIL = (
    "Росстат учитывает пассажиров железнодорожного транспорта общего пользования: поездов дальнего следования "
    "и пригородных электричек. С 2023 года данные приведены без учёта новых субъектов Российской Федерации."
)
_M_RAIL_EN = (
    "Rosstat counts passengers of public railway transport: long-distance trains and suburban trains. From "
    "2023 the data exclude the territories identified by Rosstat as new constituent entities."
)

_M_KSR = (
    "Росстат собирает годовые отчёты гостиниц и прочих коллективных средств размещения: хостелов, баз отдыха, "
    "туристских баз, кемпингов, санаториев и детских лагерей. Размещённые лица — сколько человек заселилось за "
    "год; один человек при двух заездах считается дважды. Ночёвка — одна ночь одного гостя. С 2015 и 2017 годов "
    "в наблюдение вошло больше малых средств размещения, поэтому ряды делают ступеньку вверх. С 2023 года — без "
    "учёта новых субъектов Российской Федерации."
)
_M_KSR_EN = (
    "Rosstat collects annual reports from hotels and other collective accommodation establishments: hostels, "
    "holiday centres, tourist bases, campsites, health resorts and children's camps. Guests are the number of "
    "check-ins during the year; a person staying twice is counted twice. A night spent is one night of one "
    "guest. Coverage of small establishments widened in 2015 and 2017, which lifts the series. From 2023 the "
    "data exclude the territories identified by Rosstat as new constituent entities."
)

_M_KSR_MONTHLY = (
    "Оперативные помесячные данные Росстата о ночёвках в гостиницах и прочих коллективных средствах "
    "размещения. Росстат публикует итог с начала года; месяц на сайте — разность соседних итогов. Охват "
    "оперативного наблюдения уже годового, поэтому сумма месяцев меньше годового числа ночёвок."
)
_M_KSR_MONTHLY_EN = (
    "Rosstat's preliminary monthly data on nights spent in hotels and other collective accommodation. Rosstat "
    "publishes year-to-date totals; a month on this site is the difference between consecutive totals. "
    "Coverage of the monthly survey is narrower than the annual one, so the months add up to less than the "
    "annual number of nights."
)

_M_SAN = (
    "Росстат собирает годовые отчёты санаториев, санаториев-профилакториев, пансионатов с лечением и других "
    "санаторно-курортных организаций. Размещённые — сколько человек заехало за год, ночёвки — число ночей. "
    "С 2023 года — без учёта новых субъектов Российской Федерации."
)
_M_SAN_EN = (
    "Rosstat collects annual reports from sanatoria, preventive health centres, boarding houses with treatment "
    "and other health resort organisations. Guests are the number of check-ins during the year; nights are the "
    "number of nights spent. From 2023 the data exclude the territories identified by Rosstat as new "
    "constituent entities."
)

_M_FIRMS = (
    "Росстат считает организации и предпринимателей, которые отчитались о туроператорской, турагентской и "
    "экскурсионной деятельности за год. С 2023 года — без учёта новых субъектов Российской Федерации."
)
_M_FIRMS_EN = (
    "Rosstat counts organisations and entrepreneurs that reported tour operator, travel agency or excursion "
    "activity during the year. From 2023 the data exclude the territories identified by Rosstat as new "
    "constituent entities."
)

_KW_TOUR = "туризм, туристы, туристический поток, турпоток, путешествия, статистика туризма, Россия"


def _s(code: str, name: str, name_en: str, unit: str, unit_en: str, frequency: str, source: str, url: str,
       parser: str, cfg: dict, desc: str, desc_en: str, meth: str, meth_en: str, keywords: str,
       period_phrase: str, **kw) -> TourSeries:
    """Короткая фабрика: SEO-заголовок и описание собираются из названия и периода."""
    seo_title = kw.pop("seo_title", None) or f"{name} — статистика и график"
    short = re.sub(r"\s*(?:Данные с|Квартальные данные с|Месячные данные с|С) \d{4} года\.$", "", desc)
    seo_description = kw.pop("seo_description", None) or f"{name}: официальные данные {period_phrase}. {short}"
    return TourSeries(code, name, name_en, unit, unit_en, frequency, source, url, parser, cfg, desc, desc_en,
                      meth, meth_en, f"{keywords}, {_KW_TOUR}", seo_title, seo_description[:300], **kw)


# ── Банк России: «Поездки» ────────────────────────────────────────────────────

def _cbr_series() -> list[TourSeries]:
    out: list[TourSeries] = []
    kw_exp = "траты иностранцев в России, въездной туризм, доходы от туризма, экспорт услуг, поездки, платёжный баланс"
    kw_imp = ("траты россиян за границей, выездной туризм, расходы на поездки за рубеж, импорт услуг, поездки, "
              "платёжный баланс")
    kw_bal = "сальдо поездок, туристический баланс, платёжный баланс, поездки, траты туристов"
    base = [
        ("tour-travel-exports", "Траты иностранцев в поездках по России", "Foreign visitors' spending in Russia",
         "travel-exports", "travel-exports-monthly",
         "Сколько иностранцы потратили в России во время деловых и личных поездок — экспорт услуг по статье "
         "«Поездки», миллионов долларов США.",
         "How much foreign visitors spent in Russia on business and personal trips: travel exports in the "
         "balance of payments, US dollars million.", kw_exp, "T9", "generic_quarterly"),
        ("tour-travel-imports", "Траты россиян в поездках за границу", "Russian residents' travel spending abroad",
         "travel-imports", "travel-imports-monthly",
         "Сколько россияне потратили за границей во время деловых и личных поездок — импорт услуг по статье "
         "«Поездки», миллионов долларов США.",
         "How much Russian residents spent abroad on business and personal trips: travel imports in the "
         "balance of payments, US dollars million.", kw_imp, "T9", "generic_quarterly"),
        ("tour-travel-balance", "Сальдо поездок в платёжном балансе", "Travel balance of Russia",
         "travel-balance", "travel-balance-monthly",
         "Разница между тратами иностранцев в России и тратами россиян за границей, миллионов долларов США. "
         "Минус — россияне тратят в поездках за рубежом больше, чем иностранцы в России.",
         "Foreign visitors' spending in Russia minus Russian residents' spending abroad, US dollars million. "
         "A negative value means Russians spend more abroad than visitors spend in Russia.", kw_bal, "T9s",
         "signed_quarterly"),
    ]
    for code, name, name_en, q_target, m_target, desc, desc_en, kws, fam, fc in base:
        monthly = f"{code}-monthly"
        signed = fam == "T9s"
        out.append(_s(
            code, name, name_en, "млн $", "USD mn", "quarterly", SRC_CBR, CBR_TRAVEL_URL, "cbr_bop_xlsx",
            {"bop_target": q_target, "alternate_frequencies": {"monthly": monthly}},
            desc + " Квартальные данные с 1994 года.", desc_en + " Quarterly data since 1994.",
            _M_CBR,
            _M_CBR_EN, kws, "Банка России по кварталам с 1994 года и по месяцам с 2018 года",
            family=fam, yoy_unit="млн $" if signed else None, forecast=fc,
            min_value=None if signed else 0.0,
        ))
        out.append(_s(
            monthly, f"{name} (месячный ряд)", f"{name_en} (monthly)", "млн $", "USD mn", "monthly", SRC_CBR,
            CBR_MONTHLY_URL, "cbr_trade_services_monthly",
            {"bop_target": m_target, "primary_indicator_code": code},
            desc + " Месячные данные с 2018 года.", desc_en + " Monthly data since 2018.",
            _M_CBR, _M_CBR_EN, kws, "Банка России по месяцам с 2018 года",
            family=None if signed else "T6",
            forecast=None if signed else "monthly_auto", listed=False, min_value=None if signed else 0.0,
        ))
    purpose = [
        ("business", "деловых", "business", "Деловые поездки — командировки, переговоры, выставки, а также "
         "поездки сезонных и приграничных работников.", "Business travel covers business trips, negotiations, "
         "trade fairs and travel by seasonal and border workers."),
        ("personal", "личных", "personal", "Личные поездки — отдых и туризм, лечение, учёба, поездки к "
         "родственникам и за покупками.", "Personal travel covers holidays and tourism, medical care, "
         "education, visits to relatives and shopping trips."),
    ]
    for key, adj, adj_en, note, note_en in purpose:
        for direction, kws in (("exports", kw_exp), ("imports", kw_imp)):
            code = f"tour-travel-{key}-{direction}"
            if direction == "exports":
                name = f"Траты иностранцев в {adj} поездках по России"
                name_en = f"Foreign visitors' {adj_en} travel spending in Russia"
                desc = f"Сколько иностранцы потратили в России во время {adj} поездок, миллионов долларов США. {note}"
                desc_en = f"Spending by foreign visitors in Russia on {adj_en} trips, US dollars million. {note_en}"
            else:
                name = f"Траты россиян в {adj} поездках за границу"
                name_en = f"Russian residents' {adj_en} travel spending abroad"
                desc = f"Сколько россияне потратили за границей во время {adj} поездок, миллионов долларов США. {note}"
                desc_en = f"Spending by Russian residents abroad on {adj_en} trips, US dollars million. {note_en}"
            out.append(_s(
                code, name, name_en, "млн $", "USD mn", "quarterly", SRC_CBR, CBR_TRAVEL_URL, "cbr_bop_xlsx",
                {"bop_target": f"travel-{key}-{direction}"},
                desc + " Квартальные данные с 1999 года.", desc_en + " Quarterly data since 1999.",
                _M_CBR, _M_CBR_EN, f"{key == 'business' and 'деловые поездки, командировки' or 'личные поездки, отдых, туризм'}, {kws}",
                "Банка России по кварталам с 1999 года", family="T9", listed=False,
            ))
    return out


# ── Росстат по данным ФСБ: въезд и выезд ─────────────────────────────────────

@dataclass(frozen=True)
class Country:
    slug: str
    labels: tuple[str, ...]     # подписи строки в файле Росстата (разные годы)
    name: str                   # именительный: «Китай»
    loc: str                    # «из Китая» / «в Турцию»
    name_en: str


# Особые оговорки по странам выезда (круг наблюдателей: правка 10, расхождения 5 и 6).
_COUNTRY_NOTE = {
    "egypt": (" В 2016–2018 годах Росстат строку Египта не публиковал — авиасообщение с Египтом было закрыто с ноября "
              "2015 года, поэтому за эти годы точек нет, а сравнение 2019 года с 2015 годом идёт через разрыв. Египет "
              "считает прибывших россиян по-своему: ряд «Прибытия россиян: Египет (данные страны)» за 2025 год даёт "
              "2 224,7 тыс. против 1 947,8 тыс. здесь — это два разных счёта, оба верны для своего источника."),
}

INBOUND_COUNTRIES: tuple[Country, ...] = (
    Country("kazakhstan", ("Казахстан",), "Казахстан", "из Казахстана", "Kazakhstan"),
    Country("china", ("Китай",), "Китай", "из Китая", "China"),
    Country("uzbekistan", ("Узбекистан",), "Узбекистан", "из Узбекистана", "Uzbekistan"),
    Country("abkhazia", ("Абхазия",), "Абхазия", "из Абхазии", "Abkhazia"),
    Country("tajikistan", ("Таджикистан",), "Таджикистан", "из Таджикистана", "Tajikistan"),
    Country("belarus", ("Беларусь",), "Беларусь", "из Беларуси", "Belarus"),
    Country("armenia", ("Армения",), "Армения", "из Армении", "Armenia"),
    Country("mongolia", ("Монголия",), "Монголия", "из Монголии", "Mongolia"),
    Country("kyrgyzstan", ("Киргизия", "Кыргызстан"), "Киргизия", "из Киргизии", "Kyrgyzstan"),
    Country("azerbaijan", ("Азербайджан",), "Азербайджан", "из Азербайджана", "Azerbaijan"),
    Country("georgia", ("Грузия",), "Грузия", "из Грузии", "Georgia"),
    Country("germany", ("Германия",), "Германия", "из Германии", "Germany"),
)
OUTBOUND_COUNTRIES: tuple[Country, ...] = (
    Country("turkey", ("Турция",), "Турция", "в Турцию", "Turkey"),
    Country("abkhazia", ("Абхазия",), "Абхазия", "в Абхазию", "Abkhazia"),
    Country("kazakhstan", ("Казахстан",), "Казахстан", "в Казахстан", "Kazakhstan"),
    Country("uae", ("Объединенные Арабские Эмираты", "ОАЭ"), "ОАЭ", "в ОАЭ", "United Arab Emirates"),
    Country("china", ("Китай",), "Китай", "в Китай", "China"),
    Country("egypt", ("Египет",), "Египет", "в Египет", "Egypt"),
    Country("georgia", ("Грузия",), "Грузия", "в Грузию", "Georgia"),
    Country("thailand", ("Таиланд", "Тайланд"), "Таиланд", "в Таиланд", "Thailand"),
    Country("armenia", ("Армения",), "Армения", "в Армению", "Armenia"),
    Country("uzbekistan", ("Узбекистан",), "Узбекистан", "в Узбекистан", "Uzbekistan"),
    Country("azerbaijan", ("Азербайджан",), "Азербайджан", "в Азербайджан", "Azerbaijan"),
    Country("vietnam", ("Вьетнам",), "Вьетнам", "во Вьетнам", "Vietnam"),
)


# Одно определение для русского и английского текста (круг наблюдателей, расхождение 15): формулировка Росстата.
TRIP_RU = ("Туристская поездка — пересечение границы с поездкой на срок меньше года с деловой, личной целью или для "
           "отдыха, кроме работы по найму; считаются поездки, а не люди и не ночёвки")
TRIP_EN = ("A tourist trip is a border crossing for a stay of less than a year for business, personal reasons or "
           "leisure, excluding work under contract; trips are counted, not people or nights")
# Чем ряд отличается от соседних (правка 25).
TRIP_VS_RU = (" Поэтому число въездных поездок не совпадает с иностранными гостями гостиниц: туда не входят те, кто жил "
              "у знакомых или в частном секторе, и входят повторные заселения.")
OUTBOUND_GAP_RU = (" С 2022 года данные о выезде неполные (пометка Росстата), поэтому сравнение с годами до 2022 "
                   "занижает выезд.")
OUTBOUND_GAP_EN = " From 2022 outbound data are incomplete, as noted by Rosstat."


def _fsb_series() -> list[TourSeries]:
    out: list[TourSeries] = []
    kw_in = "въездной туризм, иностранные туристы, иностранцы в России, въезд иностранцев, туристские поездки"
    kw_out = "выездной туризм, россияне за границей, выезд россиян, поездки за рубеж, туристские поездки"
    out.append(_s(
        "tour-inbound-trips", "Въездные туристские поездки иностранцев в Россию",
        "Inbound tourist trips to Russia", "тыс. поездок", "thousand trips", "quarterly", SRC_FSB,
        ROSSTAT_TOURISM_URL, "rosstat_tourism_trips",
        {"trips_direction": "inbound", "alternate_frequencies": {"monthly": "tour-inbound-trips-monthly"}},
        "Сколько туристских поездок в Россию совершили иностранцы за квартал, тысяч. " + TRIP_RU + "." + TRIP_VS_RU
        + " Данные с 2015 года.",
        "Tourist trips to Russia by foreign citizens per quarter, thousand. " + TRIP_EN + ". Data since 2015.", _M_FSB, _M_FSB_EN, kw_in, "по кварталам с 2015 года и по месяцам с 2022 года",
        family="T9", forecast="generic_quarterly",
    ))
    out.append(_s(
        "tour-inbound-trips-monthly", "Въездные туристские поездки иностранцев в Россию (месячный ряд)",
        "Inbound tourist trips to Russia (monthly)", "тыс. поездок", "thousand trips", "monthly", SRC_FSB,
        ROSSTAT_TOURISM_URL, "rosstat_tourism_trips",
        {"trips_direction": "inbound", "trips_monthly": True, "primary_indicator_code": "tour-inbound-trips"},
        "Сколько туристских поездок в Россию совершили иностранцы за месяц, тысяч. " + TRIP_RU + ". Месяц — "
        "разность итогов с начала года, с 2023 года итог округлён до 10 тыс. Данные с 2022 года.",
        "Tourist trips to Russia by foreign citizens per month, thousand. " + TRIP_EN + ". Data since 2022.", _M_FSB_MONTHLY, _M_FSB_MONTHLY_EN, kw_in, "по месяцам с 2022 года",
        family="T6", listed=False,
    ))
    out.append(_s(
        "tour-outbound-trips", "Выездные туристские поездки россиян за рубеж",
        "Outbound tourist trips by Russian citizens", "тыс. поездок", "thousand trips", "quarterly", SRC_FSB,
        ROSSTAT_TOURISM_URL, "rosstat_tourism_trips", {"trips_direction": "outbound"},
        "Сколько туристских поездок за границу совершили россияне за квартал, тысяч. " + TRIP_RU + "."
        + OUTBOUND_GAP_RU + " Данные с 2015 года.",
        "Tourist trips abroad by Russian citizens per quarter, thousand. " + TRIP_EN + "." + OUTBOUND_GAP_EN
        + " Data since 2015.", _M_FSB, _M_FSB_EN, kw_out, "по кварталам с 2015 года",
        # Прогноз снят (расхождение 10): с 2022 года ряд неполный, модель училась бы на смене полноты, а не на спросе.
        family="T9",
    ))
    for direction, countries in (("inbound", INBOUND_COUNTRIES), ("outbound", OUTBOUND_COUNTRIES)):
        for c in countries:
            if direction == "inbound":
                name = f"Въездные туристские поездки в Россию: {c.name}"
                name_en = f"Inbound tourist trips to Russia: {c.name_en}"
                desc = (f"Сколько туристских поездок в Россию совершили гости {c.loc} за квартал, тысяч. "
                        f"{TRIP_RU}. Данные с 2015 года.")
                desc_en = (f"Tourist trips to Russia by citizens of {c.name_en} per quarter, thousand. {TRIP_EN}. "
                           "Data since 2015.")
                kws = f"туристы {c.loc}, {c.name}, {kw_in}"
                seo = (f"Туристы {c.loc} в России — число поездок по кварталам и годам",
                       f"Сколько туристских поездок в Россию совершили гости {c.loc}: данные "
                       "Росстата по сведениям ФСБ России по кварталам с 2015 года, тысяч поездок, суммы за год.")
            else:
                name = f"Выездные туристские поездки россиян: {c.name}"
                name_en = f"Outbound tourist trips by Russians: {c.name_en}"
                desc = (f"Сколько туристских поездок {c.loc} совершили россияне за квартал, тысяч. {TRIP_RU}."
                        f"{OUTBOUND_GAP_RU} Данные с 2015 года.{_COUNTRY_NOTE.get(c.slug, '')}")
                desc_en = (f"Tourist trips by Russian citizens to {c.name_en} per quarter, thousand. {TRIP_EN}."
                           f"{OUTBOUND_GAP_EN} Data since 2015.")
                kws = f"россияне {c.loc}, поездки {c.loc}, туристы {c.loc}, {c.name}, {kw_out}"
                seo = (f"Сколько россиян ездят {c.loc} — поездки по кварталам и годам",
                       f"Сколько раз россияне ездили {c.loc}: данные Росстата по сведениям ФСБ России по кварталам "
                       "с 2015 года, тысяч поездок, суммы за год и изменение к прошлому году.")
            out.append(_s(
                f"tour-{direction}-{c.slug}", name, name_en, "тыс. поездок", "thousand trips", "quarterly",
                SRC_FSB, ROSSTAT_TOURISM_URL, "rosstat_tourism_trips",
                {"trips_direction": direction, "trips_country": list(c.labels)},
                desc, desc_en, _M_FSB, _M_FSB_EN, kws, "по кварталам с 2015 года",
                family="T9", listed=False, seo_title=seo[0], seo_description=seo[1],
            ))
    return out


# ── Росстат: туристская индустрия в экономике ────────────────────────────────

def _gva_series() -> list[TourSeries]:
    kw = "туризм в ВВП, доля туризма в экономике, туристская индустрия, добавленная стоимость туризма, ВДС"
    return [
        _s("tour-gva", "Добавленная стоимость туристской индустрии", "Gross value added of the tourism industry",
           "млрд руб.", "RUB bn", "quarterly", SRC_ROSSTAT, ROSSTAT_TOURISM_URL, "rosstat_tourism_gva",
           {"gva_table": "value_quarterly"},
           "Вклад туризма в экономику России: добавленная стоимость гостиниц, общепита, пассажирского "
           "транспорта, турфирм и других отраслей в части услуг туристам, млрд рублей в текущих ценах. С 2017 года.",
           "The tourism industry's contribution to Russia's economy: value added by hotels, food services, "
           "passenger transport, travel agencies and other industries serving visitors, RUB billion at current "
           "prices. Since 2017.", _M_GVA, _M_GVA_EN, kw, "Росстата по кварталам и годам с 2017 года",
           family="T9", forecast="generic_quarterly"),
        _s("tour-gva-share", "Доля туризма в ВВП России", "Tourism industry share of Russia's GDP", "%", "%",
           "quarterly", SRC_ROSSTAT, ROSSTAT_TOURISM_URL, "rosstat_tourism_gva",
           {"gva_table": "share_quarterly", "alternate_frequencies": {"annual": "tour-gva-share-annual"}},
           "Доля добавленной стоимости туристской индустрии в валовом внутреннем продукте России, процентов, "
           "по кварталам с 2017 года.",
           "Tourism industry gross value added as a share of Russia's GDP, per cent, quarterly since 2017.",
           _M_GVA, _M_GVA_EN, f"доля туризма в ВВП, {kw}", "Росстата по кварталам и годам с 2017 года",
           min_value=0.0),
        _s("tour-gva-share-annual", "Доля туризма в ВВП России (годовой ряд)",
           "Tourism industry share of Russia's GDP (annual)", "%", "%", "annual", SRC_ROSSTAT,
           ROSSTAT_TOURISM_URL, "rosstat_tourism_gva",
           {"gva_table": "share_annual", "primary_indicator_code": "tour-gva-share"},
           "Доля добавленной стоимости туристской индустрии в валовом внутреннем продукте России за год, "
           "процентов, с 2017 года.",
           "Tourism industry gross value added as a share of Russia's GDP for the year, per cent, since 2017.",
           _M_GVA, _M_GVA_EN, f"доля туризма в ВВП, {kw}", "Росстата по годам с 2017 года",
           family="T10a", yoy_unit="п.п.", listed=False),
        _s("tour-gva-volume", "Реальный рост туристской индустрии", "Real growth of the tourism industry",
           "%", "%", "quarterly", SRC_ROSSTAT, ROSSTAT_TOURISM_URL, "rosstat_tourism_gva",
           {"gva_table": "volume_quarterly"},
           "Индекс физического объёма добавленной стоимости туристской индустрии: квартал к тому же кварталу "
           "прошлого года, в процентах, без влияния цен. Выше 100 — туриндустрия выросла. С 2018 года.",
           "Volume index of tourism industry gross value added, quarter on the same quarter of the previous year, "
           "per cent, excluding price changes. Above 100 means growth. Since 2018.",
           _M_GVA, _M_GVA_EN, f"рост туризма, {kw}", "Росстата по кварталам с 2018 года",
           listed=False, min_value=0.0),
    ]


# ── ЕМИСС: транспорт, размещение, турфирмы ───────────────────────────────────

AIR_DIMS = ("37001", "37002")   # регулярность, вид сообщения
AIRPORTS: tuple[tuple[str, str, str, str], ...] = (
    ("sheremetyevo", "Москва(Шереметьево)", "Шереметьево", "Moscow Sheremetyevo"),
    ("vnukovo", "Москва(Внуково)", "Внуково", "Moscow Vnukovo"),
    ("domodedovo", "Москва(Домодедово)", "Домодедово", "Moscow Domodedovo"),
    ("pulkovo", "Санкт-Петербург (Пулково)", "Пулково", "St Petersburg Pulkovo"),
    ("koltsovo", "Екатеринбург (Кольцово)", "Кольцово", "Yekaterinburg Koltsovo"),
    ("tolmachevo", "Новосибирск (Толмачево)", "Толмачёво", "Novosibirsk Tolmachevo"),
)


def _emiss(dataset: int, period: str, *, match: dict | None = None, sum_dims: tuple[str, ...] = (),
           scale: float = 1.0, ratio_of: int | None = None, first_year: int | None = None) -> dict:
    cfg = {"emiss_dataset": dataset, "emiss_period": period, "emiss_match": match or {},
           "emiss_sum_dims": list(sum_dims), "emiss_scale": scale}
    if ratio_of:
        cfg["emiss_ratio_of"] = ratio_of
    if first_year:
        cfg["emiss_first_year"] = first_year
    return cfg


def _emiss_series() -> list[TourSeries]:
    out: list[TourSeries] = []
    kw_air = "авиаперевозки, пассажиропоток авиакомпаний, авиапассажиры, авиация, перелёты, Росавиация"
    reg, msg = AIR_DIMS
    air = [
        ("tour-air-passengers", "Пассажиры российских авиакомпаний", "Passengers of Russian airlines", {},
         "Сколько пассажиров перевезли российские авиакомпании за месяц на внутренних и международных, "
         "регулярных и чартерных рейсах, тысяч человек. С 2009 года.",
         "Passengers carried by Russian airlines per month on domestic and international, scheduled and charter "
         "flights, thousand people. Since 2009.", "", True, "monthly_auto"),
        ("tour-air-passengers-domestic", "Пассажиры авиакомпаний на внутренних рейсах",
         "Airline passengers on domestic flights", {msg: ["Внутренние перевозки"]},
         "Сколько пассажиров перевезли российские авиакомпании за месяц между городами России, тысяч человек. "
         "С 2009 года.", "Passengers carried by Russian airlines between Russian cities per month, thousand "
         "people. Since 2009.", "внутренние авиаперевозки, полёты по России", False, "monthly_auto"),
        ("tour-air-passengers-international", "Пассажиры авиакомпаний на международных рейсах",
         "Airline passengers on international flights", {msg: ["Международные перевозки"]},
         "Сколько пассажиров перевезли российские авиакомпании за месяц на рейсах за рубеж и обратно, тысяч "
         "человек. С 2009 года.", "Passengers carried by Russian airlines on flights abroad and back per "
         "month, thousand people. Since 2009.", "международные авиаперевозки, полёты за границу", False,
         "monthly_auto"),
        ("tour-air-passengers-charter", "Пассажиры чартерных рейсов российских авиакомпаний",
         "Charter passengers of Russian airlines", {reg: ["Нерегулярные коммерческие перевозки"]},
         "Сколько пассажиров перевезли российские авиакомпании за месяц на нерегулярных (чартерных) рейсах — в "
         "основном туристы по путёвкам, тысяч человек. С 2009 года.", "Passengers carried by Russian airlines "
         "on non-scheduled (charter) flights per month, mostly package tourists, thousand people. Since 2009.",
         "чартеры, чартерные рейсы, туристические перелёты", False, None),
    ]
    for code, name, name_en, match, desc, desc_en, kw_extra, listed, fc in air:
        out.append(_s(
            code, name, name_en, "тыс. чел.", "thousand people", "monthly", SRC_FAVT, FEDSTAT.format(37022),
            "rosstat_emiss_tourism",
            _emiss(37022, "monthly", match=match, sum_dims=tuple(d for d in AIR_DIMS if d not in match),
                   scale=0.001),
            desc, desc_en, _M_AIR, _M_AIR_EN, ", ".join(x for x in (kw_extra, kw_air) if x),
            "Росавиации по месяцам с 2009 года", family="T6", forecast=fc, listed=listed,
        ))
    out.append(_s(
        "tour-air-load-factor", "Занятость кресел в самолётах российских авиакомпаний",
        "Passenger load factor of Russian airlines", "%", "%", "monthly", SRC_FAVT, FEDSTAT.format(37020),
        "rosstat_emiss_tourism", _emiss(37020, "monthly", sum_dims=AIR_DIMS, ratio_of=37019),
        "Какая доля пассажирских кресел была занята: выполненный пассажирооборот, делённый на предельный "
        "(все кресла на всех рейсах), в процентах. С 2009 года.",
        "Share of seats occupied: revenue passenger-kilometres divided by available seat-kilometres, per cent. "
        "Since 2009.",
        _M_AIR + " Занятость кресел — отношение выполненного пассажирооборота к предельному: пассажиро-километры "
        "проданных мест к пассажиро-километрам всех кресел.",
        _M_AIR_EN + " The load factor is revenue passenger-kilometres divided by available seat-kilometres.",
        "загрузка самолётов, занятость кресел, коэффициент загрузки, " + kw_air,
        "Росавиации по месяцам с 2009 года", family="T2y", yoy_unit="п.п.",
    ))
    for slug, label, short, short_en in AIRPORTS:
        out.append(_s(
            f"tour-airport-{slug}", f"Пассажиропоток аэропорта {short}", f"{short_en} airport passenger traffic",
            "тыс. чел.", "thousand people", "monthly", SRC_FAVT, FEDSTAT.format(37015), "rosstat_emiss_tourism",
            _emiss(37015, "monthly", match={"36292": [label]}, sum_dims=("37000", *AIR_DIMS), scale=0.001),
            f"Сколько пассажиров улетело и прилетело через аэропорт {short} за месяц, тысяч человек. С 2018 года.",
            f"Departing and arriving passengers at {short_en} airport per month, thousand people. Since 2018.",
            _M_AIRPORT, _M_AIRPORT_EN, f"аэропорт {short}, пассажиропоток {short}, {kw_air}",
            "Росавиации по месяцам с 2018 года", family="T6", listed=slug == "sheremetyevo",
        ))
    kw_rail = "железная дорога, поезда, пассажиры поездов, РЖД, железнодорожные перевозки"
    out.append(_s(
        "tour-rail-passengers", "Пассажиры железнодорожного транспорта", "Railway passengers", "млн чел.",
        "million people", "monthly", SRC_ROSSTAT, FEDSTAT.format(31315), "rosstat_emiss_tourism",
        _emiss(31315, "monthly", match={"58787": ["Железнодорожный транспорт"]}),
        "Сколько пассажиров перевёз железнодорожный транспорт общего пользования за месяц — поезда дальнего "
        "следования и пригородные, миллионов человек. С 2016 года.",
        "Passengers carried by public railway transport per month, long-distance and suburban trains, million "
        "people. Since 2016.", _M_RAIL, _M_RAIL_EN, kw_rail, "Росстата по месяцам с 2016 года",
        family="T6", forecast="monthly_auto",
    ))
    out.append(_s(
        "tour-rail-passenger-km", "Пассажирооборот железнодорожного транспорта", "Railway passenger-kilometres",
        "млрд пасс.-км", "billion passenger-km", "monthly", SRC_ROSSTAT, FEDSTAT.format(31313),
        "rosstat_emiss_tourism", _emiss(31313, "monthly", match={"58787": ["Железнодорожный транспорт"]}),
        "Сколько километров проехали все пассажиры железной дороги за месяц, миллиардов пассажиро-километров. "
        "Дальние поездки весят больше пригородных, поэтому ряд лучше показывает междугородные путешествия. "
        "С 2016 года.",
        "Total distance travelled by all railway passengers per month, billion passenger-kilometres. Long trips "
        "weigh more than suburban ones, so the series reflects intercity travel better. Since 2016.",
        _M_RAIL, _M_RAIL_EN, f"пассажирооборот, {kw_rail}", "Росстата по месяцам с 2016 года",
        family="T6", listed=False,
    ))
    kw_hotel = "гостиницы, отели, средства размещения, туристы в гостиницах, гостиничный бизнес"
    annual_ksr = [
        ("tour-hotel-guests", 31560, "Размещённые в гостиницах и других средствах размещения",
         "Guests in hotels and other accommodation", "млн чел.", "million people", 1e-6, True, "annual_auto",
         "Сколько человек за год заселилось в гостиницы, хостелы, базы отдыха, санатории и другие коллективные "
         "средства размещения России, миллионов. Считается заселение, а не человек и не поездка: при двух заездах "
         "гость учтён дважды; сюда входят и россияне, а туристы в частном секторе — нет. Поэтому число не совпадает "
         "ни с въездом через границу, ни с турпотоком. С 2002 года.",
         "Check-ins in hotels, hostels, holiday centres, health resorts and other collective accommodation in "
         "Russia during the year, million people. Since 2002.", "размещённые лица, гости гостиниц"),
        ("tour-hotel-nights", 31587, "Ночёвки в гостиницах и других средствах размещения",
         "Nights spent in hotels and other accommodation", "млн ночёвок", "million nights", 1e-6, False,
         "annual_auto",
         "Сколько ночей за год провели гости в гостиницах и других коллективных средствах размещения России, "
         "миллионов ночёвок. Ночёвка — одна ночь одного гостя; это полный годовой итог, он больше суммы оперативных "
         "месячных данных. С 2002 года.",
         "Nights spent by guests in hotels and other collective accommodation in Russia during the year, million "
         "nights. Since 2002.", "ночёвки, гостиничные ночи"),
        ("tour-hotel-count", 31579, "Число гостиниц и других средств размещения",
         "Number of hotels and other accommodation establishments", "ед.", "units", 1.0, False, None,
         "Сколько гостиниц, хостелов, баз отдыха, санаториев и других коллективных средств размещения работало в "
         "России, на конец года. С 2002 года.",
         "Number of hotels, hostels, holiday centres, health resorts and other collective accommodation "
         "establishments operating in Russia at year end. Since 2002.", "число гостиниц, количество отелей"),
        ("tour-hotel-rooms", 31586, "Номерной фонд гостиниц и других средств размещения",
         "Rooms in hotels and other accommodation", "тыс. номеров", "thousand rooms", 0.001, False, None,
         "Сколько номеров в гостиницах и других коллективных средствах размещения России, тысяч, на конец года. "
         "С 2002 года.", "Number of rooms in hotels and other collective accommodation in Russia at year end, "
         "thousand. Since 2002.", "номерной фонд, номера в гостиницах"),
        ("tour-hotel-beds", 31583, "Число мест в гостиницах и других средствах размещения",
         "Bed places in hotels and other accommodation", "тыс. мест", "thousand bed places", 0.001, False, None,
         "Сколько спальных мест в гостиницах и других коллективных средствах размещения России, тысяч, на конец "
         "года. С 2002 года.", "Number of bed places in hotels and other collective accommodation in Russia at "
         "year end, thousand. Since 2002.", "койко-места, места в гостиницах"),
        ("tour-hotel-revenue", 31003, "Доходы гостиниц и других средств размещения",
         "Revenue of hotels and other accommodation", "млрд руб.", "RUB bn", 1e-6, False, None,
         "Сколько заработали гостиницы и другие коллективные средства размещения России на услугах за год, "
         "миллиардов рублей без НДС. С 2002 года.", "Revenue from services of hotels and other collective "
         "accommodation in Russia during the year, RUB billion excluding VAT. Since 2002.",
         "доходы гостиниц, выручка отелей"),
    ]
    for code, ds, name, name_en, unit, unit_en, scale, listed, fc, desc, desc_en, kw_extra in annual_ksr:
        out.append(_s(
            code, name, name_en, unit, unit_en, "annual", SRC_ROSSTAT, FEDSTAT.format(ds), "rosstat_emiss_tourism",
            _emiss(ds, "annual", scale=scale), desc, desc_en, _M_KSR, _M_KSR_EN, f"{kw_extra}, {kw_hotel}",
            "Росстата по годам с 2002 года", family="T10", forecast=fc, listed=listed,
        ))
    out.append(_s(
        "tour-hotel-nights-monthly", "Ночёвки в гостиницах по месяцам", "Nights spent in hotels by month",
        "млн ночёвок", "million nights", "monthly", SRC_ROSSTAT, FEDSTAT.format(62301), "rosstat_emiss_tourism",
        _emiss(62301, "ytd_monthly", scale=1e-6),
        "Сколько ночей за месяц провели гости в гостиницах и других коллективных средствах размещения России, "
        "миллионов ночёвок, по оперативным данным. Месяц — разность итогов с начала года; охват оперативного "
        "наблюдения уже годового, поэтому сумма месяцев меньше годового числа ночёвок (за 2025 год 352,6 млн против "
        "395,4 млн). С 2023 года.",
        "Nights spent by guests in hotels and other collective accommodation in Russia per month, million nights, "
        "preliminary data. Since 2023.", _M_KSR_MONTHLY, _M_KSR_MONTHLY_EN,
        f"ночёвки по месяцам, загрузка гостиниц, сезон, {kw_hotel}", "Росстата по месяцам с 2023 года",
        family="T6",
    ))
    kw_san = "санатории, санаторно-курортный отдых, курорты, лечение на курортах"
    sanatoria = [
        ("tour-sanatorium-guests", 42102, "Размещённые в санаториях", "Guests in health resorts", "млн чел.",
         "million people", 1e-6, True, "annual_auto",
         "Сколько человек за год заехало в санатории и другие санаторно-курортные организации России, "
         "миллионов. С 2002 года.", "Check-ins in sanatoria and other health resort organisations in Russia "
         "during the year, million people. Since 2002.", "Росстата по годам с 2002 года"),
        ("tour-sanatorium-nights", 42103, "Ночёвки в санаториях", "Nights spent in health resorts",
         "млн ночёвок", "million nights", 1e-6, False, None,
         "Сколько ночей за год провели гости санаториев и других санаторно-курортных организаций России, "
         "миллионов. С 2005 года.", "Nights spent in sanatoria and other health resort organisations in Russia "
         "during the year, million nights. Since 2005.", "Росстата по годам с 2005 года"),
        ("tour-sanatorium-revenue", 42101, "Доходы санаториев", "Revenue of health resorts", "млрд руб.",
         "RUB bn", 1e-6, False, None,
         "Сколько заработали санатории и другие санаторно-курортные организации России на услугах за год, "
         "миллиардов рублей без НДС. С 2003 года.", "Revenue from services of sanatoria and other health resort "
         "organisations in Russia during the year, RUB billion excluding VAT. Since 2003.",
         "Росстата по годам с 2003 года"),
    ]
    for code, ds, name, name_en, unit, unit_en, scale, listed, fc, desc, desc_en, period in sanatoria:
        out.append(_s(
            code, name, name_en, unit, unit_en, "annual", SRC_ROSSTAT, FEDSTAT.format(ds), "rosstat_emiss_tourism",
            _emiss(ds, "annual", scale=scale), desc, desc_en, _M_SAN, _M_SAN_EN, kw_san, period,
            family="T10", forecast=fc, listed=listed,
        ))
    out.append(_s(
        "tour-agencies", "Число туроператоров и турагентств", "Number of tour operators and travel agencies",
        "ед.", "units", "annual", SRC_ROSSTAT, FEDSTAT.format(31615), "rosstat_emiss_tourism",
        _emiss(31615, "annual", match={"58427": ["Всего"]}),
        "Сколько организаций и предпринимателей в России занимались туроператорской, турагентской и "
        "экскурсионной деятельностью за год. С 2004 года.",
        "Number of organisations and entrepreneurs in Russia engaged in tour operator, travel agency and "
        "excursion activity during the year. Since 2004.", _M_FIRMS, _M_FIRMS_EN,
        "турфирмы, туроператоры, турагентства, число турфирм", "Росстата по годам с 2004 года", family="T10",
    ))
    return out


# ── Россияне в странах назначения по данным этих стран (t3, 20.11.2026) ──────

_M_DEST = (
    "Ряд построен по статистике страны назначения, а не российской: страна считает прибывших граждан России по "
    "своим правилам (на границе или в гостиницах, с туристскими или любыми целями), поэтому числа не совпадают с "
    "выездом россиян по данным пограничной службы ФСБ России. Кипр, Грузия и Турция — на страницах этих стран. "
    "Источник не публикует ряд в машиночитаемом виде, данные обновляются вручную."
)
_M_DEST_EN = (
    "The series comes from the destination country's statistics, not Russia's: the country counts arriving Russian "
    "citizens under its own rules (at the border or in hotels, for tourism or any purpose), so the figures differ "
    "from outbound trips recorded by the Russian border service. Cyprus, Georgia and Turkey are on those countries' "
    "pages. The source does not publish the series in machine-readable form; data are updated manually."
)

DEST_URLS = {
    "EG": "https://sdmx.oecd.org/public/rest/data/OECD.CFE.TOU,DSD_TOURISM_INTER@DF_INBOUND/all",
    "TH": "https://www.mots.go.th/news/category/411",
    "UZ": "https://api.siat.stat.uz/media/uploads/sdmx/sdmx_data_1031.json",
    "KZ": "https://stat.gov.kz/ru/industries/business-statistics/stat-tourism/",
    "VN": "https://vietnamtourism.gov.vn/en/statistic/international",
    "MV": "https://statisticsmaldives.gov.mv/yearbook/2026/",
    "MV-M": "https://statisticsmaldives.gov.mv/yearbook/2026/",
    "ID": "https://www.bps.go.id/en/statistics-table/2/MTQ3MCMy/",
    "LK": "https://www.sltda.gov.lk/en/monthly-tourist-arrivals-reports-2026",
    "BY": "https://www.belstat.gov.by/ofitsialnaya-statistika/realny-sector-ekonomiki/turizm/",
    "SC": "https://www.nbs.gov.sc/component/edocman/2042-visitor-arrivals-data-series-2/download",
    "DO": "https://www.bancentral.gov.do/a/d/2537-sector-turismo",
    "MN": "https://data.1212.mn/api/v1/en/NSO/Industry,%20service/Tourism",
    "MN-M": "https://data.1212.mn/api/v1/en/NSO/Industry,%20service/Tourism",
    "MU": "https://statsmauritius.govmu.org/Pages/Statistics/By_Subject/Tourism/SB_Tourism.aspx",
    "MU-M": "https://statsmauritius.govmu.org/Pages/Statistics/By_Subject/Tourism/SB_Tourism.aspx",
    "TZ-ZN": "http://ocgs.go.tz/publication-list/24",
    "CU": "https://onei.gob.cu/turismo-0",
    "TJ": "https://www.stat.tj/ru/v-2025-godu-bolee-21-milliona-inostranczev-posetili-tadzhikistan/",
    "AE-DU": "https://www.dubaidet.gov.ae/en/research-and-insights/annual-visitor-report-2025",
    "UZ-M": "https://stat.uz/ru/press-tsentr/novosti-goskomstata",
    "HK-M": "https://partnernet.hktb.com/en/research_statistics/research_publications/index.html?id=3631",
    "PH": "http://tourism.gov.ph/Tourism_demand/",
    "PH-M": "http://tourism.gov.ph/Tourism_demand/",
    "KG": "https://www.stat.gov.kg/ru/statistics/turizm/",
    "AE-AZ": "https://dct.gov.ae/en/",
    "AE-DU-RU": "https://www.dubaidet.gov.ae/en/research-and-insights/",
    "AB": "https://cgsra.org/media/files/25.pdf",
    "MO": "https://dataplus.macaotourism.gov.mo/Publication/document/ENG/Book/VAHightlights/",
    "MO-YTD": "https://dataplus.macaotourism.gov.mo/Publication/document/ENG/Book/VAHightlights/",
}

DESTINATIONS: tuple[tuple[str, str, str, str, str, str, str, str, str], ...] = (
    # slug, iso2, вид периода, частота, страна (вин.), страна en, источник, период для описания, слово «прибытия»
    ("egypt", "EG", "annual", "annual", "Египет", "Egypt", "ОЭСР по данным Египта", "с 2008 года", "Туристы из России"),
    ("thailand", "TH", "monthly", "monthly", "Таиланд", "Thailand", "Министерство туризма и спорта Таиланда",
     "с 2025 года", "Туристы-граждане России"),
    ("uzbekistan", "UZ", "annual", "annual", "Узбекистан", "Uzbekistan", "Нацкомстат Узбекистана", "с 2014 года",
     "Граждане России, въехавшие с туристскими целями"),
    ("kazakhstan", "KZ", "ytd_quarterly", "quarterly", "Казахстан", "Kazakhstan",
     "Бюро национальной статистики Казахстана", "с 2026 года", "Посетители — граждане России (пересечения границы)"),
    # c5, 20.11.2026: страны без своей страницы на сайте. Десятый элемент — шаблон режимов (у рядов с пропусками
    # месяцев его нет: сумма за год по неполному году была бы занижена), одиннадцатый — подпись в группе.
    ("vietnam", "VN", "monthly", "monthly", "Вьетнам", "Vietnam", "Национальное управление туризма Вьетнама",
     "с 2012 года (часть месяцев не опубликована)", "Иностранные гости — граждане России", None, "Вьетнам"),
    ("maldives", "MV", "annual", "annual", "Мальдивы", "Maldives", "Бюро статистики Мальдив", "с 2012 года",
     "Туристы — граждане России", "T10", "Мальдивы"),
    ("maldives-monthly", "MV-M", "monthly", "monthly", "Мальдивы", "Maldives", "Бюро статистики Мальдив",
     "2018–2025 годов (2019–2020 — не все месяцы)", "Туристы — граждане России", None, "Мальдивы по месяцам"),
    ("indonesia", "ID", "monthly", "monthly", "Индонезия", "Indonesia", "Статистическое агентство Индонезии",
     "с 2017 года", "Иностранные туристы — граждане России (Бали и вся страна)", "T6", "Индонезия"),
    ("sri-lanka", "LK", "monthly", "monthly", "Шри-Ланка", "Sri Lanka", "Управление по развитию туризма Шри-Ланки",
     "с марта 2017 года (отчёты за три месяца 2017 года не найдены)", "Туристы — граждане России", None, "Шри-Ланка"),
    ("belarus", "BY", "annual", "annual", "Беларусь", "Belarus", "Белстат", "2021–2025 годов (кроме 2023)",
     "Организованные туристы и экскурсанты из России, принятые турфирмами Беларуси", "T10", "Беларусь"),
    ("seychelles", "SC", "monthly", "monthly", "Сейшелы", "Seychelles", "Национальное бюро статистики Сейшел",
     "с 2000 года", "Гости из России", "T6", "Сейшелы"),
    ("dominican-republic", "DO", "monthly", "monthly", "Доминикана", "Dominican Republic",
     "Центральный банк Доминиканской Республики", "с 2000 года (часть месяцев не опубликована)",
     "Граждане России, прилетевшие самолётом", None, "Доминикана"),
    ("mongolia", "MN", "annual", "annual", "Монголия", "Mongolia", "Национальная статистическая служба Монголии",
     "с 1999 года", "Иностранные туристы — граждане России", "T10", "Монголия"),
    ("mongolia-monthly", "MN-M", "monthly", "monthly", "Монголия", "Mongolia",
     "Национальная статистическая служба Монголии", "с 2023 года", "Иностранные туристы — граждане России", "T6",
     "Монголия по месяцам"),
    ("mauritius", "MU", "annual", "annual", "Маврикий", "Mauritius", "Statistics Mauritius", "с 1996 года",
     "Туристы, проживающие в России", "T10", "Маврикий"),
    ("mauritius-monthly", "MU-M", "monthly", "monthly", "Маврикий", "Mauritius", "Statistics Mauritius",
     "с 2025 года", "Туристы, проживающие в России", "T6", "Маврикий по месяцам"),
    ("zanzibar", "TZ-ZN", "monthly", "monthly", "Занзибар", "Zanzibar", "Управление статистики Занзибара",
     "с 2015 года (часть месяцев не опубликована)", "Иностранные гости — граждане России", None, "Занзибар"),
    ("cuba", "CU", "annual", "annual", "Куба", "Cuba", "Национальное статистическое управление Кубы",
     "1993–2022 годов (по странам позже не публиковалось)", "Гости из России", "T10", "Куба"),
    ("tajikistan", "TJ", "annual", "annual", "Таджикистан", "Tajikistan", "Агентство по статистике Таджикистана",
     "за 2025 год (публикуется только в новостях агентства)", "Въехавшие граждане России", None, "Таджикистан"),
    ("dubai", "AE-DU", "annual", "annual", "Дубай (ОАЭ)", "Dubai (UAE)", "Департамент экономики и туризма Дубая",
     "за 2025 год", "Гости с ночёвкой из СНГ и Восточной Европы вместе с Россией (Россию отдельно Дубай не "
     "публикует)", None, "Дубай: СНГ и Восточная Европа"),
    # g2/g3, 20.11.2026 (ночь).
    ("uzbekistan-monthly", "UZ-M", "monthly", "monthly", "Узбекистан", "Uzbekistan", "Нацкомстат Узбекистана",
     "с 2022 года (25 месяцев, собраны из пресс-релизов)", "Граждане России, въехавшие с туристскими целями", None,
     "Узбекистан по месяцам"),
    ("hong-kong", "HK-M", "monthly", "monthly", "Гонконг", "Hong Kong", "Совет по туризму Гонконга",
     "с мая 2021 года", "Гости — граждане России", None, "Гонконг"),
    ("philippines", "PH", "annual", "annual", "Филиппины", "Philippines", "Министерство туризма Филиппин",
     "2007–2023 годов (2022 не опубликован)", "Гости, проживающие в России", "T10", "Филиппины"),
    ("philippines-monthly", "PH-M", "monthly", "monthly", "Филиппины", "Philippines",
     "Министерство туризма Филиппин", "2008 — января 2025 года (без 2022 и части 2024)",
     "Гости, проживающие в России", None, "Филиппины по месяцам"),
    ("kyrgyzstan", "KG", "annual", "annual", "Киргизия", "Kyrgyzstan", "Нацстатком Киргизии", "с 2008 года",
     "Въезды граждан России через границу (пересечения, а не люди)", "T10", "Киргизия"),
    ("abu-dhabi", "AE-AZ", "annual", "annual", "Абу-Даби (ОАЭ)", "Abu Dhabi (UAE)",
     "Департамент культуры и туризма Абу-Даби", "за 2025 год", "Гости гостиниц — граждане России", None, "Абу-Даби"),
    ("dubai-russia", "AE-DU-RU", "annual", "annual", "Дубай (ОАЭ)", "Dubai (UAE)",
     "Департамент экономики и туризма Дубая", "за 2019 год (позже Дубай Россию отдельно не публикует)",
     "Гости с ночёвкой из России", None, "Дубай: Россия, 2019"),
    ("macao", "MO", "annual", "annual", "Макао", "Macao", "Управление по туризму Макао",
     "только за 2020 и 2025 годы (полные годы, которые удалось найти)", "Гости — граждане России", None, "Макао"),
    ("macao-ytd", "MO-YTD", "monthly", "monthly", "Макао", "Macao", "Управление по туризму Макао",
     "с 2019 года, с пропусками: нарастающий итог с начала года, а не значение месяца",
     "Гости — граждане России нарастающим итогом с начала года", None, "Макао с начала года"),
    ("abkhazia", "AB", "annual", "annual", "Абхазия", "Abkhazia", "Управление государственной статистики Абхазии",
     "с 2012 года", "Размещённые в гостиницах, санаториях и домах отдыха — все гости, не только из России", "T10",
     "Абхазия"),
)

# Подпись в группе и шаблон режимов для первых четырёх стран (кортежи без хвоста).
_DEST_DEFAULT_TAIL = {"egypt": ("T10", "Египет"), "thailand": (None, "Таиланд"), "uzbekistan": ("T10", "Узбекистан"),
                      "kazakhstan": (None, "Казахстан")}


def _dest_series() -> list[TourSeries]:
    out = []
    per = {"annual": "за год", "monthly": "за месяц", "quarterly": "за квартал"}
    per_en = {"annual": "per year", "monthly": "per month", "quarterly": "per quarter"}
    for slug, iso2, kind, freq, country, country_en, source, since, who, *tail in DESTINATIONS:
        family, _label = tail or _DEST_DEFAULT_TAIL[slug]
        name = f"Прибытия россиян: {country} (данные страны)"
        name_en = f"Russian arrivals in {country_en} (destination data)"
        if slug == "macao-ytd":
            name = "Прибытия россиян: Макао (данные страны, с начала года)"
            name_en = "Russian arrivals in Macao (destination data, year to date)"
        if slug.endswith("-monthly"):
            name, name_en = name.replace("(данные страны)", "(данные страны, по месяцам)"), name_en + ", monthly"
        meth, meth_en = _M_DEST, _M_DEST_EN
        if slug == "dubai":
            name = "Дубай: гости из СНГ и Восточной Европы, включая Россию"
            name_en = "Dubai: visitors from the CIS and Eastern Europe, including Russia"
        if slug == "egypt":
            meth = meth + (" Россия считает выезд в Египет по данным пограничной службы (ряд «Выездные туристские "
                           "поездки россиян: Египет»): за 2025 год 1 947,8 тыс. против 2 224,7 тыс. у Египта — это "
                           "два разных счёта.")
        if slug == "abkhazia":
            name = "Абхазия: размещённые в гостиницах и санаториях"
            name_en = "Abkhazia: guests in hotels and health resorts"
            meth = (
                "Официальная статистика Абхазии («Абхазия в цифрах»): учтённые гостиницы, санатории, пансионаты и "
                "дома отдыха; частный сектор не входит. Значение 2014 года в сборнике повторяет 2013 год и не "
                "показано. Отдельно — оценка Министерства туризма Абхазии, методика которой не опубликована: около "
                "1,38 млн гостей в 2024 году, 1,88 млн туристов и экскурсантов из России в 2025 году (вместе с "
                "экскурсантами из Сочи), 1,74 млн за январь–сентябрь 2026 года. Выезд россиян в Абхазию по данным "
                "пограничной службы ФСБ России — в ряду «Выездные туристские поездки россиян: Абхазия»."
            )
            meth_en = (
                "Official statistics of Abkhazia: registered hotels, sanatoria and holiday homes; the private sector "
                "is not included. The Abkhaz tourism ministry estimates about 1.88 million tourists and day "
                "visitors from Russia in 2025 (methodology not published)."
            )
        out.append(_s(
            f"tour-dest-{slug}", name, name_en, "тыс. чел.",
            "thousand people", freq, source, DEST_URLS[iso2], "tourism_destination_file",
            {"dest_iso2": iso2, "dest_kind": kind},
            f"{who} по статистике страны назначения ({country}), тысяч человек {per[freq]}. Данные {since}.",
            f"Russian citizens arriving in {country_en} according to {country_en}'s statistics, thousand "
            f"{per_en[freq]}.", meth, meth_en,
            f"россияне {country}, туристы из России {country}, {country}, выездной туризм",
            f"{source} {since}", listed=slug == "egypt", family=family,
        ))
    return out


# ── Вторая волна (c4, 20.11.2026): цены, налоги с туристов, сборник «Туризм в России» ─

PRICE_PAGE = "https://rosstat.gov.ru/statistics/price"
TREASURY_URL = "https://roskazna.gov.ru/ispolnenie-byudzhetov/konsolidirovannye-byudzhety-subektov-rossijskoj-federacii/"
FNS_1NM_URL = "https://www.nalog.gov.ru/rn77/related_activities/statistics_and_analytics/forms/"
BOOK_URL = "https://rosstat.gov.ru/statistics/turizm"

_M_CPI = (
    "Росстат каждый месяц регистрирует цены на одни и те же услуги-представители в городах России и считает, на "
    "сколько процентов они изменились к тому же месяцу прошлого года. Цена поездки за границу — стоимость типового "
    "тура (перелёт и проживание) у туроператоров; цена гостиницы — сутки проживания одного человека. Росстат "
    "публикует такие индексы по позициям только за текущий и прошлый год, поэтому ряд начинается с 2025 года и "
    "дальше копится на сайте."
)
_M_CPI_EN = (
    "Each month Rosstat records prices of the same representative services across Russian cities and computes the "
    "percentage change from the same month a year earlier. A trip abroad is a typical package (flight and stay) "
    "sold by tour operators; a hotel price is one night for one person. Rosstat publishes item-level indices only "
    "for the current and previous year, so the series starts in 2025 and accumulates on this site."
)

CPI_ITEMS: tuple[tuple[str, str, str, str, str, bool], ...] = (
    # код серии, код Росстата, название (после «Цены: »), en, подпись в группе, на витрине
    ("tourism", "9530", "услуги в сфере туризма", "tourism services", "Все услуги туризма", True),
    ("domestic", "9560", "внутренний туризм", "domestic tourism", "Внутренний туризм", False),
    ("abroad", "9540", "зарубежный туризм", "outbound tourism", "Зарубежный туризм", False),
    ("turkey", "9541", "поездка на отдых в Турцию", "holiday trip to Turkey", "Турция", False),
    ("egypt", "9552", "поездка на отдых в Египет", "holiday trip to Egypt", "Египет", False),
    ("belarus", "9553", "поездка в Беларусь", "trip to Belarus", "Беларусь", False),
    ("caucasus", "9555", "поездки в страны Закавказья", "trips to the South Caucasus", "Закавказье", False),
    ("central-asia", "9556", "поездки в страны Средней Азии", "trips to Central Asia", "Средняя Азия", False),
    ("se-asia", "9559", "поездки в страны Юго-Восточной Азии", "trips to Southeast Asia", "Юго-Восточная Азия",
     False),
    ("black-sea", "9536", "отдых на Черноморском побережье России", "holiday on Russia's Black Sea coast",
     "Черноморское побережье", False),
    ("russia-tours", "9535", "экскурсионные туры по России", "sightseeing tours in Russia", "Туры по России",
     False),
    ("river-cruise", "9532", "речной круиз по России", "river cruise in Russia", "Речной круиз", False),
    ("excursions", "9550", "экскурсионные услуги", "excursion services", "Экскурсии", False),
    ("bus-excursion", "9534", "автобусная экскурсия", "bus excursion", "Автобусная экскурсия", False),
    ("hotels", "9490", "гостиницы и прочие места проживания", "hotels and other accommodation",
     "Все средства размещения", True),
    ("hotel-1", "9462", "гостиница 1* или мотель", "1-star hotel or motel", "Гостиница 1*", False),
    ("hotel-2", "9463", "гостиница 2*", "2-star hotel", "Гостиница 2*", False),
    ("hotel-3", "9464", "гостиница 3*", "3-star hotel", "Гостиница 3*", False),
    ("hotel-4-5", "9465", "гостиница 4*–5*", "4-5-star hotel", "Гостиница 4*–5*", False),
    ("hostel", "9466", "хостел", "hostel", "Хостел", False),
    ("sanatoria", "9600", "санаторно-оздоровительные услуги", "health resort services", "Санаторно-оздоровительные",
     False),
    ("sanatorium-day", "9606", "день в санатории", "a day in a sanatorium", "Санаторий", False),
    ("rest-house-day", "9607", "день в доме отдыха или пансионате", "a day in a rest house", "Дом отдыха", False),
)
_CPI_HOTEL_FROM = 14  # позиции с этого индекса — вторая группа (размещение и санатории)


def _cpi_series() -> list[TourSeries]:
    out = []
    # Позиции, введённые в корзину в 2025 году: изменение к прошлому году Росстат даёт с января 2026.
    new_2025 = {"hotel-1", "hotel-2", "hotel-3", "hotel-4-5", "hostel", "sanatoria", "sanatorium-day",
                "rest-house-day"}
    for slug, item, label, label_en, _short, listed in CPI_ITEMS:
        name = f"Цены на туризм: {label}"
        since = 2026 if slug in new_2025 else 2025
        out.append(_s(
            f"tour-cpi-{slug}", name, f"Tourism prices: {label_en}", "% г/г", "% y/y", "monthly", SRC_ROSSTAT,
            PRICE_PAGE, "rosstat_tourism_cpi", {"cpi_item": item},
            f"На сколько процентов изменились цены ({label}) к тому же месяцу прошлого года. Данные с {since} года.",
            f"Year-on-year change in prices for {label_en}, per cent. Since {since}.", _M_CPI, _M_CPI_EN,
            f"цены на {label}, подорожание, инфляция в туризме, стоимость отдыха",
            f"Росстата по месяцам с {since} года", listed=listed, min_value=None,
            seo_title=f"Цены на {label}: на сколько подорожало за год",
        ))
    return out


_M_STATIC = (
    "Ряд собран из официальной публикации, у которой нет постоянно обновляемой машиночитаемой версии, и обновляется "
    "на сайте вручную."
)
_M_STATIC_EN = "Compiled from an official publication without a regularly updated machine-readable version."
_M_BOOK = (
    "Данные статистического сборника Росстата «Туризм в России» 2024 года (2014–2023). Сборник снят с сайта Росстата, "
    "таблицы взяты из его архивной копии; более нового выпуска нет. " + _M_STATIC
)
_M_BOOK_EN = (
    "Data from Rosstat's statistical yearbook Tourism in Russia, 2024 edition (2014-2023). The yearbook was removed "
    "from Rosstat's website and the tables come from its archived copy; no newer edition exists."
)


# Страны таблиц ежегодников 2002–2013 (ряды tour-hist-<направление>-<страна>): slug, страна, en, род. падеж, шаблон.
# Страны, которые попадали в таблицу меньше трёх раз, не взяты (Болгария и Филиппины на въезде, Сербия — 2 года).
def _hc(rows):
    return tuple((slug, ru, en, gen, "T10" if n >= 5 else None) for slug, ru, en, gen, n in rows)


HIST_INBOUND = _hc((
    ("germany", "Германия", "Germany", "Германии", 11), ("finland", "Финляндия", "Finland", "Финляндии", 11),
    ("china", "Китай", "China", "Китая", 11), ("usa", "США", "United States", "США", 11),
    ("poland", "Польша", "Poland", "Польши", 11), ("estonia", "Эстония", "Estonia", "Эстонии", 11),
    ("latvia", "Латвия", "Latvia", "Латвии", 11), ("lithuania", "Литва", "Lithuania", "Литвы", 11),
    ("uk", "Великобритания", "United Kingdom", "Великобритании", 11), ("italy", "Италия", "Italy", "Италии", 11),
    ("france", "Франция", "France", "Франции", 11), ("turkey", "Турция", "Turkey", "Турции", 11),
    ("japan", "Япония", "Japan", "Японии", 11), ("korea", "Республика Корея", "South Korea", "Кореи", 11),
    ("mongolia", "Монголия", "Mongolia", "Монголии", 11), ("israel", "Израиль", "Israel", "Израиля", 11),
    ("netherlands", "Нидерланды", "Netherlands", "Нидерландов", 11), ("sweden", "Швеция", "Sweden", "Швеции", 11),
    ("austria", "Австрия", "Austria", "Австрии", 11), ("spain", "Испания", "Spain", "Испании", 10),
    ("norway", "Норвегия", "Norway", "Норвегии", 8), ("canada", "Канада", "Canada", "Канады", 5),
    ("india", "Индия", "India", "Индии", 3), ("switzerland", "Швейцария", "Switzerland", "Швейцарии", 3),
))
HIST_OUTBOUND = _hc((
    ("turkey", "Турция", "Turkey", "Турции", 12), ("egypt", "Египет", "Egypt", "Египта", 12),
    ("china", "Китай", "China", "Китая", 12), ("finland", "Финляндия", "Finland", "Финляндии", 12),
    ("germany", "Германия", "Germany", "Германии", 12), ("spain", "Испания", "Spain", "Испании", 12),
    ("italy", "Италия", "Italy", "Италии", 12), ("greece", "Греция", "Greece", "Греции", 12),
    ("uae", "ОАЭ", "United Arab Emirates", "ОАЭ", 12), ("cyprus", "Кипр", "Cyprus", "Кипра", 12),
    ("bulgaria", "Болгария", "Bulgaria", "Болгарии", 12), ("france", "Франция", "France", "Франции", 12),
    ("poland", "Польша", "Poland", "Польши", 12), ("estonia", "Эстония", "Estonia", "Эстонии", 12),
    ("latvia", "Латвия", "Latvia", "Латвии", 12), ("lithuania", "Литва", "Lithuania", "Литвы", 12),
    ("uk", "Великобритания", "United Kingdom", "Великобритании", 12), ("usa", "США", "United States", "США", 12),
    ("czechia", "Чехия", "Czechia", "Чехии", 10), ("thailand", "Таиланд", "Thailand", "Таиланда", 8),
    ("switzerland", "Швейцария", "Switzerland", "Швейцарии", 8), ("japan", "Япония", "Japan", "Японии", 7),
    ("israel", "Израиль", "Israel", "Израиля", 6), ("austria", "Австрия", "Austria", "Австрии", 5),
    ("korea", "Республика Корея", "South Korea", "Кореи", 4),
))


def _static_series() -> list[TourSeries]:
    S = "tourism_static_file"
    book = "Росстата по годам 2014–2023"
    out = [
        _s("tour-tax", "Туристический налог в России", "Tourist tax in Russia", "млн руб.", "RUB mn", "quarterly",
           "ФНС России", FNS_1NM_URL, S, {},
           "Сколько туристического налога поступило в бюджеты регионов и муниципалитетов за квартал, миллионов "
           "рублей. Налог действует с 2025 года вместо курортного сбора и взимается с проживания в гостиницах.",
           "Tourist tax received by regional and municipal budgets per quarter, RUB million. The tax replaced the "
           "resort fee in 2025 and is charged on hotel stays.",
           "Отчёт ФНС России о начислении и поступлении налогов (форма 1-НМ). Гостиницы платят налог раз в квартал — "
           "до 28-го числа месяца после квартала, поэтому в первом квартале 2025 года поступлений ещё не было, а "
           "квартал на сайте — это деньги, поступившие в этом квартале. Итог 2025 года (5,64 млрд руб.) совпадает с "
           "отчётом Федерального казначейства об исполнении бюджетов. В Москве налог не введён. Сумма по регионам в "
           "отчёте ФНС может быть меньше строки «Россия» на несколько миллионов рублей. Курортный сбор 2018–2024 "
           "годов — другой платёж (отдельный ряд), складывать их нельзя. " + _M_STATIC,
           "Federal Tax Service report on tax accruals and receipts (form 1-NM). Hotels pay quarterly, by the 28th "
           "of the month after the quarter, so no receipts arrived in Q1 2025; a quarter on this site is the money "
           "received in it. The 2025 total matches the Federal Treasury budget execution report. Moscow has not "
           "introduced the tax.",
           "туристический налог, туристический сбор, налог с туристов, налог на проживание в гостинице",
           "ФНС России по кварталам с 2025 года", family="T9"),
        _s("tour-resort-fee", "Курортный сбор в России", "Resort fee in Russia", "млн руб.", "RUB mn", "annual",
           "Федеральное казначейство", TREASURY_URL, S, {},
           "Сколько курортного сбора поступило в бюджеты за год, миллионов рублей. Сбор брали в 2018–2024 годах в "
           "Краснодарском, Ставропольском и Алтайском краях, на «Сириусе» и в Санкт-Петербурге; с 2025 года его "
           "заменил туристический налог.",
           "Resort fee received by budgets during the year, RUB million. The fee was charged in 2018-2024 in "
           "Krasnodar, Stavropol and Altai territories, Sirius and St Petersburg; the tourist tax replaced it in 2025.",
           "Отчёт Федерального казначейства об исполнении консолидированных бюджетов субъектов (форма 0503317), "
           "доходы по коду платы за пользование курортной инфраструктурой. Остаточные поступления 2025 года после "
           "окончания эксперимента не показаны. " + _M_STATIC,
           "Federal Treasury report on execution of consolidated regional budgets (form 0503317), revenue code for "
           "the resort infrastructure fee. Residual receipts in 2025 after the experiment ended are not shown.",
           "курортный сбор, сбор с отдыхающих, Сочи, Крым, Кавминводы", "Казначейства по годам 2018–2024",
           family="T10"),
        _s("tour-price-sanatorium", "Цена дня в санатории", "Price of a day in a sanatorium", "руб.", "RUB",
           "annual", SRC_ROSSTAT, PRICE_PAGE, S, {},
           "Средняя цена одного дня в санатории в России на конец года, рублей. С 1991 года.",
           "Average price of one day in a sanatorium in Russia at year end, roubles. Since 1991.",
           "Средняя потребительская цена Росстата на конец года по России. Цены 1991–1997 годов пересчитаны в "
           "деноминированные рубли (разделены на 1000), поэтому ряд непрерывен. До 2000 года в наблюдение входили "
           "в основном профсоюзные и ведомственные санатории.",
           "Rosstat's average consumer price at year end. Prices for 1991-1997 are converted to redenominated "
           "roubles (divided by 1000) so the series is continuous.",
           "цена санатория, стоимость санатория, путёвка в санаторий, сколько стоит санаторий",
           "Росстата по годам с 1991 года", family="T10"),
        _s("tour-price-rest-house", "Цена дня в доме отдыха", "Price of a day in a rest house", "руб.", "RUB",
           "annual", SRC_ROSSTAT, PRICE_PAGE, S, {},
           "Средняя цена одного дня в доме отдыха или пансионате в России на конец года, рублей. С 1991 года.",
           "Average price of one day in a rest house or boarding house in Russia at year end, roubles. Since 1991.",
           "Средняя потребительская цена Росстата на конец года по России. Цены 1991–1997 годов пересчитаны в "
           "деноминированные рубли (разделены на 1000).",
           "Rosstat's average consumer price at year end. Prices for 1991-1997 are converted to redenominated "
           "roubles (divided by 1000).", "цена дома отдыха, пансионат, стоимость отдыха",
           "Росстата по годам с 1991 года", family="T10", listed=False),
    ]
    book_rows = [
        ("tour-packages", "Турпакеты, проданные населению", "Package tours sold", "тыс. турпакетов",
         "thousand package tours",
         "Сколько турпакетов продали турфирмы населению за год, тысяч — туры по России и за рубеж.",
         "Package tours sold by travel firms during the year, thousand.", "турпакеты, путёвки, продажи туров", True,
         "T10"),
        ("tour-packages-domestic", "Турпакеты по России, проданные россиянам", "Domestic package tours sold",
         "тыс. турпакетов", "thousand package tours", "Сколько туров по России продали турфирмы россиянам за год, тысяч.",
         "Package tours within Russia sold to Russian citizens, thousand.", "туры по России", False, "T10"),
        ("tour-packages-outbound", "Турпакеты за рубеж, проданные россиянам", "Outbound package tours sold",
         "тыс. турпакетов", "thousand package tours", "Сколько зарубежных туров продали турфирмы россиянам за год, тысяч.",
         "Package tours abroad sold to Russian citizens, thousand.", "зарубежные туры", False, "T10"),
        ("tour-packages-value", "Стоимость проданных турпакетов", "Value of package tours sold", "млрд руб.",
         "RUB bn", "Сколько население заплатило турфирмам за турпакеты за год, миллиардов рублей.",
         "Amount paid by the population for package tours during the year, RUB billion.", "выручка турфирм",
         False, "T10"),
        ("tour-package-price", "Средняя стоимость турпакета", "Average package tour price", "тыс. руб.",
         "RUB thousand", "Средняя цена одного турпакета, проданного населению, тысяч рублей.",
         "Average price of one package tour sold to the population, RUB thousand.",
         "стоимость путёвки, сколько стоит тур, цена тура", True, "T10"),
        ("tour-package-price-domestic", "Средняя стоимость тура по России", "Average domestic package tour price",
         "тыс. руб.", "RUB thousand", "Средняя цена одного тура по России, проданного россиянам, тысяч рублей.",
         "Average price of one domestic package tour, RUB thousand.", "цена тура по России", False, "T10"),
        ("tour-package-price-outbound", "Средняя стоимость зарубежного тура", "Average outbound package tour price",
         "тыс. руб.", "RUB thousand", "Средняя цена одного зарубежного тура, проданного россиянам, тысяч рублей.",
         "Average price of one outbound package tour, RUB thousand.", "цена тура за границу", False, "T10"),
        ("tour-firm-tourists-russia", "Туристы турфирм в поездках по России", "Travel firm clients on domestic tours",
         "тыс. чел.", "thousand people", "Сколько российских туристов турфирмы отправили в туры по России за год, тысяч.",
         "Russian tourists sent by travel firms on domestic tours, thousand.", "организованный туризм", False, "T10"),
        ("tour-firm-tourists-abroad", "Туристы турфирм в поездках за рубеж", "Travel firm clients on tours abroad",
         "тыс. чел.", "thousand people", "Сколько российских туристов турфирмы отправили в зарубежные туры за год, тысяч.",
         "Russian tourists sent by travel firms on tours abroad, thousand.", "организованный туризм", False, "T10"),
        ("tour-household-spending", "Расходы семей на туризм и отдых", "Household spending on tourism and leisure",
         "руб.", "RUB", "Сколько в среднем тратит на туризм и отдых один член семьи за год, рублей, по обследованию "
         "бюджетов домашних хозяйств.", "Average annual spending on tourism and leisure per household member, "
         "roubles.", "расходы на отпуск, траты на отдых", True, "T10"),
        ("tour-household-spending-share", "Доля туризма и отдыха в расходах семей",
         "Share of tourism and leisure in household spending", "%", "%",
         "Какую долю всех потребительских расходов семьи тратят на туризм и отдых, процентов.",
         "Share of tourism and leisure in household consumer spending, per cent.", "доля расходов на отдых", False,
         "T10a"),
        ("tour-hotel-workers", "Работники гостиниц и других средств размещения",
         "Employees of hotels and other accommodation", "чел.", "people",
         "Среднесписочная численность работников гостиниц, санаториев и других коллективных средств размещения, "
         "человек.", "Average number of employees of collective accommodation establishments.",
         "работники гостиниц, занятость в туризме", False, "T10"),
        ("tour-new-hotel-beds", "Ввод мест в новых гостиницах", "New hotel bed places commissioned", "мест",
         "bed places", "Сколько мест в гостиницах ввели в действие за год.",
         "Hotel bed places commissioned during the year.", "строительство гостиниц, новые отели", False, "T10"),
    ]
    _M_HIST = (
        "Ежегодники Росстата 2003–2014 по сведениям пограничной службы ФСБ России: пересечения границы "
        "иностранцами и россиянами — только страны дальнего зарубежья, без СНГ, со всеми целями (служебные, "
        "туризм, частные, транзит, обслуживающий персонал) или только с целью «туризм». Это другой учёт, чем у "
        "рядов «туристских поездок» Росстата с 2014 года, поэтому ряды ведутся отдельно и не продолжают друг "
        "друга. 1994 год в ежегодниках не опубликован."
    )
    _M_HIST_EN = (
        "Rosstat yearbooks 2003-2014 based on FSB border service records: border crossings to and from countries "
        "outside the CIS only. A different count from Rosstat's tourist trips since 2014, so the series are kept "
        "separate."
    )
    for code, name, name_en, desc, desc_en, listed in (
        ("tour-hist-inbound", "Въезд иностранцев в Россию до 2014 года", "Foreign arrivals in Russia before 2014",
         "Сколько раз иностранцы из стран дальнего зарубежья въезжали в Россию за год, с любыми целями, тысяч "
         "поездок. 1993–2013 годы.", "Entries of citizens of non-CIS countries, all purposes, thousand.", True),
        ("tour-hist-inbound-tourism", "Въезд иностранцев в Россию с целью туризма до 2014 года",
         "Foreign tourist arrivals in Russia before 2014",
         "Сколько раз иностранцы из стран дальнего зарубежья въезжали в Россию с целью «туризм», тысяч поездок. "
         "1993–2013 годы.", "Entries for tourism by citizens of non-CIS countries, thousand.", False),
        ("tour-hist-outbound", "Выезд россиян за рубеж до 2014 года", "Russian departures abroad before 2014",
         "Сколько раз россияне выезжали в страны дальнего зарубежья за год, с любыми целями, тысяч поездок. "
         "1993–2013 годы.", "Departures of Russians to non-CIS countries, all purposes, thousand.", True),
        ("tour-hist-outbound-tourism", "Выезд россиян за рубеж с целью туризма до 2014 года",
         "Russian tourist departures abroad before 2014",
         "Сколько раз россияне выезжали в страны дальнего зарубежья с целью «туризм», тысяч поездок. "
         "1993–2013 годы.", "Departures of Russians for tourism to non-CIS countries, thousand.", False),
    ):
        out.append(_s(code, name, name_en, "тыс. поездок", "thousand trips", "annual", SRC_FSB, BOOK_URL, S, {},
                      desc, desc_en, _M_HIST, _M_HIST_EN, "история туризма, выезд за границу 1990-е, 2000-е",
                      "Росстата по годам 1993–2013", family="T10", listed=listed))
    _M_AIRPORT_ANNUAL = (
        "Годовой пассажиропоток (улетевшие и прилетевшие) собран из двух видов источников. 2020–2021 годы — сумма "
        "месяцев из отчётов Росавиации; Росавиация публиковала данные по аэропортам до февраля 2022 года и сейчас "
        "их не раскрывает. Остальные годы — сообщения самого аэропорта и отраслевые рейтинги (вторичный источник, "
        "не официальная статистика). 2018–2019 и часть 2000-х годов в этих источниках не найдены."
    )
    _M_AIRPORT_ANNUAL_EN = (
        "Annual passenger traffic: 2020-2021 are sums of monthly Federal Air Transport Agency reports; other years "
        "come from airport releases and industry rankings (secondary sources)."
    )
    for direction, countries in (("inbound", HIST_INBOUND), ("outbound", HIST_OUTBOUND)):
        for slug, country, country_en, gen, family in countries:
            if direction == "inbound":
                name = f"Въезд в Россию до 2014 года: {country}"
                name_en = f"Arrivals in Russia before 2014: {country_en}"
                desc = (f"Сколько раз граждане страны {country} въезжали в Россию за год, с любыми целями, тысяч "
                        "поездок. 2002–2013 годы, в которые страна была в таблице ежегодника.")
                desc_en = f"Entries to Russia by citizens of {country_en}, all purposes, thousand. 2002-2013."
                kws = f"иностранцы {gen} в России, туристы {gen}, история туризма"
            else:
                name = f"Выезд россиян до 2014 года: {country}"
                name_en = f"Russian departures before 2014: {country_en}"
                desc = (f"Сколько раз россияне выезжали в страну {country} за год, с любыми целями, тысяч поездок. "
                        "2002–2013 годы, в которые страна была в таблице ежегодника.")
                desc_en = f"Departures of Russians to {country_en}, all purposes, thousand. 2002-2013."
                kws = f"россияне в {country}, поездки {country}, история выездного туризма"
            out.append(_s(f"tour-hist-{direction}-{slug}", name, name_en, "тыс. поездок", "thousand trips", "annual",
                          SRC_FSB, BOOK_URL, S, {}, desc, desc_en,
                          _M_HIST + " По странам ежегодники дают 22–23 ведущие страны с 2002 года; въезда по странам "
                          "за 2012 год в сборнике нет.", _M_HIST_EN, kws, "Росстата по годам 2002–2013",
                          family=family, listed=False))
    for slug, short, short_en, listed in (("sochi", "Сочи", "Sochi", True), ("kazan", "Казань", "Kazan", False),
                                          ("mineralnye-vody", "Минеральные Воды", "Mineralnye Vody", False),
                                          ("kaliningrad", "Калининград", "Kaliningrad", False)):
        out.append(_s(
            f"tour-airport-annual-{slug}", f"Пассажиропоток аэропорта {short} по годам",
            f"{short_en} airport annual passenger traffic", "тыс. чел.", "thousand people", "annual",
            "Росавиация; аэропорт и отраслевые рейтинги (вторичные)", "https://favt.gov.ru/", S, {},
            f"Сколько пассажиров улетело и прилетело через аэропорт {short} за год, тысяч человек.",
            f"Departing and arriving passengers at {short_en} airport per year, thousand people.",
            _M_AIRPORT_ANNUAL, _M_AIRPORT_ANNUAL_EN, f"аэропорт {short}, пассажиропоток {short}, авиаперевозки",
            "по годам", family="T10", listed=listed,
        ))
    for code, name, name_en, unit, unit_en, desc, desc_en, kw, listed, fam in book_rows:
        out.append(_s(code, name, name_en, unit, unit_en, "annual", SRC_ROSSTAT, BOOK_URL, S, {},
                      desc + " Данные 2014–2023 годов." if code != "tour-hotel-workers" else desc + " 2019–2023.",
                      desc_en, _M_BOOK, _M_BOOK_EN, kw, book, family=fam, listed=listed,
                      yoy_unit="п.п." if fam == "T10a" else None))
    return out


SERIES: dict[str, TourSeries] = {s.code: s for s in (*_cbr_series(), *_fsb_series(), *_gva_series(),
                                                     *_emiss_series(), *_dest_series(), *_cpi_series(),
                                                     *_static_series())}


# ── Адрес источника на карточке: конкретная публикация (круг наблюдателей, правки 3 и 4, 21.11.2026) ──
# Раздел rosstat.gov.ru/statistics/turizm не ведёт к ряду, а сертификат сайта Росстата (Минцифры) Safari не принимает.
# Где ряд есть в ЕМИСС (сертификат Let's Encrypt), ссылка ведёт на витрину; таблицы сборника «Туризм в России» — на
# архивную копию файла. Проверено запросом 21.11.2026: ЦБ, ЕМИСС, ФНС — 200.
_ARCHIVE_BOOK = "https://web.archive.org/web/20250201063454/https://rosstat.gov.ru/storage/mediabank/{}-tur.xlsx"


def _source_url_override(code: str, s: "TourSeries") -> str | None:
    if s.parser_type == "rosstat_tourism_trips":
        return FEDSTAT.format(59466 if "-inbound-" in f"{code}-" else 59467)
    if code in ("tour-gva", "tour-gva-volume"):
        return FEDSTAT.format(59212)
    if code.startswith("tour-gva-share"):
        return FEDSTAT.format(59213)
    if s.parser_type == "rosstat_tourism_cpi":
        return FEDSTAT.format(31074)
    if code in ("tour-price-sanatorium", "tour-price-rest-house"):
        return FEDSTAT.format(31448)
    if code.startswith(("tour-packages", "tour-package-price", "tour-firm-tourists")):
        return _ARCHIVE_BOOK.format("R3")
    if code in ("tour-household-spending", "tour-household-spending-share", "tour-new-hotel-beds"):
        return _ARCHIVE_BOOK.format("R4")
    if code == "tour-hotel-workers":
        return _ARCHIVE_BOOK.format("R2")
    if code.startswith("tour-hist-"):
        # «Российский статистический ежегодник» 2003–2014: страница выпусков в архивной копии (сайт Росстата — сертификат
        # Минцифры).
        return "https://web.archive.org/web/2025/https://rosstat.gov.ru/folder/210/document/12994"
    return None


SERIES = {code: (replace(s, source_url=url) if (url := _source_url_override(code, s)) else s)
          for code, s in SERIES.items()}

# ── Группы срезов (frontend indicatorVariants.js повторяет их; тест сверяет) ──

VARIANT_GROUPS: tuple[tuple[str, str, tuple[tuple[str, str, str], ...]], ...] = (
    ("tourTravelExports", "Траты иностранцев в России", (
        ("tour-travel-exports", "Все поездки", "All trips"),
        ("tour-travel-business-exports", "Деловые", "Business"),
        ("tour-travel-personal-exports", "Личные", "Personal"),
    )),
    ("tourTravelImports", "Траты россиян за границей", (
        ("tour-travel-imports", "Все поездки", "All trips"),
        ("tour-travel-business-imports", "Деловые", "Business"),
        ("tour-travel-personal-imports", "Личные", "Personal"),
    )),
    ("tourInbound", "Въезд иностранцев по странам", (
        ("tour-inbound-trips", "Все страны", "All countries"),
        *((f"tour-inbound-{c.slug}", c.name, c.name_en) for c in INBOUND_COUNTRIES),
    )),
    ("tourOutbound", "Выезд россиян по странам", (
        ("tour-outbound-trips", "Все страны", "All countries"),
        *((f"tour-outbound-{c.slug}", c.name, c.name_en) for c in OUTBOUND_COUNTRIES),
    )),
    ("tourDestinations", "Россияне по данным стран назначения", tuple(
        (f"tour-dest-{d[0]}", (d[10] if len(d) > 9 else _DEST_DEFAULT_TAIL[d[0]][1]),
         d[5] + (", monthly" if d[0].endswith("-monthly") else "")) for d in DESTINATIONS
    )),
    ("tourEconomy", "Туризм в экономике", (
        ("tour-gva", "Добавленная стоимость", "Value added"),
        ("tour-gva-share", "Доля в ВВП", "Share of GDP"),
        ("tour-gva-volume", "Реальный рост", "Real growth"),
    )),
    ("tourAir", "Авиаперевозки пассажиров", (
        ("tour-air-passengers", "Все рейсы", "All flights"),
        ("tour-air-passengers-domestic", "Внутренние", "Domestic"),
        ("tour-air-passengers-international", "Международные", "International"),
        ("tour-air-passengers-charter", "Чартеры", "Charters"),
    )),
    ("tourAirports", "Пассажиропоток аэропортов", tuple(
        (f"tour-airport-{slug}", short, short_en.split(" ", 1)[-1] if slug in ("sheremetyevo", "vnukovo",
                                                                                "domodedovo") else short_en)
        for slug, _label, short, short_en in AIRPORTS
    ) + (
        ("tour-airport-annual-sochi", "Сочи", "Sochi"),
        ("tour-airport-annual-kazan", "Казань", "Kazan"),
        ("tour-airport-annual-mineralnye-vody", "Минеральные Воды", "Mineralnye Vody"),
        ("tour-airport-annual-kaliningrad", "Калининград", "Kaliningrad"),
    )),
    ("tourHistOutbound", "Выезд россиян 1993–2013 по странам", (
        ("tour-hist-outbound", "Все страны", "All countries"),
        ("tour-hist-outbound-tourism", "С целью туризма", "For tourism"),
        *((f"tour-hist-outbound-{c[0]}", c[1], c[2]) for c in HIST_OUTBOUND),
    )),
    ("tourHistInbound", "Въезд иностранцев 1993–2013 по странам", (
        ("tour-hist-inbound", "Все страны", "All countries"),
        ("tour-hist-inbound-tourism", "С целью туризма", "For tourism"),
        *((f"tour-hist-inbound-{c[0]}", c[1], c[2]) for c in HIST_INBOUND),
    )),
    ("tourRail", "Железная дорога", (
        ("tour-rail-passengers", "Пассажиры", "Passengers"),
        ("tour-rail-passenger-km", "Пассажирооборот", "Passenger-km"),
    )),
    ("tourHotels", "Гостиницы и средства размещения", (
        ("tour-hotel-guests", "Размещённые", "Guests"),
        ("tour-hotel-nights", "Ночёвки", "Nights"),
        ("tour-hotel-count", "Число объектов", "Establishments"),
        ("tour-hotel-rooms", "Номера", "Rooms"),
        ("tour-hotel-beds", "Места", "Bed places"),
        ("tour-hotel-revenue", "Доходы", "Revenue"),
        ("tour-hotel-workers", "Работники", "Employees"),
        ("tour-new-hotel-beds", "Новые места", "New bed places"),
    )),
    ("tourCpiTrips", "Цены на поездки и экскурсии", tuple(
        (f"tour-cpi-{c[0]}", c[4], c[3].capitalize()) for c in CPI_ITEMS[:_CPI_HOTEL_FROM]
    )),
    ("tourCpiStay", "Цены на гостиницы и санатории", tuple(
        (f"tour-cpi-{c[0]}", c[4], c[3].capitalize()) for c in CPI_ITEMS[_CPI_HOTEL_FROM:]
    )),
    ("tourStayPrice", "Цена дня отдыха", (
        ("tour-price-sanatorium", "Санаторий", "Sanatorium"),
        ("tour-price-rest-house", "Дом отдыха", "Rest house"),
    )),
    ("tourTaxes", "Налоги с туристов", (
        ("tour-tax", "Туристический налог", "Tourist tax"),
        ("tour-resort-fee", "Курортный сбор", "Resort fee"),
    )),
    ("tourFirms", "Турфирмы и турпакеты", (
        ("tour-packages", "Турпакеты", "Package tours"),
        ("tour-packages-domestic", "Туры по России", "Domestic tours"),
        ("tour-packages-outbound", "Туры за рубеж", "Tours abroad"),
        ("tour-packages-value", "Стоимость турпакетов", "Value of tours"),
        ("tour-package-price", "Средняя цена тура", "Average tour price"),
        ("tour-package-price-domestic", "Цена тура по России", "Domestic tour price"),
        ("tour-package-price-outbound", "Цена тура за рубеж", "Outbound tour price"),
        ("tour-firm-tourists-russia", "Туристы по России", "Tourists in Russia"),
        ("tour-firm-tourists-abroad", "Туристы за рубеж", "Tourists abroad"),
        ("tour-agencies", "Число турфирм", "Travel firms"),
    )),
    ("tourHousehold", "Расходы семей на отдых", (
        ("tour-household-spending", "На человека", "Per person"),
        ("tour-household-spending-share", "Доля в расходах", "Share of spending"),
    )),
    ("tourSanatoria", "Санатории", (
        ("tour-sanatorium-guests", "Размещённые", "Guests"),
        ("tour-sanatorium-nights", "Ночёвки", "Nights"),
        ("tour-sanatorium-revenue", "Доходы", "Revenue"),
    )),
)


def is_seasonal(s: TourSeries) -> bool:
    """Сезонный ряд: месяц или квартал туризма (поездки, траты, перевозки, ночёвки, загрузка кресел, налог). Сравнение
    с прошлым периодом здесь — сезон, а не рост. Не сезонные: годовые ряды и ряды, уже выраженные к году (ИПЦ позиций,
    реальный рост туриндустрии)."""
    return (s.frequency in ("monthly", "quarterly") and s.parser_type != "rosstat_tourism_cpi"
            and s.code != "tour-gva-volume")


def hidden_codes() -> set[str]:
    return {code for code, s in SERIES.items() if not s.listed}


def forecast_codes(kind: str) -> set[str]:
    return {code for code, s in SERIES.items() if s.forecast == kind}


_FORECAST_CFG = {
    "monthly_auto": None,     # seed_data.MONTHLY_AUTO_FORECAST_CODES ставит 12 шагов
    "annual_auto": None,      # seed_data.ANNUAL_AUTO_FORECAST_CODES ставит 1 шаг
    "generic_quarterly": {"forecast_steps": 4, "forecast_strategy": "generic_quarterly",
                          "forecast_transform": "absolute"},
    "signed_quarterly": {"forecast_steps": 4, "forecast_strategy": "signed_quarterly",
                         "forecast_transform": "absolute"},
}


def seed_indicators():
    for s in SERIES.values():
        cfg = {**s.cfg, **s.extra_cfg}
        fc = _FORECAST_CFG.get(s.forecast or "") if s.forecast else None
        cfg.update(fc or {"forecast_steps": 0})
        if s.min_value is not None:
            cfg["validation"] = {"min": s.min_value}
        if is_seasonal(s):
            cfg["seasonal"] = True
        yield {
            "code": s.code,
            "name": s.name,
            "name_en": s.name_en,
            "unit": s.unit,
            "frequency": s.frequency,
            "source": s.source,
            "source_url": s.source_url,
            "description": s.description,
            "methodology": s.methodology,
            "parser_type": s.parser_type,
            "model_config_json": cfg,
            "is_active": True,
            "category": CATEGORY,
        }


def family_defs():
    """Строки FamilyDef для view_model_families (импорт там, чтобы не было цикла)."""
    from app.data.view_model_families import FamilyDef

    for s in SERIES.values():
        if s.family:
            yield FamilyDef(s.code, s.name, s.family, s.unit, CATEGORY, s.frequency,
                            yoy_unit=s.yoy_unit, forecastable=s.forecast is not None)


def seo_keywords() -> dict[str, str]:
    return {code: f"{s.name}, {s.keywords}" for code, s in SERIES.items()}


def seo_meta() -> dict[str, dict[str, str]]:
    return {code: {"seo_title": s.seo_title, "seo_description": s.seo_description} for code, s in SERIES.items()}


def copy_en() -> dict[str, dict[str, str]]:
    return {code: {"name": s.name_en, "description": s.description_en, "methodology": s.methodology_en,
                   "unit": s.unit_en} for code, s in SERIES.items()}


# ── «О показателе» (INDICATOR_SEO_BLOCKS): шесть подблоков по одному шаблону ──

_WHY = {
    "cbr": (
        "Траты в поездках — самая прямая денежная мера туризма: сколько валюты приносят иностранные гости и "
        "сколько уходит за рубеж вместе с российскими туристами. Ряд влияет на счёт текущих операций и курс "
        "рубля, по нему видно, как санкции, курс и закрытые направления меняли поездки."
    ),
    "fsb": (
        "Число поездок через границу — главный счётчик международного туризма. Он показывает, какие страны "
        "открываются и закрываются для россиян, откуда едут гости в Россию и как туризм пережил пандемию и "
        "ограничения 2022 года."
    ),
    "gva": (
        "Добавленная стоимость и доля в ВВП показывают вес туризма в экономике в целом, а не только в "
        "гостиницах: в неё входят транспорт, общепит, турфирмы и курорты. Это целевой показатель национального "
        "проекта «Туризм и индустрия гостеприимства»."
    ),
    "transport": (
        "Пассажирские перевозки — быстрый признак туристического спроса: путешествия начинаются с билета. Ряд "
        "показывает сезонность отпусков, влияние закрытого неба и курса рубля на поездки."
    ),
    "hotels": (
        "Размещение в гостиницах и санаториях — итоговая мера внутреннего туризма: сколько людей реально "
        "доехало и переночевало. По ряду видно рост внутренних поездок после 2020 года и расширение "
        "гостиничного фонда."
    ),
}
_WHY["dest"] = (
    "Статистика страны назначения — второй взгляд на выездной туризм: она показывает, сколько россиян страна "
    "действительно приняла, и помогает сверить российские данные о выезде с данными принимающей стороны."
)
_WHY["prices"] = (
    "Цены на туры, гостиницы и санатории показывают, во что обходится отдых, и объясняют сдвиги спроса: дорожают "
    "закрытые направления, дешевеют те, где растёт предложение. Туристские услуги — заметная часть инфляции услуг."
)
_WHY["static"] = (
    "Ряд дополняет основные показатели туризма тем, что публикуется редко: налоги с туристов, продажи турфирм, "
    "расходы семей на отдых, работники и новые места в гостиницах."
)
_FREQ = {
    "cbr": ("Банк России публикует квартальный платёжный баланс примерно через полтора месяца после квартала, "
            "месячную торговлю услугами — около 15-го числа следующего месяца. Последние месяцы — оценка."),
    "fsb": ("Росстат обновляет файл о въездных и выездных поездках раз в квартал, примерно через два-три месяца "
            "после его окончания; месячный итог по въезду — ежемесячно."),
    "gva": "Росстат публикует квартальные данные примерно через два с половиной месяца после квартала, годовые "
           "уточняет в феврале следующего года.",
    "transport": "Росавиация и Росстат публикуют месячные данные примерно через полтора-два месяца после месяца.",
    "hotels": "Годовые данные выходят весной–летом следующего года, оперативные помесячные — через два-три месяца.",
    "prices": "Индексы по позициям Росстат публикует ежемесячно; средние цены дня отдыха — раз в год.",
    "static": "Источник обновляется раз в год или публикация прекращена; на сайте ряд обновляется вручную.",
    "dest": "Страны публикуют данные в своём графике; на сайте ряд обновляется вручную при выходе новых данных.",
}


def _group(s: TourSeries) -> str:
    if s.source == SRC_CBR:
        return "cbr"
    if s.parser_type == "rosstat_tourism_trips":
        return "fsb"
    if s.parser_type == "tourism_destination_file":
        return "dest"
    if s.parser_type == "rosstat_tourism_cpi" or s.code.startswith("tour-price-"):
        return "prices"
    if s.parser_type == "tourism_static_file":
        return "static"
    if s.parser_type == "rosstat_tourism_gva":
        return "gva"
    if s.code.startswith(("tour-air", "tour-rail")):
        return "transport"
    return "hotels"


def _mode_text(s: TourSeries) -> str:
    if s.frequency == "monthly":
        base = "По умолчанию — значение за месяц."
        if s.family == "T6":
            base += " Переключатель над графиком показывает суммы за квартал и год, изменение к прошлому месяцу и к тому же периоду прошлого года."
        elif s.family == "T2y":
            base += " Доступны средние за квартал и год и изменение в процентных пунктах к прошлому году."
    elif s.frequency == "quarterly":
        base = "По умолчанию — значение за квартал."
        if s.family in ("T9", "T9s"):
            base += " Доступны сумма за год, изменение к прошлому кварталу и к тому же кварталу прошлого года."
    else:
        base = "Значение за год."
        if s.family in ("T10", "T10a"):
            base += " Доступно изменение к прошлому году."
    if s.cfg.get("alternate_frequencies") or s.cfg.get("primary_indicator_code"):
        base += " Переключатель частоты ведёт к тому же показателю по месяцам или кварталам."
    return base


def seo_blocks() -> dict[str, list[dict[str, str]]]:
    out: dict[str, list[dict[str, str]]] = {}
    for code, s in SERIES.items():
        g = _group(s)
        out[code] = [
            {"title": "Что показывает эта карточка", "body": s.description},
            {"title": "Какой режим на графике", "body": _mode_text(s)},
            {"title": "Чем показатель важен", "body": _WHY[g]},
            {"title": "Как читать график", "body": (
                "Рост линии — показатель увеличивается, снижение — уменьшается. Сравнивайте одинаковые месяцы "
                "или кварталы разных лет: у туризма сильная сезонность, лето почти всегда выше зимы."
                if s.unit not in ("%",) else
                "Линия показывает уровень в процентах; изменение удобнее читать в процентных пунктах к тому же "
                "периоду прошлого года."
            )},
            {"title": "Как часто обновляются данные", "body": _FREQ[g]},
            {"title": "Откуда берутся данные и чего ряд не показывает", "body": s.methodology},
        ]
    return out
