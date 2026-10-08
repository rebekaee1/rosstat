"""Typed economic vocabulary and bounded question grammar for public search.

The vocabulary describes measures, not saved visitor answers. Neutral grammar is
removed; unknown subjects, variants, geographic and period tokens remain required.
No external model, training, embeddings or analytics dependency.
"""
from __future__ import annotations

import math
import re
from collections import Counter

# Function words only: real/nominal/net/gross, age/sex, currencies and units are
# deliberately absent. Ordinary question wording must not become an AND facet.
QUESTION_WORDS = frozenset("""
что какой какая какие какое как сколько насколько где когда под покажи показать
найди найти ищу поиск хочу узнать данные статистика показатель показатели
мне меня пожалуйста нас наш наши нужен нужна нужно нужны есть это эти этот
был было была были будет будут стал стала стали стало происходит изменился изменилась
изменились меняется ли или либо а но с со от до о об у при через поправки
можно больше меньше чем всего каждый такая такой там сейчас пожалуйста
работнику работники работник людям человек человека стране живет живут
начисляют начислено платят платить денег деньги выдают дают заемщикам
how what which where when show find search tell please need want know data
statistics indicator indicators me my our us is are was were be been being
has have had do does did can could would will should it its this that these
those there their they them you your we on at to from with by as about into
than or but more less much many any some an a also now currently
money paid pay employee employees workers worker live living
country countries adjusting adjusted charge borrowers around way
receive receives received receiving recorded occur occurs occurring kept keep
held hold holding engaged carried out including includes include figures
using use used составил составила составило составили составляет составляли
observation observations during данных данным данными наблюдения наблюдениям наблюдениями
выполняют выполняет работает работают работало работали проходит проходят
получает получают получили значения значениях ведет ведут имеет имеют
находятся находится содержится содержит региона регионе региону регионе
""".split())

