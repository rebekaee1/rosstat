"""Цены производителей и цены в строительстве России из ЕМИСС (19.11.2026).

До 19.11.2026 на сайте был только общий индекс цен производителей промышленных товаров (`ppi`). Люди ищут
разбивку: Яндекс — «индексы цен производителей по видам экономической деятельности росстат», «на строительную
продукцию» (≈344 показа за 30 дней), пустой внутренний поиск «индекс цен производителей промышленность». Здесь —
помесячные ряды Росстата по России целиком, с января 2017 года (по объектам строительства — с 2025 года):

- 57609 — цены производителей по видам деятельности, канал «Внутренний рынок» (14 ходовых видов из 250);
- 57608 — цены производителей по товарам, канал «Внутренний рынок» (18 ходовых товаров из 1672; сталь — отдельно,
  `emiss_steel`, 57606);
- 57724 — средние цены, по которым строительные организации покупают основные материалы (10 из 163);
- 57796 — цены производителей на строительную продукцию (всего и три вида работ из 372 строк);
- 63349 — индексы цен по группам объектов капитального строительства (все 4 группы, с 2025 года).

Индексы хранятся как изменение к тому же месяцу прошлого года в процентах (индекс 104,5 → 4,5): это то, что
публикует Росстат, и то, что люди спрашивают («насколько подорожало за год»). Средние цены — в рублях за единицу.

Не взяты (живые запросы 19.11.2026): 57709 «индексы цен на стройматериалы» — по тем же материалам, что 57724, а
рубли за кубометр понятнее индекса; «Всего по обследуемым видам» 57609 на внутреннем рынке не публикуется, общий
индекс уже есть (`ppi`); электроэнергия в 57608 — десятки строк по категориям потребителей и тарифам без одной
понятной; минеральные удобрения в 57608 по России не опубликованы; песок и гравий в 57724 — средняя цена прыгает в 2–3 раза
от месяца к месяцу (песок: 889 → 292 → 976 ₽/м³ в мае–июле 2026), это смена набора покупок, а не рынок.

В 2021 году у части товаров 57608 Росстат не опубликовал по 2–6 месяцев (смена классификатора) — пропуск остаётся
пропуском.
"""

from __future__ import annotations

from dataclasses import dataclass

YOY = "1704141"              # 57937 «Отчетный месяц к соответствующему месяцу предыдущего года»
DOMESTIC = "1744136"         # 58601 канал «Внутренний рынок»
PERCENT, RUBLE = "950473", "950351"
FIRST_YEAR = 2017


@dataclass(frozen=True)
class Dataset:
    id: int
    line_dim: str                # измерение позиций (ОКВЭД2 57940, ОКПД2 57939, объекты 63351)
    filters: tuple[str, ...]     # постоянные фильтры: вид показателя, канал, единица
    kind: str                    # "yoy" — индекс к тому же месяцу прошлого года; "price" — рубли за единицу
    first_year: int = FIRST_YEAR
    unit_dim: bool = False       # 57724: единица ОКЕИ — строка ответа (у материалов разные единицы)
    category: str = "Цены"

    @property
    def source_url(self) -> str:
        return f"https://www.fedstat.ru/indicator/{self.id}"


DATASETS: dict[int, Dataset] = {
    57609: Dataset(57609, "57940", (f"57937_{YOY}", f"58601_{DOMESTIC}", f"30611_{PERCENT}"), "yoy"),
    57608: Dataset(57608, "57939", (f"57937_{YOY}", f"58601_{DOMESTIC}", f"30611_{PERCENT}"), "yoy"),
    57796: Dataset(57796, "57940", (f"57937_{YOY}", f"30611_{PERCENT}"), "yoy"),
    63349: Dataset(63349, "63351", (f"57937_{YOY}", f"30611_{PERCENT}"), "yoy", first_year=2025),
    57724: Dataset(57724, "57939", (f"30611_{RUBLE}",), "price", unit_dim=True),
}

# ОКЕИ 57956 в 57724: oid → (название в ответе, единица на сайте, единица по-английски).
UNITS: dict[str, tuple[str, str, str]] = {
    "1694826": ("Кубический метр", "руб./м³", "RUB/m³"),
    "1694829": ("Тонна;^метрическая тонна (1000 кг)", "руб./т", "RUB/t"),
    "1694824": ("Квадратный метр", "руб./м²", "RUB/m²"),
    "1757957": ("Тысяча условных кирпичей", "руб./тыс. шт.", "RUB per 1,000 bricks"),
}


