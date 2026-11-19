"""Помесячные региональные наборы ЕМИСС: сельское хозяйство, жильё, промышленность, транспорт (19.11.2026).

До 19.11.2026 по регионам эти темы были только годовыми и заканчивались 2024 годом (сборник «Регионы России»).
Здесь — свежие помесячные ряды Росстата по субъектам и России в целом, слой ``region_monthly_data``
(как цены 31448), разделы регионального каталога 12, 13, 14 и 16:

- 57693 «Средние цены производителей сельскохозяйственной продукции» — зерно, масличные, картофель, молоко,
  скот, яйца, рублей за тонну (яйца — за тысячу штук), с 2017 года. Пустые поиски «цена подсолнечник»,
  «цена семена», «цена пшеницы» (отчёт каталога ЕМИСС 19.11.2026);
- 34118 «Введено в действие общей площади жилых домов» — всего, многоквартирные дома, дома населения,
  тысяч м² за месяц, с 2012/2015 года. Наборы 59262/59993 (те же темы в млн м²) не нужны: история короче,
  значения те же;
- 57806 «Индекс производства (оперативные данные)» — четыре раздела промышленности к тому же месяцу прошлого
  года. Строка «Всего по обследуемым видам» в наборе не опубликована ни за один год (живой запрос 19.11.2026);
- 31076 «Индексы тарифов на грузовые перевозки» — все виды транспорта, автомобильный, железнодорожный,
  к тому же месяцу прошлого года, с 2006 года (раньше этот вид индекса не публиковался, живой запрос 19.11.2026).
  Пустой поиск «стоимость грузоперевозок».

Ключ ряда — oid позиции в измерении набора; у части позиций 57693 Росстат завёл новый oid с 2024 года
под тем же названием (молоко, яйца, кукуруза): ряд берёт оба oid, ответ различает их только названием,
поэтому месяцы старого и нового oid складываются в один ряд.

Не взяты (зона E, 19.11.2026; причины — в отчёте impl-emiss-e.md): 57740 (индексы тех же цен —
средние цены нагляднее и закрывают спрос), 34165/34158/40545/33784 (ход сева и уборки «на 1-е число», с 2023
года, без сои и ячменя, о которых спрашивали), 62900 (турпоездки с 2025 года, своё измерение территорий),
57788 (платные услуги).
"""

from __future__ import annotations

from dataclasses import dataclass

# 33560 «Период»: только месяцы (у набора бывают и «январь–март», «I квартал», «на 1 июля»).
TERRITORY_DIM = "57831"
SOURCE_URL = "https://www.fedstat.ru/indicator/{dataset}"


@dataclass(frozen=True)
class RegionalSeries:
    code: str
    oids: tuple[str, ...]   # позиция в измерении набора (несколько — если Росстат сменил oid)
    label: str              # название позиции у Росстата (так приходит в ответе)
    name: str
    name_en: str
    short: str              # короткое имя для строк раздела региона
    keywords: str = ""


@dataclass(frozen=True)
class RegionalSet:
    dataset: int
    series_dim: str
    extra_lines: tuple[str, ...]  # измерения, которые идут строками, но ряд не различают (единица ОКЕИ)
    filters: tuple[str, ...]      # «dim_oid»: показатель, единица, вид показателя
    first_year: int
    section_num: int
    section_name: str
    section_en: str
    unit: str
    unit_en: str
    note: str
    note_en: str
    scale: float                  # множитель к значению источника
    min_value: float              # граница допустимого значения (вне — точка пропускается и считается)
    max_value: float
    series: tuple[RegionalSeries, ...]
    title: str                    # название набора у Росстата (для источника)

    @property
    def source_url(self) -> str:
        return SOURCE_URL.format(dataset=self.dataset)


def _s(code, oids, label, name, name_en, short, keywords=""):
    return RegionalSeries(code, tuple(oids.split(",")), label, name, name_en, short, keywords)