# Longest alias wins in search_intent. First alternative is a typed identity and
# supplies a stable ranking key; alternatives refer to the same economic measure.
LANGUAGE_CONCEPTS = (
 # «Сколько стоил бензин» — тот же вопрос о цене; глагол не должен становиться
 # обязательным словом названия и обнулять выдачу.
 (("price", "цена", "цену", "цене", "ценой", "стоил", "стоила", "стоило", "стоили", "стоит", "стоят"), ("search-subject-price",)),
 (("звр", "золотовалютные резервы", "золотовалютных резервов"), ("reserves", "international reserves", "foreign exchange reserves", "международные резервы")),
 (("цена меди", "цены на медь", "copper price", "copper prices", "медь"), ("copper", "copper", "медь", "меди")),
 (("серебро", "silver", "цена серебра"), ("silver", "silver", "серебр")),
 (("алюминий", "aluminum", "aluminium", "цена алюминия"), ("aluminum", "aluminum", "aluminium", "алюмини")),
 (("солана", "solana", "sol"), ("sol-usd", "solana", "солана")),
 (("уровень безработица",), ("unemployment", "безработ", "jobless")),
 (("средняя зарплата", "average wage", "average salary"), ("wage", "salary", "заработн", "зарплат")),
 (("реальная зарплата", "реальные зарплаты", "реальная заработная плата", "real wages", "real wage", "зарплата с учетом инфляции", "покупательная способность зарплаты"), ("wages-real", "real wage", "реальн заработн", "реальная заработная")),
 (("номинальная зарплата", "средняя номинальная заработная плата", "average nominal wage", "nominal wages", "получка", "оплата труда", "заработок", "earnings", "pay packet"), ("wages-nominal", "wages-nominal", "nominal wage", "номинальная заработная", "заработн", "salary")),
 (("медианная зарплата", "медианная заработная плата", "median wages", "median wage"), ("median-wage", "median wage", "медиан")),
 (("минималка", "минимальная заработная плата", "minimum salary"), ("minimum-wage", "minimum wage", "минималь")),
 (("реальные располагаемые доходы", "real disposable income"), ("income-real-disposable", "реальные располагаемые", "real disposable")),
 (("располагаемый доход", "располагаемые доходы", "disposable income"), ("income-disposable", "располагаем", "disposable income")),
 (("среднедушевые доходы", "доходы на душу", "доход на человека", "income per person", "per capita income"), ("income-per-capita", "среднедушев", "per capita income")),
 (("доходы населения", "денежные доходы", "household income"), ("household-income", "доходы населения", "household income", "денежные доходы")),
 (("неравенство доходов", "разрыв в доходах", "income inequality", "gini", "джини"), ("gini", "джини", "gini", "income inequality")),
 (("бедность", "бедности", "poverty", "poverty rate", "черта бедности"), ("poverty", "бедност", "poverty")),
 (("продукты питания", "цены на продукты", "продовольственная инфляция", "food inflation", "food price", "еда", "grocery", "food", "продукты"), ("cpi-food", "продовольствен", "food price", "food and non alcoholic")),
 (("food sector", "пищевая отрасль"), ("food-industry", "food", "пищев", "продуктов питания")),
 (("базовая инфляция", "core inflation", "core cpi"), ("cpi-core", "core inflation", "core consumer price", "базов")),
 (("дороговизна", "подорожание", "рост стоимости жизни", "cost of living", "consumer inflation"), ("cpi", "inflation", "hicp", "потребительских цен", "consumer price")),
 (("индекс цен производителей", "producer price index", "producer inflation", "заводские цены"), ("ppi", "producer price", "цен производителей")),
 (("обрабатывающая промышленность", "обработки", "обработка", "manufacturing output", "manufacturing production", "manufacturing"), ("ipi-manufacturing", "manufacturing", "обрабатывающ")),
 (("добывающая промышленность", "добыча", "mining output", "mining production", "mining"), ("ipi-mining", "mining", "добывающ", "добыча полезных")),
 (("промышленность", "промышленного производства", "заводы", "industrial output", "factories"), ("ipi", "industrial production", "промышленного производства")),
 (("розничная торговля", "розничные продажи", "retail sales", "retail turnover", "магазины"), ("retail", "retail sales", "retail trade", "розничн")),
 (("оптовая торговля", "wholesale trade", "wholesale turnover", "оптовики"), ("wholesale", "wholesale", "оптов")),
 (("расходы домашних хозяйств", "потребление домашних хозяйств", "household consumption", "household spending", "consumer spending"), ("household-consumption", "household final consumption", "household consumption", "домашних хозяйств", "personal consumption expenditures")),
 (("платные услуги", "услуги населению", "market services", "paid services"), ("services-paid", "платных услуг", "market services", "услуг населению")),
 (("реальный ввп", "рост ввп", "real gdp", "gdp growth", "экономический рост"), ("gdp-real", "real gdp", "gdp growth", "физического объема ввп", "валового внутреннего продукта", "gross domestic product")),
 (("номинальный ввп", "ввп в текущих ценах", "nominal gdp", "gdp current prices", "gdp current dollars", "размер экономики"), ("gdp-nominal", "current prices", "current dollars", "текущих ценах", "текущие цены", "nominal gdp")),
 (("ввп по ппс", "ввп по паритету", "ppp gdp", "gdp ppp"), ("gdp-ppp", "purchasing power parity", "паритету покупательной", "ppp")),
 (("дефлятор ввп", "gdp deflator"), ("gdp-deflator", "gdp deflator", "дефлятор")),
 (("валовой национальный доход", "gross national income", "gni"), ("gni", "gross national income", "валовой национальный доход")),
 (("инвестиции в основной капитал", "fixed capital investment", "gross fixed capital formation"), ("capital-investment", "основной капитал", "fixed capital")),
 (("валовое накопление капитала", "gross capital formation"), ("capital-formation", "gross capital formation", "валовое накопление капитала")),
 (("прямые иностранные инвестиции", "foreign direct investment", "fdi"), ("fdi", "foreign direct investment", "прямых иностранных")),
 (("численность занятых", "число занятых", "employment count", "employed persons", "работающие люди"), ("employment-count", "занятых", "employed", "employment")),
 (("участие в рабочей силе", "labour force participation", "labor force participation"), ("labour-participation", "participation rate", "участия в рабочей силе")),
 (("вакансии", "vacancies", "job openings"), ("vacancies", "ваканс", "vacancies", "job openings")),
 (("отработанные часы", "hours worked", "рабочие часы"), ("hours-worked", "hours worked", "отработан")),
 (("производительность труда", "labour productivity", "labor productivity", "выработка на работника"), ("labour-productivity", "productivity", "производительность труда")),
 (("жители", "жителей", "житель", "resident count", "residents", "люди", "people"), ("population", "population", "населен")),
 (("рост населения", "population growth"), ("population-growth", "population growth", "прирост населения", "изменение численности")),
 (("рождаемость", "родившиеся", "родившихся", "новорожденные", "births", "birth rate"), ("births", "birth", "родивш", "рождаем")),
 (("суммарный коэффициент рождаемости", "fertility rate", "total fertility"), ("fertility", "fertility", "суммарный коэффициент")),
 (("смертность", "умерших", "deaths", "mortality", "death rate"), ("mortality", "mortality", "death", "смертност", "умерш")),
 (("продолжительность жизни", "долголетие", "life expectancy"), ("life-expectancy", "life expectancy", "продолжительность жизни")),
 (("миграционный прирост", "net migration", "миграция", "migration", "переезды"), ("migration", "migration", "миграцион")),
 (("цены на жилье", "стоимость жилья", "цены квартир", "house prices", "housing prices", "квартиры"), ("housing-price", "housing price", "house price", "цен на жилье", "средние цены", "рынке жилья")),
 (("ввод жилья", "введено жилья", "новостройки", "housing completions", "new housing completed"), ("housing-completions", "ввод", "введено в действие", "housing completions", "dwellings completed")),
 (("разрешения на строительство", "building permits", "construction permits"), ("building-permits", "building permits", "разрешени")),
 (("аренда жилья", "съем жилья", "rent prices", "housing rent"), ("rent", "rent", "аренд")),
 (("ставки по ипотеке", "ипотечная ставка", "mortgage rates", "mortgage interest rate"), ("mortgage-rate", "mortgage rate", "mortgage interest", "ставк", "ипотеч")),
 (("выдача ипотеки", "объем ипотеки", "mortgage lending volume", "mortgage originations"), ("mortgage-volume", "объем", "выданных ипотечных", "mortgage lending", "mortgage originations")),
 (("потребительские кредиты", "потребительское кредитование", "consumer credit", "consumer lending"), ("consumer-credit", "consumer credit", "потребительск")),
 (("ставки по кредитам", "кредитные ставки", "bank lending rates", "lending interest rates", "процент по кредиту"), ("credit-rate", "lending rate", "interest rates on loans", "ставк", "кредит")),
 (("ставка центробанка", "policy rate", "central bank policy rate"), ("key-rate", "policy rate", "ключевая ставка")),
 (("денежная масса м2", "денежная масса m2", "money supply m2", "broad money"), ("m2", "money supply", "денежная масса", "broad money")),
 (("ставки по депозитам", "депозитные ставки", "deposit interest rate", "процент по вкладу"), ("deposit-rate", "deposit interest", "ставка по вкладам")),
 (("вклады населения", "депозиты населения", "household deposits", "personal deposits"), ("household-deposits", "депозит", "вклад", "household deposits")),
 (("государственный долг", "госдолг", "government debt", "public debt"), ("government-debt", "government debt", "public debt", "государственн")),
 (("внешний государственный долг", "external public debt"), ("external-debt", "external debt", "внешний долг", "внешнего долга")),
 (("дефицит бюджета", "профицит бюджета", "сальдо бюджета", "budget balance", "budget deficit", "budget surplus"), ("budget-balance", "budget balance", "deficit", "сальдо бюджета", "дефицит")),
 (("расходы бюджета", "бюджетные расходы", "госрасходы", "government spending", "government expenditure"), ("budget-expenditure", "government expenditure", "government spending", "расходы бюджета")),
 (("доходы бюджета", "бюджетные доходы", "government revenue", "budget revenue"), ("budget-revenue", "government revenue", "доходы бюджета")),
 (("экспорт", "exports", "продажи за границу"), ("exports", "export", "экспорт")),
 (("импорт", "imports", "покупки за границей"), ("imports", "import", "импорт")),
 (("торговый баланс", "сальдо торговли", "trade balance", "trade gap"), ("trade-balance", "trade balance", "торговый баланс", "сальдо торговли")),
 (("текущий счет", "current account"), ("current-account", "current account", "текущего счета")),
 (("международные резервы", "валютные резервы", "international reserves", "foreign exchange reserves"), ("reserves", "international reserves", "foreign exchange reserves", "международные резервы")),
 (("курс валюты", "обменный курс", "exchange rate"), ("exchange-rate", "exchange rate", "обменный курс", "курс")),
 (("природный газ", "natural gas"), ("natural-gas", "natural gas", "природный газ")),
 (("цены газа", "цена газа", "gas price", "gas prices"), ("gas-price", "natural gas", "природный газ", "газ")),
 (("выработка электроэнергии", "electricity generation", "power generation"), ("electricity-generation", "electricity generation", "электроэнергии")),
 (("цены электроэнергии", "цена электричества", "electricity prices", "счет за свет"), ("electricity-price", "electricity price", "электроэнергию")),
 (("производство автомобилей", "car production", "automobile production"), ("car-production", "motor vehicles", "автомобил", "car production")),
 (("продажи автомобилей", "car sales", "new car sales"), ("car-sales", "car sales", "vehicle sales", "продажи автомобилей")),
 (("сельское хозяйство", "сельхозпроизводство", "agricultural output", "agricultural production"), ("agriculture", "agricultural", "сельского хозяйства")),
 (("урожай зерна", "сбор зерна", "зерна собрали", "зерна собрано", "grain harvest", "grain harvested"), ("grain-harvest", "grain", "зерна", "зернов")),
 (("туристы", "туристические прибытия", "tourist arrivals", "tourism arrivals"), ("tourism", "tourist arrivals", "турист", "tourism")),
 (("потребительская уверенность", "настроение покупателей", "consumer confidence", "consumer sentiment"), ("consumer-confidence", "consumer confidence", "потребительской уверенности", "consumer sentiment")),
 (("индекс менеджеров по закупкам", "pmi", "purchasing managers index"), ("pmi", "purchasing managers", "менеджеров по закупкам")),
)