@dataclass(frozen=True)
class Series:
    dataset: int
    items: tuple[str, ...]   # oid позиции; у части позиций Росстат с 2022 года завёл новый oid с тем же названием
    label: str               # название позиции у Росстата (так приходит в ответе)
    name: str
    name_en: str
    explanation: str
    explanation_en: str
    unit_oid: str = ""       # только 57724
    first_year: int | None = None   # позиция с новым описанием товара — ряд начинается с него
    keywords: str = ""

    @property
    def spec(self) -> Dataset:
        return DATASETS[self.dataset]

    @property
    def unit(self) -> str:
        return UNITS[self.unit_oid][1] if self.unit_oid else "%"

    @property
    def unit_en(self) -> str:
        return UNITS[self.unit_oid][2] if self.unit_oid else "%"

    @property
    def start_year(self) -> int:
        return self.first_year or self.spec.first_year


def _activity(oid, label, short, short_en, what, what_en, keywords=""):
    return Series(
        57609, (oid,), label, f"Цены производителей за год: {short}", f"Producer prices, year on year: {short_en}",
        f"На сколько процентов цены, по которым предприятия ({what}) продают продукцию покупателям в России, выше "
        "или ниже, чем в том же месяце год назад.",
        f"How much higher or lower, in per cent, the prices at which producers ({what_en}) sell to buyers in Russia "
        "are than in the same month a year earlier.",
        keywords=keywords,
    )


def _good(oid, label, short, short_en, keywords="", acc=None, first_year=None):
    return Series(
        57608, (oid,), label, f"Цена производителей за год: {short}", f"Producer price, year on year: {short_en}",
        f"На сколько процентов цена, по которой производители продают {acc or short} покупателям в России, выше или "
        "ниже, чем в том же месяце год назад.",
        f"How much higher or lower, in per cent, the price at which producers sell {short_en} to buyers in Russia "
        "is than in the same month a year earlier.",
        first_year=first_year, keywords=keywords,
    )


def _material(oid, label, unit_oid, short, short_en, what, what_en, keywords="", first_year=None, items=None):
    per = UNITS[unit_oid][1].removeprefix("руб./")
    return Series(
        57724, items or (oid,), label, f"Цена стройматериалов: {short}", f"Construction materials price: {short_en}",
        f"Средняя цена, по которой строительные организации в России покупают {what}, рублей за {per}, с доставкой.",
        f"Average price at which construction companies in Russia buy {what_en}, roubles per "
        f"{UNITS[unit_oid][2].removeprefix('RUB/').removeprefix('RUB per ')}, delivery included.",
        unit_oid=unit_oid, first_year=first_year, keywords=keywords,
    )


def _works(oid, label, short, short_en, what, what_en, keywords="", first_year=None):
    return Series(
        57796, (oid,), label, f"Цены в строительстве за год: {short}", f"Construction prices, year on year: {short_en}",
        f"На сколько процентов цены строительных работ ({what}) выше или ниже, чем в том же месяце год назад.",
        f"How much higher or lower, in per cent, construction prices ({what_en}) are than in the same month a year "
        "earlier.",
        first_year=first_year, keywords=keywords,
    )


def _objects(oid, label, short, short_en, what, what_en, keywords=""):
    return Series(
        63349, (oid,), label, f"Стоимость стройки за год: {short}", f"Building costs, year on year: {short_en}",
        f"На сколько процентов дороже или дешевле, чем год назад, обходится строительство: {what}. Учитываются "
        "материалы, работа, машины и прочие затраты подрядчика.",
        f"How much more or less, in per cent, construction costs than a year earlier: {what_en}. Materials, labour, "
        "machinery and other contractor costs are included.",
        keywords=keywords,
    )


