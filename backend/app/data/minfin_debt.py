"""ФНБ и государственный долг России — помесячные ряды Минфина (19.11.2026).

Люди спрашивают про Фонд национального благосостояния (гипотезы Пульса 173 и 200) и госдолг («внешний
государственный долг России график», «госдолг России на сегодня»), а на сайте были только внешний долг страны по
данным ЦБ (квартальный, все секторы) и оценка МВФ «госдолг к ВВП» (годовая). Минфин публикует три помесячных файла
(лицензия сайта CC BY 4.0, проверено 19.11.2026 с Mac):

- ФНБ: страница `perfomance/nationalwealthfund/statistics` → `Dannye_YYYYMMDD.xlsx`, лист «Таблица по ФНБ»,
  с января 2008, столбец — месяц, значение «на конец периода»;
- государственный внутренний долг: `perfomance/public_debt/internal/structure` →
  `Obem_gosdolga_s_garantiyami_god_polnostu_na_DD_MM_YYYY.xls` (старый Excel), лист на год с 2009, «по состоянию на»
  1-е число месяца, млрд руб.;
- государственный внешний долг: `perfomance/public_debt/external/structure` → `GVD_YYYYMMDD.xlsx`, с 2011,
  «по состоянию на» 1-е число, млн долларов США.

Даты везде — «на 1-е число месяца»: значение ФНБ «на конец октября» хранится как 1 ноября, как и в сообщениях
Минфина («объём ФНБ на 1 ноября»). Боевому серверу Минфин отвечает 503 (сети Timeweb), поэтому файлы доставляет
Mac владельца (`scripts/minfin-debt-sync-from-mac.sh`) поверх снимков в `app/data/minfin/`, как у бюджета.
"""

from __future__ import annotations

from dataclasses import dataclass

SITE = "https://minfin.gov.ru"


@dataclass(frozen=True)
class Source:
    key: str
    page: str             # страница Минфина, на которой ссылка на свежий файл
    link_re: str          # регулярное выражение ссылки на файл
    snapshot: str         # имя снимка в app/data/minfin/


SOURCES: dict[str, Source] = {
    "nwf": Source("nwf", f"{SITE}/ru/perfomance/nationalwealthfund/statistics",
                  r"/common/upload/library/\d{4}/\d{2}/main/Dannye_\d{8}\.xlsx", "nwf.xlsx"),
    "domestic": Source("domestic", f"{SITE}/ru/perfomance/public_debt/internal/structure/",
                       r"/common/upload/library/\d{4}/\d{2}/main/Obem_gosdolga_s_garantiyami[^\"']*?\.xls",
                       "gov_debt_domestic.xls"),
    "external": Source("external", f"{SITE}/ru/perfomance/public_debt/external/structure/",
                       r"/common/upload/library/\d{4}/\d{2}/main/GVD_\d{8}\.xlsx", "gov_debt_external.xlsx"),
}


@dataclass(frozen=True)
class DebtSeries:
    code: str
    source: str           # ключ SOURCES
    row: str              # что брать из файла (см. minfin_debt_parser.parse_*)
    name: str
    name_en: str
    unit: str
    unit_en: str
    description: str
    description_en: str
    max_value: float


_NWF_NOTE = (
    "Фонд национального благосостояния — резерв федерального бюджета. В него зачисляют нефтегазовые доходы сверх "
    "базовой цены нефти, а тратят на покрытие дефицита бюджета и вложения в крупные проекты. Значение — на 1-е число "
    "месяца (на конец предыдущего месяца), данные Минфина России, помесячно с февраля 2008 года."
)
_NWF_NOTE_EN = (
    "The National Wealth Fund is the federal budget's reserve. It receives oil and gas revenue above the base oil "
    "price and is spent to cover budget deficits and invest in large projects. Values are as of the first day of the "
    "month (end of the previous month), Russian Ministry of Finance data, monthly since February 2008."
)