def prepare_language(text: str) -> str:
    """Resolve a few compositional questions while retaining unknown qualifiers.

    Only recognised subject/comparison tokens are consumed. A geographic, date,
    currency, industry, age or other unrecognised token survives the rewrite.
    """
    # Productive inflections of unambiguous economic nouns. This is a bounded
    # lexicon; arbitrary words are never truncated into a popular search topic.
    inflections = ((r"инфляци[а-я]*", "инфляция"), (r"зарплат[а-я]*", "зарплата"),
        (r"безработиц[а-я]*", "безработица"), (r"пенси(?:я|и|ю|ей|ях|ям)", "пенсия"))
    words = [next((replacement for pattern, replacement in inflections if re.fullmatch(pattern, word)), word)
        for word in text.split()]
    # The native energy-unit abbreviation includes an explicit million scale.
    # Expanding it before aliases preserves two independent quantity facets.
    words = [piece for word in words for piece in (("million", "btu") if word == "mmbtu" else (word,))]
    # A food industry is a subject of GDP/employment/compensation, rather than
    # a consumer-price measure. Require both the sector and measure context;
    # explicit food prices retain their price role and all outside words remain.
    sector_measure = any(re.fullmatch(r"gdp|ввп|employment|занятост.*|compensation", word) for word in words)
    sector = any(re.fullmatch(r"manufacturing|industr(?:y|ies)|sector|производств.*|отрасл.*", word) for word in words)
    outside_valuation = re.sub(r"\b(?:current|constant) prices\b|\b(?:текущих|постоянных) ценах\b", " ", " ".join(words))
    price = any(re.fullmatch(r"prices?|inflation|cpi|цен.*|инфляци.*", word) for word in outside_valuation.split())
    food_sector = sector_measure and sector and not price
    if food_sector:
        words = [replacement for word in words for replacement in
            (("food", "sector") if word == "food" else (word,))]
    text = " ".join(words)
    def consume(patterns: tuple[str, ...], replacement: str) -> str:
        retained = [word for word in words if not any(re.fullmatch(p, word) for p in patterns)]
        return replacement + " " + " ".join(retained)
    def has(pattern: str) -> bool:
        return any(re.fullmatch(pattern, word) for word in words)
    has_currency_scale = has(r"миллион.*|миллиард.*|млн|млрд|million.*|billion.*")
    if has(r"доллар.*|dollars?|usd") and has(r"иен.*|йен.*|yen|jpy") and not has_currency_scale:
        return consume((r"доллар.*|dollars?|usd", r"иен.*|йен.*|yen|jpy", r"сша|us|american|japanese|японск.*", r"курс.*|exchange|rate"), "usd jpy")
    if has(r"доллар.*|dollars?|usd") and (has(r"руб.*|rubles?|roubles?|rub") or (words and words[-1] in ("r", "ru", "ру"))) and not has_currency_scale:
        return consume((r"доллар.*|dollars?|usd", r"руб.*|rubles?|roubles?|rub|r|ru|ру", r"сша|us|american", r"курс.*|exchange|rate"), "usd rub")
    # A bare currency request ("usd", "dollar rate", "us dollar exchange rate")
    # means the exchange rate. Only a query made entirely of the currency word
    # and rate filler qualifies, so "gdp usd" keeps USD as a unit facet.
    fx_filler = r"rates?|exchange|курс.*|today|сегодня|current|текущий|сша|us|american|dollars?|доллар.*|usd|euros?|eur|евро|yuan|cny|юан.*"
    if words and all(re.fullmatch(fx_filler, word) for word in words):
        if any(re.fullmatch(r"dollars?|доллар.*|usd", word) for word in words) and not any(re.fullmatch(r"euros?|eur|евро|yuan|cny|юан.*", word) for word in words):
            return "usd rub"
        if any(re.fullmatch(r"euros?|eur", word) for word in words) and not any(re.fullmatch(r"dollars?|доллар.*|usd|yuan|cny|юан.*", word) for word in words):
            return "eur rub"
        if any(re.fullmatch(r"yuan|cny", word) for word in words) and not any(re.fullmatch(r"dollars?|доллар.*|usd|euros?|eur|евро|юан.*", word) for word in words):
            return "cny rub"
    if has(r"завод.*|промышленност.*|factories|industry") and has(r"выпуска.*|производ.*|producing|produce|output"):
        return consume((r"завод.*|промышленност.*|factories|industry", r"выпуска.*|производ.*|producing|produce|output", r"продукц.*"), "industrial production")
    if not food_sector and has(r"продукт.*|food|grocery") and has(r"подорож.*|дороже|expensive|price.*"):
        return consume((r"продукт.*|food|grocery", r"подорож.*|дороже|expensive|price.*", r"магазин.*|shopping|become"), "food inflation")
    if has(r"жиль.*|housing|homes?|dwellings?") and has(r"достро.*|ввели|введен.*|completed|completions"):
        return consume((r"жиль.*|housing|homes?|dwellings?", r"достро.*|ввели|введен.*|completed|completions", r"нового|новое|new|эксплуатац.*|put|use"), "housing completions")
    if has(r"уверенн.*|уверен.*|confident|confidence") and has(r"покуп.*|потребител.*|purchases|consumers?"):
        return consume((r"уверенн.*|уверен.*|confident|confidence", r"покуп.*|потребител.*|purchases|consumers?", r"люди|people|оценива.*|feel|финанс.*|finances|свои|будущие|future"), "consumer confidence")
    if has(r"реальн.*|real") and (has(r"зарплат.*|wages?|salary") or (has(r"заработн.*") and has(r"плат.*"))):
        return consume((r"реальн.*|real", r"зарплат.*|wages?|salary", r"заработн.*", r"плат.*"), "real wages")
    if has(r"медианн.*|median") and (has(r"зарплат.*|wages?|salary") or (has(r"заработн.*") and has(r"плат.*"))):
        return consume((r"медианн.*|median", r"зарплат.*|wages?|salary", r"заработн.*", r"плат.*"), "median wage")
    if has(r"работник.*|работнику|employee|worker") and has(r"начисля.*|начислен.*|paid") and has(r"денег|деньги|money"):
        return consume((r"работник.*|работнику|employee|worker", r"начисля.*|начислен.*|paid", r"денег|деньги|money", r"до|before", r"поправ.*|adjust.*", r"цен.*|prices?", r"среднем|average"), "nominal wages")
    if has(r"зарплат.*|wages?|salary") and has(r"до|before") and has(r"цен.*|инфляц.*|prices?|inflation") and has(r"поправ.*|adjust.*"):
        return consume((r"зарплат.*|wages?|salary", r"до|before", r"цен.*|инфляц.*|prices?|inflation", r"поправ.*|adjust.*", r"среднем|average"), "nominal wages")
    if has(r"экспорт.*|exports?") and has(r"импорт.*|imports?") and has(r"превыша.*|превыс.*|разниц.*|exceed.*|balance|difference"):
        return consume((r"экспорт.*|exports?", r"импорт.*|imports?", r"превыша.*|превыс.*|разниц.*|exceed.*|balance|difference", r"товар.*|goods|наоборот|other"), "trade balance")
    if has(r"зарплат.*|wages?|salary") and has(r"купить|покупатель.*|buy|purchas.*") and has(r"цен.*|инфляц.*|prices?|inflation"):
        return consume((r"зарплат.*|wages?|salary", r"купить|покупатель.*|buy|purchas.*", r"цен.*|инфляц.*|prices?|inflation", r"роста|рост|growth", r"после|after"), "real wages")
    if has(r"ипотек.*|mortgage") and has(r"ставк.*|процент.*|rates?|interest"):
        return consume((r"ипотек.*|mortgage", r"ставк.*|процент.*|rates?|interest"), "mortgage rates")
    if has(r"банки?|banks?") and has(r"процент.*|rates?|interest") and has(r"кредит.*|заем.*|loans?|borrowers?"):
        return consume((r"банки?|banks?", r"процент.*|rates?|interest", r"кредит.*|заем.*|loans?|borrowers?", r"дают|деньги|charge"), "bank lending rates")
    if has(r"жител.*|residents?") and has(r"жив.*|live|living"):
        return consume((r"жител.*|residents?", r"жив.*|live|living"), "population")
    if has(r"зерн.*|grain") and has(r"собрал.*|собран.*|harvest.*"):
        return consume((r"зерн.*|grain", r"собрал.*|собран.*|harvest.*", r"полей|полях|fields?"), "grain harvest")
    return text