SERIES: dict[str, Series] = {
    # ── 57609: виды деятельности ────────────────────────────────────────────────────────────────────────────────
    "ppi-mining": _activity("1692320", "ДОБЫЧА ПОЛЕЗНЫХ ИСКОПАЕМЫХ", "добыча полезных ископаемых", "mining",
                            "нефтяные, газовые, угольные, рудные компании и карьеры",
                            "oil, gas, coal and ore companies and quarries", "ИЦП добыча, цены в добыче"),
    "ppi-manufacturing": _activity("1692321", "ОБРАБАТЫВАЮЩИЕ ПРОИЗВОДСТВА", "обрабатывающие производства",
                                   "manufacturing", "заводы и фабрики всех отраслей", "factories of all industries",
                                   "ИЦП промышленность, ИЦП обрабатывающие, цены в промышленности"),
    "ppi-energy": _activity("1692750", "ОБЕСПЕЧЕНИЕ ЭЛЕКТРИЧЕСКОЙ ЭНЕРГИЕЙ, ГАЗОМ И ПАРОМ; КОНДИЦИОНИРОВАНИЕ ВОЗДУХА",
                            "электроэнергия, газ и тепло", "electricity, gas and heat",
                            "электростанции, сети, газовые и тепловые компании",
                            "power plants, grids, gas and heat suppliers", "тарифы на электроэнергию для предприятий"),
    "ppi-water": _activity("1692748", "ВОДОСНАБЖЕНИЕ; ВОДООТВЕДЕНИЕ, ОРГАНИЗАЦИЯ СБОРА И УТИЛИЗАЦИИ ОТХОДОВ, "
                           "ДЕЯТЕЛЬНОСТЬ ПО ЛИКВИДАЦИИ ЗАГРЯЗНЕНИЙ", "водоснабжение и отходы",
                           "water supply and waste", "водоканалы и компании по вывозу и переработке отходов",
                           "water utilities and waste collection and recycling companies"),
    "ppi-oil-gas": _activity("1692336", "Добыча нефти и природного газа", "добыча нефти и газа",
                             "oil and gas extraction", "нефтяные и газовые компании", "oil and gas companies",
                             "цена нефти в России, цена газа для предприятий"),
    "ppi-coal-mining": _activity("1692335", "Добыча угля", "добыча угля", "coal mining", "угольные компании",
                                 "coal companies", "цена угля"),
    "ppi-food-industry": _activity("1692340", "Производство пищевых продуктов", "пищевая промышленность",
                                   "food industry", "производители продуктов питания", "food manufacturers",
                                   "отпускные цены на продукты, цены производителей продуктов"),
    "ppi-petroleum-products": _activity("1692348", "Производство кокса и нефтепродуктов", "нефтепереработка",
                                        "oil refining", "нефтеперерабатывающие заводы", "oil refineries",
                                        "цены на нефтепродукты, оптовые цены на топливо"),
    "ppi-chemicals": _activity("1692349", "Производство химических веществ и химических продуктов", "химия",
                               "chemicals", "химические заводы, включая производителей удобрений и пластмасс",
                               "chemical plants, including fertiliser and plastics makers", "цены на удобрения"),
    "ppi-pharma": _activity("1692309", "Производство лекарственных средств и материалов, применяемых в медицинских "
                            "целях и ветеринарии", "лекарства", "pharmaceuticals",
                            "фармацевтические заводы", "pharmaceutical plants", "цены на лекарства у производителей"),
    "ppi-building-materials": _activity("1692351", "Производство прочей неметаллической минеральной продукции",
                                        "цемент, стекло, кирпич", "cement, glass and bricks",
                                        "заводы цемента, бетона, кирпича, стекла и керамики",
                                        "cement, concrete, brick, glass and ceramics plants",
                                        "цены на стройматериалы, цена цемента, цена кирпича"),
    "ppi-metallurgy": _activity("1692352", "Производство металлургическое", "металлургия", "metallurgy",
                                "металлургические заводы", "steel and non-ferrous metal plants",
                                "цены на металл, цены на металлопрокат"),
    "ppi-wood": _activity("1692796", "Обработка древесины и производство изделий из дерева и пробки, кроме мебели, "
                          "производство изделий из соломки и материалов для плетения", "древесина и пиломатериалы",
                          "wood and sawn timber", "лесопилки и деревообрабатывающие заводы",
                          "sawmills and woodworking plants", "цены на пиломатериалы, цена доски"),
    "ppi-vehicles": _activity("1692819", "Производство автотранспортных средств, прицепов и полуприцепов",
                              "автомобили", "motor vehicles", "автозаводы и производители прицепов",
                              "car plants and trailer makers", "цены на автомобили у производителей"),
    # ── 57608: товары ───────────────────────────────────────────────────────────────────────────────────────────
    "ppi-crude-oil": _good("1831798", "Нефть обезвоженная, обессоленная и стабилизированная", "нефть", "crude oil",
                           "цена нефти в России, цена нефти для НПЗ", first_year=2021),
    "ppi-natural-gas": _good("1693328", "Газ горючий природный (газ естественный)", "природный газ", "natural gas",
                             "цена газа для промышленности"),
    "ppi-hard-coal": _good("1694797", "Уголь каменный", "каменный уголь", "hard coal", "цена угля", first_year=2018),
    "ppi-gasoline": _good("1694068", "Бензин автомобильный", "автомобильный бензин", "motor petrol",
                          "оптовая цена бензина, цена бензина на заводе, биржевая цена бензина"),
    "ppi-diesel": _good("1694081", "Топливо дизельное", "дизельное топливо", "diesel fuel",
                        "оптовая цена дизеля, цена солярки на заводе"),
    "ppi-cement": _good("1693124", "Портландцемент, цемент глиноземистый, цемент шлаковый и аналогичные "
                        "гидравлические цементы", "цемент", "cement", "цена цемента"),
    "ppi-copper": _good("1757782", "Медь рафинированная необработанная", "медь", "refined copper", "цена меди в России"),
    "ppi-aluminium": _good("1709082", "Алюминий необработанный", "алюминий", "primary aluminium",
                           "цена алюминия в России"),
    "ppi-beef": _good("1694621", "Говядина, кроме субпродуктов", "говядина", "beef", "оптовая цена говядины", "говядину"),
    "ppi-pork": _good("1694620", "Свинина, кроме субпродуктов", "свинина", "pork", "оптовая цена свинины", "свинину"),
    "ppi-poultry": _good("1757893", "Мясо домашней птицы", "мясо птицы", "poultry meat",
                         "оптовая цена курицы, цена бройлера"),
    "ppi-milk": _good("1757631", "Молоко питьевое пастеризованное", "пастеризованное молоко", "pasteurised milk",
                      "отпускная цена молока"),
    "ppi-butter": _good("1757634", "Масло сливочное", "сливочное масло", "butter", "отпускная цена масла"),
    "ppi-sugar": _good("1693843", "Сахар белый свекловичный в твердом состоянии без вкусоароматических или красящих "
                       "добавок", "сахар", "white beet sugar", "оптовая цена сахара"),
    "ppi-sunflower-oil": _good("1693003", "Масло подсолнечное и его фракции рафинированные, но не подвергнутые "
                               "химической модификации", "подсолнечное масло", "refined sunflower oil",
                               "отпускная цена подсолнечного масла"),
    "ppi-flour": _good("1757645", "Мука пшеничная", "пшеничная мука", "wheat flour", "оптовая цена муки", "пшеничную муку"),
    "ppi-bread": _good("1693828", "Хлеб и хлебобулочные изделия недлительного хранения", "хлеб", "bread",
                       "отпускная цена хлеба"),
    "ppi-cars": _good("1693287", "Автомобили легковые", "легковые автомобили", "passenger cars",
                      "цены на новые автомобили у заводов"),
    # ── 57724: средние цены стройматериалов ─────────────────────────────────────────────────────────────────────
    "build-cement": _material("1693124", "Портландцемент, цемент глиноземистый, цемент шлаковый и аналогичные "
                              "гидравлические цементы", "1694829", "цемент", "cement", "цемент", "cement",
                              "цена цемента за тонну, стоимость цемента", first_year=2022),
    "build-crushed-stone": _material("1693348", "Щебень", "1694826", "щебень", "crushed stone", "щебень",
                                     "crushed stone", "цена щебня, стоимость щебня за куб"),
    "build-concrete": _material("1793407", "Бетон, готовый для заливки (товарный бетон)", "1694826",
                                "товарный бетон", "ready-mix concrete", "готовый товарный бетон",
                                "ready-mix concrete", "цена бетона, стоимость бетона за куб",
                                items=("1693127", "1793407")),
    "build-mortar": _material("1694306", "Растворы строительные", "1694826", "строительный раствор",
                              "building mortar", "готовый строительный раствор", "ready-mixed mortar",
                              "цена раствора"),
    "build-brick": _material("1694273", "Кирпич керамический неогнеупорный строительный", "1757957",
                             "керамический кирпич", "clay bricks", "керамический строительный кирпич",
                             "clay building bricks", "цена кирпича, стоимость кирпича"),
    "build-silicate-brick": _material("1757755", "Кирпич силикатный и шлаковый", "1757957", "силикатный кирпич",
                                      "sand-lime bricks", "силикатный кирпич", "sand-lime bricks",
                                      "цена силикатного кирпича"),
    "build-floor-slabs": _material("1758236", "Плиты перекрытий железобетонные", "1694826",
                                   "плиты перекрытий", "floor slabs", "железобетонные плиты перекрытий",
                                   "reinforced concrete floor slabs", "цена плит перекрытия"),
    "build-timber": _material("1694031", "Пиломатериалы хвойных пород", "1694826", "хвойные пиломатериалы",
                              "softwood lumber", "хвойные пиломатериалы (доска, брус)",
                              "softwood lumber (boards and beams)", "цена доски, цена бруса, цена пиломатериалов"),
    "build-insulation": _material("1757763", "Материалы и изделия минеральные тепло- и звукоизоляционные", "1694826",
                                  "минеральный утеплитель", "mineral insulation",
                                  "минеральную тепло- и звукоизоляцию (минвату)",
                                  "mineral heat and sound insulation (mineral wool)", "цена утеплителя, цена минваты"),
    "build-bitumen": _material("1694134", "Битумы нефтяные", "1694829", "битум", "bitumen", "нефтяной битум",
                               "petroleum bitumen", "цена битума"),
    # ── 57796: строительная продукция ───────────────────────────────────────────────────────────────────────────
    "ppi-construction": _works("1692933", "Всего по обследуемым видам экономической деятельности", "всего",
                               "total", "все виды строительной продукции", "all construction output",
                               "индекс цен производителей на строительную продукцию, ИЦП строительство"),
    "ppi-construction-buildings": _works("1692441", "Строительство жилых и нежилых зданий", "жилые и нежилые здания",
                                         "residential and non-residential buildings",
                                         "строительство жилых и нежилых зданий",
                                         "residential and non-residential buildings", first_year=2018),
    "ppi-construction-civil": _works("1692359", "Строительство инженерных сооружений",
                                     "дороги, мосты и сети", "roads, bridges and utility networks",
                                     "дороги, мосты, трубопроводы и сети", "roads, bridges, pipelines and networks"),
    "ppi-construction-specialised": _works("1692360", "Работы строительные специализированные",
                                           "отделка и монтаж", "finishing and installation",
                                           "подготовка участка, монтаж, отделка", "site preparation, installation "
                                           "and finishing", "цены на ремонт, стоимость отделочных работ"),
    # ── 63349: группы объектов ──────────────────────────────────────────────────────────────────────────────────
    "build-cost-housing": _objects("1856450", "Объекты жилищно-гражданского назначения",
                                   "жильё и общественные здания", "housing and public buildings",
                                   "жилые дома, школы, больницы, магазины, офисы",
                                   "homes, schools, hospitals, shops and offices",
                                   "стоимость строительства жилья, удорожание стройки"),
    "build-cost-industrial": _objects("1856451", "Объекты производственного назначения", "заводы и склады",
                                      "industrial buildings", "заводы, склады и другие производственные здания",
                                      "factories, warehouses and other industrial buildings"),
    "build-cost-roads": _objects("1856452", "Линейные объекты транспортной дорожной инфраструктуры", "дороги",
                                 "roads", "автомобильные дороги и мосты", "roads and bridges",
                                 "стоимость строительства дорог"),
    "build-cost-power-lines": _objects("1856469", "Линейные объекты энергетического хозяйства",
                                       "линии электропередачи и сети", "power lines and grids",
                                       "линии электропередачи, газо- и теплосети",
                                       "power lines, gas and heat networks"),
}