AGRO_PRICES = RegionalSet(
    dataset=57693, series_dim="57939", extra_lines=("57956",),
    filters=("30611_1341910", "57956_1694829", "57956_1694838"),
    first_year=2017, section_num=13, section_name="Сельское хозяйство", section_en="Agriculture",
    unit="рублей за тонну", unit_en="roubles per tonne",
    note="Средняя цена, по которой сельхозорганизации продают продукцию, без НДС. Частота — месячная.",
    note_en="average price at which agricultural companies sell their produce, excluding VAT; monthly",
    scale=1.0, min_value=100.0, max_value=3_000_000.0,
    title="Средние цены производителей сельскохозяйственной продукции, реализуемой сельскохозяйственными "
          "организациями",
    series=(
        _s("selhoz-cena-pshenica", "1785972", "Пшеница",
           "Цена производителей: пшеница", "Producer price: wheat", "Пшеница, т",
           "цена пшеницы, стоимость пшеницы, зерно, цена зерна"),
        _s("selhoz-cena-pshenica-3", "1795394", "Пшеница мягкая 3 класса",
           "Цена производителей: пшеница мягкая 3 класса", "Producer price: soft wheat, class 3",
           "Пшеница 3 класса, т", "пшеница 3 класса, продовольственная пшеница"),
        _s("selhoz-cena-pshenica-4", "1795395", "Пшеница мягкая 4 класса",
           "Цена производителей: пшеница мягкая 4 класса", "Producer price: soft wheat, class 4",
           "Пшеница 4 класса, т", "пшеница 4 класса"),
        _s("selhoz-cena-pshenica-5", "1795396", "Пшеница мягкая 5 класса",
           "Цена производителей: пшеница мягкая 5 класса", "Producer price: soft wheat, class 5",
           "Пшеница 5 класса, т", "пшеница 5 класса, фуражная пшеница, фураж"),
        _s("selhoz-cena-yachmen", "1785641", "Ячмень",
           "Цена производителей: ячмень", "Producer price: barley", "Ячмень, т", "цена ячменя, фуражный ячмень"),
        _s("selhoz-cena-kukuruza", "1751300,1758224", "Кукуруза",
           "Цена производителей: кукуруза на зерно", "Producer price: maize (grain)", "Кукуруза, т",
           "цена кукурузы, кукуруза на зерно"),
        _s("selhoz-cena-rozh", "1751301", "Рожь",
           "Цена производителей: рожь", "Producer price: rye", "Рожь, т", "цена ржи"),
        _s("selhoz-cena-oves", "1751302", "Овес",
           "Цена производителей: овёс", "Producer price: oats", "Овёс, т", "цена овса, овес"),
        _s("selhoz-cena-grechiha", "1751304", "Гречиха",
           "Цена производителей: гречиха", "Producer price: buckwheat", "Гречиха, т",
           "цена гречихи, гречка зерно"),
        _s("selhoz-cena-podsolnechnik", "1758151", "Семена подсолнечника",
           "Цена производителей: семена подсолнечника", "Producer price: sunflower seeds", "Подсолнечник, т",
           "цена подсолнечника, подсолнечник, семечки, масличные"),
        _s("selhoz-cena-soya", "1758149", "Бобы соевые",
           "Цена производителей: соя (бобы соевые)", "Producer price: soybeans", "Соя, т",
           "цена сои, соя, соевые бобы"),
        _s("selhoz-cena-raps", "1758150", "Семена рапса",
           "Цена производителей: семена рапса", "Producer price: rapeseed", "Рапс, т", "цена рапса, рапс"),
        _s("selhoz-cena-kartofel", "1758161", "Картофель",
           "Цена производителей: картофель", "Producer price: potatoes", "Картофель, т",
           "цена картофеля у производителей, картошка оптом"),
        _s("selhoz-cena-svekla", "1758163", "Корнеплоды свеклы сахарной",
           "Цена производителей: сахарная свёкла", "Producer price: sugar beet", "Сахарная свёкла, т",
           "цена сахарной свеклы, свекла"),
        _s("selhoz-cena-moloko", "1758171,1851174", "Молоко сырое крупного рогатого скота",
           "Цена производителей: сырое молоко", "Producer price: raw cow's milk", "Сырое молоко, т",
           "цена молока, закупочная цена молока, сырое молоко"),
        _s("selhoz-cena-krs", "1754681", "Крупный рогатый скот",
           "Цена производителей: крупный рогатый скот в живом весе", "Producer price: cattle, live weight",
           "Крупный рогатый скот, т", "цена говядины в живом весе, бычки, скот, крс"),
        _s("selhoz-cena-svinyi", "1754685", "Свиньи",
           "Цена производителей: свиньи в живом весе", "Producer price: pigs, live weight", "Свиньи, т",
           "цена свинины в живом весе, свиньи"),
        _s("selhoz-cena-ptica", "1758178", "Птица сельскохозяйственная живая",
           "Цена производителей: птица в живом весе", "Producer price: poultry, live weight", "Птица, т",
           "цена бройлера, птица, курица живым весом"),
        _s("selhoz-cena-yayca", "1758179,1847175", "Яйца куриные в скорлупе свежие",
           "Цена производителей: яйца куриные", "Producer price: hen eggs", "Яйца, тыс. шт.",
           "цена яиц у производителей, яйца оптом"),
    ),
)
# Яйца у Росстата — за тысячу штук; остальная продукция — за тонну.
UNIT_OVERRIDES: dict[str, tuple[str, str]] = {
    "selhoz-cena-yayca": ("рублей за 1000 штук", "roubles per 1,000 eggs"),
}