# Required measure guards operate on identity/title, never on SEO keywords. These
# prevent a broad synonym from converting a demographic facet into its subject or
# selecting a neighbouring monetary measure.
MEASURE_RULES = {
    "search-subject-price": ((r"price|цен",), ()),
    "food-industry": ((r"food|пищев|продукт.*питани",),
        (r"consumer price|food price|food inflation|cpi|потребительск.*цен|продовольственн.*инфляц",)),
    "current-prices": ((r"current prices|current dollars|nominal|текущ.*цен|текущ.*доллар",),
        (r"constant prices|constant dollars|real gdp|постоянн.*цен|реальн.*ввп",)),
    "constant-prices": ((r"constant prices|constant dollars|real|постоянн.*цен|реальн",),
        (r"current prices|current dollars|nominal|текущ.*цен|текущ.*доллар",)),
    "earnings-income-contribution": ((r"earnings|заработк", r"contribution|вклад", r"change|изменени", r"income|доход"),
        (r"bank deposit|банковск.*вклад|deposit rate|ставк.*вклад",)),
    "consumption-change-contribution": ((r"consumption|потреблени", r"contribution|вклад", r"change|изменени"),
        (r"bank deposit|банковск.*вклад|deposit rate|ставк.*вклад",)),
    "farm-earnings": ((r"farm|фермерск", r"earnings|заработк"),
        (r"farm wage|farm salary|заработная плата|заработной платы",)),
    # "Frequently" alone does not prove daily use. A provider may expose an
    # explicit verified daily-use dimension as a human label in the identity.
    "internet-daily-use": ((r"internet|интернет", r"daily|every day|ежеднев|каждый день"), ()),
    "deprivation-weekly-spending": ((r"cannot afford|недоступн|не могут позволить", r"weekly|each week|еженедельн", r"small|небольш", r"spend|трат"), ()),
    "usd-rub": ((r"usd|dollar|доллар", r"rub|ruble|rouble|руб"), (r"dollar index|индекс доллара|effective exchange|эффективн.*курс",)),
    "usd-jpy": ((r"usd|dollar|доллар", r"jpy|yen|иен|йен"), (r"dollar index|индекс доллара|effective exchange|эффективн.*курс",)),
    "cny-rub": ((r"cny|yuan|юан", r"rub|ruble|rouble|руб"), (r"effective exchange|эффективн.*курс",)),
    "try-rub": ((r"try|lira|лир", r"rub|ruble|rouble|руб"), (r"effective exchange|эффективн.*курс",)),
    "kzt-rub": ((r"kzt|tenge|тенге", r"rub|ruble|rouble|руб"), (r"effective exchange|эффективн.*курс",)),
    "eur-rub": ((r"eur|euro|евро", r"rub|ruble|rouble|руб"), (r"effective exchange|эффективн.*курс",)),
    "eur-usd": ((r"eur|euro|евро", r"usd|dollar|доллар"), (r"dollar index|индекс доллара|effective exchange|эффективн.*курс",)),
    "credit-stock-households": ((r"credit|loan|кредит|заем", r"consumer|household|individual|физическ|населен"),
        (r"rate|interest|ставк|процент|origination|new loans|выдач|выдан|число.*кредит|number of.*loan|number of.*credit",)),
    "credit-stock-business": ((r"credit|loan|кредит|заем", r"business|corporat|compan|legal entit|юрид|бизнес|организац"),
        (r"rate|interest|ставк|процент|origination|new loans|выдач|выдан|число.*кредит|number of.*loan|number of.*credit",)),
    "research-personnel": ((r"research|r&d|исследован|разработк", r"personnel|staff|researcher|численност|персонал"),
        (r"expenditure|funding|расход|финансир|organizations|организаци",)),
    "research-organizations": ((r"research|r&d|исследован|разработк", r"organization|organisation|организац"),
        (r"expenditure|funding|расход|финансир|personnel|персонал",)),
    "wage-salary-employment": ((r"employment|jobs|наемн.*работник",), (r"earnings|compensation|оплата труда|доход",)),
    "net-earnings": ((r"net earnings|чист.*доход",), (r"gross earnings|валов.*доход",)),
    "employee-compensation": ((r"compensation.*employees|employee compensation|оплат.*труда",),
        (r"workers.*compensation|benefits|пособи",)),
    "benefits-workers-compensation": ((r"workers.*compensation|производственн.*травм",),
        (r"compensation of employees|employee compensation|оплат.*труда",)),
    "monetary-base": ((r"monetary base|денежн.*баз",), (r"broad money|money supply m2|денежная масса м2",)),
    "dividend-interest-rent-income": ((r"dividend|дивиденд", r"interest|процент", r"rent|рент|аренд"), (r"housing rent|аренда жилья",)),
    "budget-spending": ((r"budget|бюджет", r"expenditure|spending|расход"), (r"revenue|доход",)),
    "budget-revenue": ((r"budget|бюджет", r"revenue|доход"), (r"expenditure|расход",)),
    "birth-count": ((r"birth|родив",), (r"rate|коэффициент|на 1000|per 1000",)),
    "birth-rate": ((r"birth|рождаем", r"rate|коэффициент"), (r"number of births|число родив|численность родив",)),
    "death-rate": ((r"death|mortality|смертн|умер", r"rate|коэффициент"), (r"number of deaths|число умер|численность умер",)),
    "employment-count": ((r"employ|занят",), (r"unemploy|безработ|rate|ratio|уровень занятости",)),
    "unemployment-count": ((r"unemploy|безработ",), (r"rate|ratio|уровень безработицы",)),
    "employment-rate": ((r"employ|занят", r"rate|ratio|уровень"), (r"unemploy|безработ",)),
    "median-household-income": ((r"median|медиан", r"household|домохозяйств", r"income|доход"), ()),
    "road-paved-share": ((r"road|дорог", r"share|удельный вес|доля", r"paved|hard surface|тверд"), (r"density|густота",)),
    "road-density": ((r"road|дорог", r"density|густота|плотност"), ()),
    "grain-area": ((r"grain|зерн", r"area|площад"), (r"yield|урожайност",)),
    "grain-yield": ((r"grain|зерн", r"yield|урожайност"), ()),
    "population": ((r"population|населен",), (r"birth|death|mortality|migration|growth|density|change|рождаем|родив|умер|смертн|мигра|прирост|убыль|изменение|плотност",)),
    "saving-rate": ((r"saving|сбережен", r"rate|ratio|норма"), (r"volume|amount|объем",)),
    "university-students": ((r"student|студент", r"university|higher|высшего"), (r"vocational|профессионального",)),
    "vocational-students": ((r"student|студент", r"vocational|профессиональн|specialist training|программам подготовки"), (r"preschool|дошкольн",)),
    "rent-index": ((r"rent|аренд", r"index|индекс|cpi"), ()),
    "pension-real": ((r"pension|пенси", r"real|реальн"), (r"nominal|номинальн",)),
    "pension": ((r"pension|пенси", r"average|amount|assigned|size|средн|размер|назначен"),
        (r"number of.*pension|численност.*пенси|число.*пенси",)),
    "auto-loan-rate": ((r"auto|car|авто", r"loan|credit|кредит", r"rate|ставк"), ()),
    "gas-price": ((r"gas|газ",), (r"extraction|добыч|production|производств|consumption|потреблен|imports|импорт|exports|экспорт",)),
    "housing-price": ((r"price|цен|стоим", r"housing|house|dwelling|жиль|квартир"), ()),
    "housing-completions": ((r"complet|ввод|введен", r"housing|dwelling|residential|homes|жиль|жил.*дом|квартир"), ()),
    "building-permits": ((r"permit|разрешен", r"building|construction|строительств"), (r"trade|торговлю",)),
    "external-debt": ((r"external|внешн", r"debt|долг", r"public|government|государств"), (r"private|corporate|корпоративн",)),
    "rent": ((r"rent|аренд", r"housing|house|dwelling|residential|жиль|жил.*дом|квартир"), (r"land rental|аренд.*земл",)),
    "births": ((r"birth|родив|рождаем",), (r"country of birth|страны рождения|стране рождения",)),
    "mortality": ((r"death|mortality|смертност|умерш",), ()),
    "labour-productivity": ((r"productivity|производительность труда",), (r"capacity|мощност",)),
    "household-consumption": ((r"household|personal|домашних хозяйств", r"consumption|потреблен"), (r"government consumption|государствен.*потреблен",)),
    "capital-investment": ((r"fixed capital|основной капитал",), ()),
    "capital-formation": ((r"gross capital formation|валовое накопление капитала",), (r"gross fixed capital",)),
    "wages-nominal": ((r"wage|salary|earnings|заработн|зарплат",), (r"real wage|реальн.*заработн|wages real",)),
    "grain-harvest": ((r"grain|зерн", r"harvest|сбор"), (r"price|цен",)),
    "household-deposits": ((r"deposit|вклад|депозит", r"household|personal|населен|физическ"), (r"corporate|корпоративн|организац",)),
    "tourism": ((r"arrival|прибыт|приезд|число.*турист|численност.*турист",), (r"gdp|ввп",)),
    "wages-real": ((r"real wage|реальн.*заработн|wages real",), (r"nominal|номинальн",)),
    "median-wage": ((r"median|медиан",), ()),
    "gdp-nominal": ((r"gdp|gross domestic product|ввп|валов.*внутренн.*продукт", r"nominal|current prices|current dollars|текущих ценах|текущие цены"),
        (r"real gdp|constant prices|constant dollars|постоянн.*цен|gdp deflator|дефлятор|purchasing power parity|ppp",)),
    "gdp-real": ((r"gdp|gross domestic product|ввп|валов.*внутренн.*продукт", r"real|constant prices|volume|growth|change|физическ|рост"), (r"current prices|current dollars|текущих ценах|текущие цены|nominal|номинальн",)),
    "consumer-credit": ((r"consumer|потребительск", r"credit|loan|кредит"), (r"mortgage|ипотеч",)),
    "gdp-ppp": ((r"purchasing power parity|паритет.*покупатель|ppp",), ()),
    "gdp-deflator": ((r"deflator|дефлятор",), ()),
    "government-debt": ((r"government debt|public debt|государствен.*долг",), ()),
    "mortgage-rate": ((r"rate|ставк", r"mortgage|ипотеч"), ()),
    "mortgage-volume": ((r"volume|amount|value|объем|выдан|originations", r"mortgage|ипотеч"), ()),
    "credit-rate": ((r"rate|ставк", r"loan|lending|кредит"), (r"deposit|вклад|депозит",)),
    "electricity-generation": ((r"generation|выработ|производств", r"electric|электро"), (r"capacity|мощност|price|цен",)),
    "electricity-price": ((r"price|цен|тариф", r"electric|электро"), ()),
    "car-production": ((r"production|manufactur|производств|выпуск", r"car|vehicle|автомобил"), ()),
    "car-sales": ((r"sales|продаж", r"car|vehicle|автомобил"), ()),
}