_YOY_METHODOLOGY = (
    "Росстат каждый месяц собирает цены одних и тех же товаров и услуг у выборки предприятий и сравнивает их с ценами "
    "того же месяца прошлого года. Цены без НДС, акцизов и других налогов. Число на сайте — изменение в процентах: "
    "4,5 означает, что за год цены выросли на 4,5 %, минус — что снизились. Значение за месяц выходит примерно через "
    "три недели после его окончания. С 2023 года данные приведены без учёта новых субъектов Российской Федерации."
)
_YOY_METHODOLOGY_EN = (
    "Each month Rosstat collects prices of the same goods and services from a sample of companies and compares them "
    "with the same month a year earlier. Prices exclude VAT, excise and other taxes. The figure shown is the change "
    "in per cent: 4.5 means prices rose 4.5% over the year, a negative value means they fell. Monthly figures are "
    "released about three weeks after the month ends. From 2023, the data exclude the territories identified by "
    "Rosstat as new constituent entities."
)
_PRICE_METHODOLOGY = (
    "Росстат каждый месяц собирает у строительных организаций цены, по которым они фактически купили основные "
    "материалы, детали и конструкции, и считает среднюю по России. В цену входят доставка и наценка поставщика, НДС "
    "не входит. Значение за месяц выходит примерно через три недели после его окончания. С 2023 года данные "
    "приведены без учёта новых субъектов Российской Федерации."
)
_PRICE_METHODOLOGY_EN = (
    "Each month Rosstat collects the prices at which construction companies actually bought the main materials, parts "
    "and structures and averages them for Russia. Delivery and supplier mark-ups are included, VAT is not. Monthly "
    "figures are released about three weeks after the month ends. From 2023, the data exclude the territories "
    "identified by Rosstat as new constituent entities."
)