HOUSING = RegionalSet(
    dataset=34118, series_dim="58389", extra_lines=(),
    filters=("30611_950292",),
    first_year=2012, section_num=14, section_name="Строительство", section_en="Construction",
    unit="тысяч м² общей площади", unit_en="thousand m² of floor area",
    note="Введено за месяц, оперативные данные. Частота — месячная.",
    note_en="completed during the month, preliminary data; monthly",
    scale=1.0, min_value=0.0, max_value=100_000.0,
    title="Введено в действие общей площади жилых домов (оперативные данные)",
    series=(
        _s("vvod-zhilya-mes", "1754555",
           "Жилые здания, жилые помещения в нежилых зданиях и жилые дома, построенные населением",
           "Ввод жилья за месяц", "Housing completed during the month", "Ввод жилья, всего",
           "ввод жилья, ввод жилья по регионам, построено жилья, введено жилья, сдача домов"),
        _s("vvod-zhilya-mkd-mes", "1754559", "Жилые здания многоквартирные",
           "Ввод жилья за месяц: многоквартирные дома", "Housing completed: apartment buildings",
           "Многоквартирные дома", "ввод многоквартирных домов, новостройки, мкд"),
        _s("vvod-zhilya-izhs-mes", "1754556", "Жилые дома,построенные населением",
           "Ввод жилья за месяц: дома, построенные населением", "Housing completed: homes built by households",
           "Дома населения (ИЖС)", "ижс, индивидуальное жилищное строительство, частные дома"),
    ),
)

INDUSTRY = RegionalSet(
    dataset=57806, series_dim="57940", extra_lines=(),
    filters=("30611_950473", "57937_1704141"),
    first_year=2015, section_num=12, section_name="Промышленное производство", section_en="Industrial production",
    unit="% к тому же месяцу прошлого года", unit_en="% of the same month a year earlier",
    note="Индекс производства, оперативные данные. Частота — месячная.",
    note_en="production index, preliminary data; monthly",
    scale=1.0, min_value=0.1, max_value=10_000.0,
    title="Индекс производства (оперативные данные) (ОКВЭД2)",
    series=(
        _s("ipp-dobycha-mes", "1692320", "ДОБЫЧА ПОЛЕЗНЫХ ИСКОПАЕМЫХ",
           "Индекс производства: добыча полезных ископаемых", "Production index: mining and quarrying",
           "Добыча полезных ископаемых", "индекс промышленного производства, ипп, добыча, промпроизводство"),
        _s("ipp-obrabotka-mes", "1692321", "ОБРАБАТЫВАЮЩИЕ ПРОИЗВОДСТВА",
           "Индекс производства: обрабатывающие производства", "Production index: manufacturing",
           "Обрабатывающие производства", "индекс промышленного производства, ипп, обработка, промпроизводство"),
        _s("ipp-energetika-mes", "1692750",
           "ОБЕСПЕЧЕНИЕ ЭЛЕКТРИЧЕСКОЙ ЭНЕРГИЕЙ, ГАЗОМ И ПАРОМ; КОНДИЦИОНИРОВАНИЕ ВОЗДУХА",
           "Индекс производства: электроэнергия, газ и пар", "Production index: electricity, gas and steam",
           "Электроэнергия, газ и пар", "производство электроэнергии, энергетика, ипп"),
        _s("ipp-vodosnabzhenie-mes", "1692748",
           "ВОДОСНАБЖЕНИЕ; ВОДООТВЕДЕНИЕ, ОРГАНИЗАЦИЯ СБОРА И УТИЛИЗАЦИИ ОТХОДОВ, ДЕЯТЕЛЬНОСТЬ ПО ЛИКВИДАЦИИ "
           "ЗАГРЯЗНЕНИЙ",
           "Индекс производства: водоснабжение, водоотведение и отходы",
           "Production index: water supply, sewerage and waste", "Водоснабжение и отходы", "ипп, водоснабжение"),
    ),
)