# The same valuation may be declared in native currency-code units, e.g.
# constant-2017-USD or RUB at current prices. Plain alternation keeps parity
# with the hermetic SQL grammar; native unit witnesses remain scoped to these
# two descriptors and never establish another subject or denomination.
_VALUATION_CURRENCIES = ("usd", "eur", "rub", "cad", "aud", "gbp", "jpy", "cny",
    "dollar", "euro", "ruble", "rouble", "pound", "yen", "yuan", "доллар", "евро", "руб", "фунт", "йен", "иен", "юан")
VALUATION_UNIT_RULES = {}
for _valuation_key, _valuation_words in (("current-prices", ("current", "текущ")), ("constant-prices", ("constant", "постоянн"))):
    _required, _excluded = MEASURE_RULES[_valuation_key]
    _currency_pattern = "|".join(word + ".*" + currency for word in _valuation_words for currency in _VALUATION_CURRENCIES)
    VALUATION_UNIT_RULES[_valuation_key] = ((_required[0] + "|" + _currency_pattern,), ())
for _valuation_key in VALUATION_UNIT_RULES:
    _opposite_key = "constant-prices" if _valuation_key == "current-prices" else "current-prices"
    VALUATION_UNIT_RULES[_valuation_key] = (VALUATION_UNIT_RULES[_valuation_key][0],
        (MEASURE_RULES[_valuation_key][1][0] + "|" + VALUATION_UNIT_RULES[_opposite_key][0][0],))