def methodology(series: Series) -> tuple[str, str]:
    if series.spec.kind == "price":
        text, text_en = _PRICE_METHODOLOGY, _PRICE_METHODOLOGY_EN
    else:
        text, text_en = _YOY_METHODOLOGY, _YOY_METHODOLOGY_EN
    if series.first_year and series.first_year > series.spec.first_year:
        text += f" Ряд начинается с {series.first_year} года: с него Росстат публикует эту позицию в нынешнем виде."
        text_en += f" The series starts in {series.first_year}, the first year Rosstat publishes this item in its current form."
    if series.dataset == 63349:
        text += " Наблюдение по группам объектов Росстат ведёт с 2025 года."
        text_en += " Rosstat has published these building groups since 2025."
    return text, text_en


# Слова людей из запросов Яндекса и пустых поисков сайта (отчёт каталога ЕМИСС 19.11.2026).
KEYWORDS: dict[int, str] = {
    57609: "индексы цен производителей по видам экономической деятельности, индекс цен производителей, ИЦП, ИЦП по "
           "отраслям, цены производителей, отпускные цены, Росстат",
    57608: "индексы цен производителей по товарам, индекс цен производителей, ИЦП, цены производителей, отпускные "
           "цены, оптовые цены, Росстат",
    57796: "индексы цен производителей на строительную продукцию, индекс цен на строительную продукцию, ИЦП в "
           "строительстве, цены в строительстве, удорожание строительства, Росстат",
    63349: "индексы цен по группам объектов капитального строительства, индексы цен в строительстве, стоимость "
           "строительства, удорожание строительства, удорожание стройки, Росстат",
    57724: "цены на стройматериалы, стоимость стройматериалов, строительные материалы, средние цены на материалы, "
           "стройка, Росстат",
}