SERIES: tuple[DebtSeries, ...] = (
    DebtSeries("nwf-volume", "nwf", "total", "Объём ФНБ", "National Wealth Fund", "млрд руб.", "RUB bn",
               "Сколько средств в Фонде национального благосостояния России, миллиардов рублей.",
               "Total assets of Russia's National Wealth Fund, billions of roubles.", 100_000),
    DebtSeries("nwf-liquid", "nwf", "liquid", "Ликвидные активы ФНБ", "National Wealth Fund liquid assets",
               "млрд руб.", "RUB bn",
               "Ликвидная часть ФНБ — средства на счетах в Банке России (юани, золото, рубли), которые можно "
               "быстро потратить. Это объём фонда за вычетом вложений в облигации, акции и депозиты, миллиардов "
               "рублей.",
               "The liquid part of the National Wealth Fund: money held on accounts at the Bank of Russia (yuan, "
               "gold, roubles) that can be spent quickly. Total assets minus investments in bonds, shares and "
               "deposits, billions of roubles.", 100_000),
    DebtSeries("nwf-volume-usd", "nwf", "usd", "Объём ФНБ в долларах", "National Wealth Fund in US dollars",
               "млрд $", "USD bn",
               "Объём Фонда национального благосостояния, пересчитанный Минфином в доллары США, миллиардов "
               "долларов.",
               "National Wealth Fund assets converted by the Ministry of Finance into US dollars, billions of "
               "dollars.", 2_000),
    DebtSeries("nwf-gdp", "nwf", "gdp", "ФНБ к ВВП", "National Wealth Fund to GDP", "% ВВП", "% of GDP",
               "Объём Фонда национального благосостояния в процентах от ВВП России.",
               "National Wealth Fund assets as a percentage of Russia's GDP.", 100),
    DebtSeries("gov-debt-domestic", "domestic", "total", "Государственный внутренний долг",
               "Government domestic debt", "млрд руб.", "RUB bn",
               "Внутренний долг Российской Федерации в рублях: облигации федерального займа (ОФЗ) и другие ценные "
               "бумаги, а также государственные гарантии в рублях, миллиардов рублей.",
               "Russia's domestic government debt in roubles: federal loan bonds (OFZ) and other securities plus "
               "rouble state guarantees, billions of roubles.", 1_000_000),
    DebtSeries("gov-debt-external", "external", "total", "Государственный внешний долг",
               "Government external debt", "млрд $", "USD bn",
               "Внешний долг Российской Федерации в иностранной валюте: еврооблигации, кредиты и государственные "
               "гарантии в валюте, миллиардов долларов США.",
               "Russia's external government debt in foreign currency: eurobonds, loans and foreign-currency state "
               "guarantees, billions of US dollars.", 1_000),
)

SERIES_BY_CODE: dict[str, DebtSeries] = {s.code: s for s in SERIES}

METHODOLOGY = {
    "nwf": _NWF_NOTE,
    "domestic": (
        "Объём государственного внутреннего долга Российской Федерации на 1-е число месяца по данным Минфина России, "
        "включая государственные гарантии в рублях. Основная часть — облигации федерального займа (ОФЗ) по "
        "номинальной стоимости. Помесячно с января 2009 года."
    ),
    "external": (
        "Объём государственного внешнего долга Российской Федерации на 1-е число месяца по данным Минфина России, "
        "в эквиваленте долларов США, включая государственные гарантии в иностранной валюте. Это долг государства, "
        "а не всей страны: внешний долг банков и компаний считает Банк России. Помесячно с января 2011 года."
    ),
}
METHODOLOGY_EN = {
    "nwf": _NWF_NOTE_EN,
    "domestic": (
        "Russia's domestic government debt on the first day of the month, Ministry of Finance data, including rouble "
        "state guarantees. Most of it is federal loan bonds (OFZ) at face value. Monthly since January 2009."
    ),
    "external": (
        "Russia's external government debt on the first day of the month, Ministry of Finance data, in US dollar "
        "equivalent, including foreign-currency state guarantees. This is the state's debt, not the whole country's: "
        "external debt of banks and companies is compiled by the Bank of Russia. Monthly since January 2011."
    ),
}

KEYWORDS = {
    "nwf-volume": "ФНБ, фонд национального благосостояния, объём ФНБ, нацфонд, резервы бюджета, Минфин",
    "nwf-liquid": "ликвидные активы ФНБ, ликвидная часть ФНБ, ФНБ, фонд национального благосостояния, Минфин",
    "nwf-volume-usd": "ФНБ в долларах, фонд национального благосостояния, объём ФНБ, Минфин",
    "nwf-gdp": "ФНБ к ВВП, ФНБ в процентах ВВП, фонд национального благосостояния, Минфин",
    "gov-debt-domestic": "госдолг России, государственный внутренний долг, внутренний долг, ОФЗ, Минфин",
    "gov-debt-external": "госдолг России, государственный внешний долг, внешний долг государства, еврооблигации, Минфин",
}


def seed_indicators():
    for s in SERIES:
        yield {
            "code": s.code,
            "name": s.name,
            "name_en": s.name_en,
            "unit": s.unit,
            "frequency": "monthly",
            "source": "Минфин",
            "source_url": SOURCES[s.source].page,
            "description": s.description,
            "methodology": METHODOLOGY[s.source],
            "parser_type": "minfin_debt_xlsx",
            "model_config_json": {
                "minfin_series": s.code,
                "forecast_steps": 0,
                "validation": {"min": 0, "max": s.max_value},
            },
            "is_active": True,
            "category": "Финансы",
        }


def copy_en() -> dict[str, dict[str, str]]:
    return {
        s.code: {"name": s.name_en, "description": s.description_en,
                 "methodology": METHODOLOGY_EN[s.source], "unit": s.unit_en}
        for s in SERIES
    }


def seo_keywords() -> dict[str, str]:
    return {s.code: KEYWORDS[s.code] for s in SERIES}


def seo_meta() -> dict[str, dict[str, str]]:
    return {
        s.code: {
            "seo_title": f"{s.name} — помесячно, {s.unit}",
            "seo_description": f"{s.description} Данные Минфина России на 1-е число месяца, график и таблица.",
        }
        for s in SERIES
    }