def measure_matches(terms: tuple[tuple[str, ...], ...], *, code: str, names: tuple[str, ...],
        unit_names: tuple[str, ...] = ()) -> bool:
    """Every recognised typed economic measure must hold in its title/identity."""
    labels = tuple((name or "").casefold().replace("ё", "е").replace("-", " ") for name in (code, *names))
    units = tuple((name or "").casefold().replace("ё", "е").replace("-", " ") for name in unit_names)
    text = " ".join(labels)
    for alternatives in terms:
        rule = MEASURE_RULES.get(alternatives[0])
        if rule:
            required, excluded = rule
            if alternatives[0] in VALUATION_UNIT_RULES:
                # One complete native label witnesses valuation in its own
                # namespace. Currency-only units cannot finish a title such
                # as Current transfers, and separate unit fields cannot join.
                unit_required, unit_excluded = VALUATION_UNIT_RULES[alternatives[0]]
                title_match = any(all(re.search(pattern, label) for pattern in required) for label in labels)
                unit_match = any(all(re.search(pattern, unit) for pattern in unit_required) for unit in units)
                if (not (title_match or unit_match)
                        or any(re.search(pattern, label) for pattern in excluded for label in labels)
                        or any(re.search(pattern, unit) for pattern in unit_excluded for unit in units)):
                    return False
            elif not all(re.search(pattern, text) for pattern in required) or any(re.search(pattern, text) for pattern in excluded):
                return False
    return True