def seed_indicators():
    for code, series in SERIES.items():
        yield {
            "code": code,
            "name": series.name,
            "name_en": series.name_en,
            "unit": series.unit,
            "frequency": "monthly",
            "source": "Росстат",
            "source_url": series.spec.source_url,
            "description": series.explanation,
            "methodology": methodology(series)[0],
            "parser_type": "rosstat_emiss_producer_prices",
            "model_config_json": {"forecast_steps": 0},
            "is_active": True,
            "category": series.spec.category,
        }


def seo_keywords() -> dict[str, str]:
    return {
        code: ", ".join(part for part in (series.name, series.keywords, KEYWORDS[series.dataset]) if part)
        for code, series in SERIES.items()
    }


def seo_meta() -> dict[str, dict[str, str]]:
    out = {}
    for code, series in SERIES.items():
        since = series.start_year
        if series.spec.kind == "price":
            title = f"{series.name}, {series.unit} — Росстат"
            description = (f"{series.name} в России: средняя цена покупки строительными организациями, "
                           f"помесячно с {since} года, {series.unit}, без НДС.")
        else:
            title = f"{series.name} — изменение в %, Росстат"
            description = (f"{series.name}: на сколько процентов цены выше или ниже, чем год назад. "
                           f"Помесячно с {since} года, данные Росстата.")
        out[code] = {"seo_title": title, "seo_description": description}
    return out