FREIGHT = RegionalSet(
    dataset=31076, series_dim="58787", extra_lines=(),
    filters=("30611_950473", "57937_1704141"),
    first_year=2006, section_num=16, section_name="Транспорт", section_en="Transport",
    unit="% к тому же месяцу прошлого года", unit_en="% of the same month a year earlier",
    note="Индекс тарифов на перевозку грузов для юридических лиц. Частота — месячная.",
    note_en="index of freight tariffs charged to businesses; monthly",
    scale=1.0, min_value=1.0, max_value=10_000.0,
    title="Индексы тарифов на грузовые перевозки",
    series=(
        _s("tarif-gruz-vse-mes", "1754338", "Транспорт - все виды",
           "Индекс тарифов на грузовые перевозки: все виды транспорта", "Freight tariffs: all modes of transport",
           "Грузоперевозки, все виды", "стоимость грузоперевозок, тарифы на перевозку грузов, грузоперевозки"),
        _s("tarif-gruz-avto-mes", "1754341", "Автомобильный транспорт",
           "Индекс тарифов на грузовые перевозки: автомобильный транспорт", "Freight tariffs: road transport",
           "Грузоперевозки автомобилем", "стоимость перевозки грузов автомобилем, фура, автоперевозки"),
        _s("tarif-gruz-zhd-mes", "1754337", "Железнодорожный транспорт",
           "Индекс тарифов на грузовые перевозки: железная дорога", "Freight tariffs: rail transport",
           "Грузоперевозки по железной дороге", "жд тарифы, тарифы ржд, перевозка грузов по железной дороге"),
    ),
)

SETS: tuple[RegionalSet, ...] = (AGRO_PRICES, HOUSING, INDUSTRY, FREIGHT)
SERIES_BY_CODE: dict[str, tuple[RegionalSet, RegionalSeries]] = {
    s.code: (rset, s) for rset in SETS for s in rset.series
}


def unit_of(rset: RegionalSet, series: RegionalSeries) -> tuple[str, str]:
    return UNIT_OVERRIDES.get(series.code, (rset.unit, rset.unit_en))


def artifact_rows() -> list[dict]:
    """Строки каталога регионов (формат ``app/data/regional/indicators.json``); дописываются при сиде."""
    rows = []
    for rset in SETS:
        for n, s in enumerate(rset.series, start=1):
            unit, _ = unit_of(rset, s)
            rows.append({
                "code": s.code,
                "table_code": f"{rset.section_num}.m{n}",
                "section_num": rset.section_num,
                "section_name": rset.section_name,
                "name": s.name,
                "unit": unit,
                "note": rset.note,
                "source_sheet": f"ЕМИСС, витрина {rset.dataset}",
                "frequency": "monthly",
            })
    return rows


def copy_en() -> dict[str, dict[str, str | None]]:
    out = {}
    for rset in SETS:
        for s in rset.series:
            _, unit_en = unit_of(rset, s)
            out[s.code] = {"name": s.name_en, "unit": unit_en, "note": rset.note_en, "section": rset.section_en}
    return out