def title_frequencies(terms: tuple[tuple[str, ...], ...], candidates: list[dict]) -> Counter[str]:
    """Compute title document frequencies once for this bounded candidate set."""
    frequencies: Counter[str] = Counter()
    for candidate in candidates:
        candidate_title = " ".join(str(candidate.get(key) or "") for key in ("name_ru", "name_en")).casefold().replace("ё", "е")
        frequencies.update({alt for group in terms for alt in group if alt in candidate_title})
    return frequencies


def relevance_bonus(terms: tuple[tuple[str, ...], ...], *, names: tuple[str, ...],
        frequencies: Counter[str], count: int) -> int:
    """Candidate-set inverse document frequency rewards concise subject titles.

    This is a small tie-breaking component, not corpus BM25 or a probability. It
    cannot resurrect a candidate rejected by a required facet or measure guard.
    """
    title = " ".join(name or "" for name in names).casefold().replace("ё", "е")
    n = max(count, 1)
    score = 0.0
    for alternatives in terms:
        if alternatives[0].startswith("search-"):
            continue
        hits = [alt for alt in alternatives if alt in title]
        if hits:
            score += max(math.log1p((n + 1) / (frequencies[alt] + 1)) for alt in hits) * 6
    # Additional semicolon slices tend to be demographic/sector subdivisions;
    # broad intent prefers the explicitly aggregated title. Specific words remain
    # mandatory and therefore cannot be overridden by this small penalty.
    return round(score) - min(title.count(";") * 2, 16)
