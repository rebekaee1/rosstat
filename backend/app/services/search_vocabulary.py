"""Economic subjects and compositional wording, independent of visitor history.

These are bilingual measure/facet definitions. They never identify a destination
or relax an unknown qualifier. Longer compound subjects win over their parts.
"""
from __future__ import annotations
import re

# A comparison window and the observation frequency are independent required
# facets. Replacing the whole relation with two ordinary phrases lets the
# existing longest-alias parser create two AND groups, never one OR group.
TEMPORAL_ROLE_REWRITES = (
    (("end of each year", "end of the year", "end of year", "конец года"), "end period annual"),
    (("end of each quarter", "end of the quarter", "end of quarter", "конец квартала"), "end period quarterly"),
    (("end of each month", "end of the month", "end of month", "конец месяца"), "end period monthly"),
    (("относительно предыдущего года", "к соответствующему периоду предыдущего года",
      "к предыдущему году", "к прошлому году", "against the same period a year earlier"), "year on year"),
    (("same quarter of the previous year", "same quarter last year", "same quarter a year earlier",
      "тот же квартал прошлого года", "тому же кварталу прошлого года", "аналогичному кварталу прошлого года"), "year on year quarterly"),
    (("same month of the previous year", "same month last year", "same month a year earlier",
      "тот же месяц прошлого года", "тому же месяцу прошлого года", "аналогичному месяцу прошлого года"), "year on year monthly"),
    (("over the previous month", "over previous month", "compared with the previous month", "compared to the previous month",
      "previous month", "к предыдущему месяцу", "по сравнению с предыдущим месяцем"), "period on period monthly"),
    (("over the previous quarter", "over previous quarter", "compared with the previous quarter", "compared to the previous quarter",
      "previous quarter", "к предыдущему кварталу", "по сравнению с предыдущим кварталом"), "period on period quarterly"),
    (("average over the quarter", "quarter average", "average quarter", "quarterly average",
      "средняя за квартал", "среднее за квартал", "в среднем за квартал"), "average quarterly"),
)


def prepare_temporal_roles(text: str) -> str:
    """Rewrite complete relative windows, preserving absolute dates and tails.

    The caller extracts actual dates first. Bare calendar nouns, Q1, numbers,
    unknown periods and plain year-on-year are deliberately untouched here.
    """
    aliases = sorted(((alias, replacement) for phrases, replacement in TEMPORAL_ROLE_REWRITES
        for alias in phrases), key=lambda row: len(row[0]), reverse=True)
    for alias, replacement in aliases:
        pattern = r"(?<!\w)" + re.escape(alias) + r"(?!\w)"
        if replacement.startswith(("year on year", "period on period")):
            # In this complete comparison clause, change is represented by the
            # required mode. A standalone change or an unknown window survives.
            text = re.sub(r"(?<!\w)change from (?:the )?" +
                re.escape(alias) + r"(?!\w)", replacement, text)
        text = re.sub(pattern, replacement, text)
    # Source methodology and the stored observation frequency are independent.
    # Only complete source clauses gain a role; plain monthly observations stay
    # ordinary observation-frequency wording. The source requirement is never
    # silently removed when a provider has no registered source contract.
    frequencies = ("annual", "quarterly", "monthly", "weekly", "daily")
    for frequency in frequencies:
        text = re.sub(r"\b(?:from (?:the )?" + frequency + r" source series|estimated from (?:the )?" +
            frequency + r" observations)\b", frequency + " source frequency", text)
    text = re.sub(r"\b(change|изменение)\s+(year on year|period on period)\b", r"\2", text)
    text = re.sub(r"\b(year on year|period on period)\s+(change|изменение)\b", r"\1", text)
    return text


VOCABULARY_CONCEPTS = (
    (("end period", "end of period", "eop", "на конец периода"), ("search-mode-eop",)),
    *(((frequency + " source frequency",), ("search-source-freq-" + frequency,))
        for frequency in ("annual", "quarterly", "monthly", "weekly", "daily")),
    (("earnings contribution to income change", "earnings contributions to income change", "вклад заработков в изменение дохода", "вклад заработков в изменение доходов"),
        ("earnings-income-contribution", "earnings contributions to income change", "earnings contribution to income change", "вклад заработков в изменение дохода", "вклад заработков в изменение доходов")),
    (("contributions to consumption change", "contribution to consumption change", "вклад категорий в изменение потребления", "вклад в изменение потребления"),
        ("consumption-change-contribution", "contributions to consumption change", "contribution to consumption change", "вклад категорий в изменение потребления", "вклад в изменение потребления")),
    (("farm earnings", "earnings of farms", "фермерские заработки", "заработки фермерских хозяйств", "заработки в фермерских хозяйствах"),
        ("farm-earnings", "farm earnings", "фермерские заработки", "заработки в фермерских", "заработки фермерских")),
    (("employee compensation by industry", "оплата труда работников", "оплата труда по отраслям"),
        ("employee-compensation", "employee compensation", "compensation of employees", "оплата труда")),
    (("daily internet use", "daily use of the internet", "use of the internet every day", "ежедневное использование интернета", "ежедневно пользуются интернетом", "интернетом каждый день"),
        ("internet-daily-use", "daily internet use", "daily use of the internet", "frequently using the internet", "часто пользующегося интернетом", "ежедневное использование интернета")),
    (("cannot afford small weekly personal spending", "недоступны небольшие еженедельные траты на себя"),
        ("deprivation-weekly-spending", "cannot afford small weekly personal spending", "cannot afford a small amount of money to spend each week", "недоступны небольшие еженедельные траты на себя")),
    (("household credit outstanding", "household loans outstanding", "consumer credit outstanding", "кредиты физическим лицам", "задолженность физических лиц по кредитам"), ("credit-stock-households", "consumer credit outstanding", "household credit outstanding", "household loans outstanding", "outstanding loans to households", "кредиты физическим лицам", "задолженность физических лиц")),
    (("business credit outstanding", "business loans outstanding", "кредиты бизнесу", "задолженность бизнеса по кредитам"), ("credit-stock-business", "business credit outstanding", "business loans outstanding", "loans outstanding to businesses", "кредиты бизнесу", "задолженность бизнеса")),
    (("legal entity borrowers", "legal entities", "юридическим лицам", "юридических лиц"), ("borrower-legal-entities", "legal entities", "legal entity", "corporate", "юридическ")),
    (("corporate loan rate", "corporate loan rates"), ("credit-rate", "corporate loan rate", "interest rates on loans", "ставка по кредитам юридическим лицам")),
    (("research and development personnel", "r d personnel", "персонал нир", "персонал ниокр"), ("research-personnel", "research and development personnel", "r d personnel", "персонал нир", "персонал ниокр")),
    (("research and development organizations", "r d organizations", "число организаций нир", "число организаций ниокр"), ("research-organizations", "research and development organizations", "r d organizations", "организаций нир", "организаций ниокр")),
    (("monetary base", "денежная база", "денежной базы"), ("monetary-base", "monetary base", "денежная база", "денежной базы")),
    (("central bank assets", "активы центрального банка", "активы центробанка"), ("central-bank-assets", "central bank assets", "assets of all federal reserve banks", "активы центрального банка", "баланс федеральной резервной системы")),
    (("коэффициент рождаемости", "коэффициента рождаемости", "crude birth rate"), ("birth-rate", "birth rate", "коэффициент рождаемости")),
    (("коэффициент смертности", "коэффициента смертности", "crude death rate"), ("death-rate", "death rate", "коэффициент смертности")),
    (("medicare benefits", "medicare benefit", "medicare"), ("benefits-medicare", "medicare", "медикэр", "медикер")),
    (("medicaid benefits", "medicaid benefit", "medicaid", "медикейд"), ("benefits-medicaid", "medicaid", "медикейд")),
    (("supplemental nutrition assistance program", "продовольственная помощь snap", "snap benefits", "snap"), ("benefits-snap", "supplemental nutrition assistance program", "snap", "продовольственная помощь малоимущим")),
    (("social security benefits", "social security benefit", "выплаты по социальному обеспечению"), ("benefits-social-security", "social security benefits", "выплаты по социальному обеспечению")),
    (("railroad retirement and disability benefits", "пособия по пенсии и инвалидности железнодорожникам"), ("benefits-railroad", "railroad retirement and disability benefits", "пособия по пенсии и инвалидности железнодорожникам")),
    (("workers compensation benefits", "workers compensation", "страховые выплаты работникам при производственных травмах"), ("benefits-workers-compensation", "workers compensation", "страховые выплаты работникам при производственных травмах")),
    (("income maintenance benefits", "пособия по поддержанию дохода", "пособия по поддержанию доходов"), ("benefits-income-maintenance", "income maintenance benefits", "пособия по поддержанию дохода")),
    (("veterans pension and disability benefits", "пенсии и пособия по инвалидности ветеранам"), ("benefits-veterans", "veterans pension and disability benefits", "пенсии и пособия по инвалидности ветеранам")),
    (("education and training assistance", "помощь в получении образования и профессиональной подготовке"), ("benefits-education-training", "education and training assistance", "помощь в получении образования и профессиональной подготовке")),
    (("additional child tax credit", "дополнительный налоговый кредит на ребенка"), ("benefits-child-tax-credit", "additional child tax credit", "дополнительный налоговый кредит на ребенка")),
    (("current transfer receipts of individuals from businesses", "текущие выплаты населению от бизнеса"), ("transfers-business-to-persons", "current transfer receipts of individuals from businesses", "текущие выплаты населению от бизнеса")),
    (("wage and salary employment", "wage and salary jobs", "число наемных работников"), ("wage-salary-employment", "wage and salary employment", "число наемных работников")),
    (("net earnings", "чистый трудовой доход", "чистого трудового дохода"), ("net-earnings", "net earnings", "чистый доход", "чистого трудового дохода")),
    (("employee compensation", "compensation of employees", "оплата труда наемных работников"), ("employee-compensation", "compensation of employees", "employee compensation", "оплата труда")),
    (("dividends interest and rent", "дивиденды проценты и рента", "дивиденды процентные и арендные доходы"), ("dividend-interest-rent-income", "dividends interest and rent", "дивиденды процентные и арендные доходы")),
    (("валовой внутренний продукт", "gross domestic product"), ("gdp", "gdp", "ввп", "валовой внутренний продукт", "gross domestic product")),
    (("индекс потребительских цен", "consumer price index"), ("cpi", "cpi", "потребительских цен", "consumer price", "hicp")),
    (("плотность населения", "population density"), ("population-density", "population density", "плотность населения")),
    (("жилье", "housing"), ("housing", "housing", "жиль", "жилых домов")),
    (("рабочая сила", "рабочую силу", "labour force", "labor force"), ("labour-force", "labor force", "labour force", "рабочая сила")),
    (("наличные в обращении", "cash in circulation", "наличных денег в обращении"), ("currency-circulation", "m0", "currency in circulation", "cash in circulation", "наличн")),
    (("строительные работы", "объем строительных работ", "construction work", "construction work volume"), ("construction-work", "construction work", "construction volume", "объем работ", "строительства")),
    (("сальдо текущего счета", "текущий счет", "current account balance", "current account"), ("current-account", "current account", "текущего счета", "текущий счет")),
    (("естественный прирост населения", "natural population change", "natural increase"), ("natural-change", "natural increase", "natural population", "естественный прирост")),
    (("государственное потребление", "government consumption"), ("government-consumption", "government consumption", "государственное потребление", "потребление государственного управления")),
    (("расходы бюджета", "бюджетные расходы", "budget expenditure", "government budget spending"), ("budget-spending", "budget expenditure", "расходы", "budget spending")),
    (("к предыдущему году", "к прошлому году"), ("search-mode-yoy",)),
    (("доходы федерального бюджета", "budget revenue", "доходы бюджета"), ("budget-revenue", "budget revenue", "доходы федерального бюджета", "доходы бюджета")),
    (("экспорт услуг", "продажа услуг за границу", "services exports", "exports of services"), ("services-exports", "services exports", "exports of services", "экспорт услуг")),
    (("внешний долг", "foreign debt"), ("total-external-debt", "external debt", "foreign debt", "внешний долг")),
    (("число родившихся", "число рождений", "number of births"), ("birth-count", "births", "number of births", "родившихся")),
    (("auto loan interest rate", "ставка по автокредитам"), ("auto-loan-rate", "auto loan", "автокредит")),
    (("часовая заработная плата", "hourly earnings", "hourly pay", "hourly wages"), ("hourly-earnings", "hourly earnings", "hourly pay", "hourly wage", "часов")),
    (("норма сбережений", "сбережения доля доходов", "personal saving rate", "saving rate"), ("saving-rate", "saving rate", "сбережений", "saving ratio")),
    (("незаполненные рабочие места", "вакантные рабочие места"), ("vacancies", "vacancies", "job openings", "ваканс")),
    (("цены аренды жилья", "rent price index", "rent index"), ("rent-index", "rent", "аренды жилья")),
    (("уровень занятости", "employment rate", "employment population ratio"), ("employment-rate", "employment rate", "employment population", "уровень занятости")),
    (("число безработных", "численность безработных", "unemployed persons", "unemployment count"), ("unemployment-count", "unemployment level", "unemployment count", "unemployed", "численность безработных")),
    (("медианный доход домохозяйства", "median household income"), ("median-household-income", "median household income", "медианный доход")),
    (("личный доход на душу", "personal income per capita"), ("personal-income-capita", "per capita personal income", "personal income per capita", "личный доход на душу")),
    (("доля жилья собственников", "homeownership", "owner occupied housing"), ("homeownership", "homeownership", "owner occupied", "собственник")),
    (("численность пенсионеров", "число пенсионеров", "pensioners"), ("pensioners", "pensioners", "пенсионеров")),
    (("средняя назначенная пенсия", "average assigned pension", "average pension"), ("pension", "pension", "пенси")),
    (("реальный размер назначенных пенсий", "real pension"), ("pension-real", "real pension", "реальный размер", "пенси")),
    (("студенты вузов", "студентов вузов", "university students"), ("university-students", "higher education", "university students", "образовательных программам высшего", "студентов")),
    (("студенты профессиональных программ", "secondary vocational students"), ("vocational-students", "secondary vocational", "среднего профессионального", "программам подготовки")),
    (("площадь зерновых", "посевная площадь зерновых", "grain sown area"), ("grain-area", "sown area", "посевная площадь", "посевные площади")),
    (("урожайность зерна", "grain yield"), ("grain-yield", "grain yield", "урожайность зерновых")),
    (("доля дорог с твердым покрытием", "paved public roads share"), ("road-paved-share", "share", "удельный вес", "hard surface", "твердым покрытием")),
    (("плотность дорог с твердым покрытием", "surfaced public road density"), ("road-density", "density", "густота", "плотность")),
    (("manufacturing shipments", "отгрузки обрабатывающей промышленности"), ("manufacturing-shipments", "manufacturing sales", "manufacturing shipments", "отгрузк")),
    (("core pce price index", "базовый индекс цен pce"), ("core-pce", "core pce", "excluding food and energy", "без продуктов питания и энергии")),
    (("monthly", "помесячно", "по месяцам", "ежемесячно", "месячный", "месячная", "месячное", "месячные", "месячных", "месячную", "ежемесячный", "ежемесячная", "ежемесячные", "ежемесячных"), ("search-freq-monthly",)),
    (("quarterly", "по кварталам", "квартальная", "квартальный", "квартальное", "квартальные", "квартальных", "квартальную", "ежеквартально", "ежеквартальная", "ежеквартальные", "each quarter"), ("search-freq-quarterly",)),
    (("annual", "annually", "yearly", "по годам", "ежегодно", "годовой", "годовая", "годовое", "годовые", "годовых", "годовую", "годовым", "годовому", "годовом", "ежегодный", "ежегодная", "ежегодные", "ежегодных", "each year"), ("search-freq-annual",)),
    (("weekly", "по неделям", "еженедельно", "еженедельный", "еженедельная", "каждую неделю", "each week"), ("search-freq-weekly",)),
    (("daily", "по дням", "ежедневно", "ежедневный", "ежедневная", "ежедневные", "каждый день", "each day"), ("search-freq-daily",)),
    (("private", "частный", "частных", "частные"), ("private", "private", "частн")),
    (("government", "государственный", "государственных", "государственные"), ("government", "government", "государств")),
    (("federal", "федеральный", "федерального"), ("federal", "federal", "федеральн")),
    (("current prices", "текущих ценах"), ("current-prices", "current prices", "current dollars", "текущих ценах", "текущие цены", "текущих долларах", "nominal")),
    (("constant prices", "постоянных ценах"), ("constant-prices", "constant prices", "constant dollars", "постоянных ценах", "real")),
)

GRAMMAR_WORDS = frozenset("""
какова каков какой находится находилось входят входит
показывает покажите данные changing changes changed across
large big each take programmes programme earn earns getting gets
""".split())


def prepare_subject_roles(text: str) -> str:
    """Compose a known economic subject and role without dropping qualifiers.

    Only words that express the recognised relationship are consumed. A stock
    of loans is different from a lending rate, research personnel from research
    organisations, and a benefit programme from food prices or bank lending.
    Explicit amounts become the existing native monetary-unit requirement.
    """
    words = text.split()

    def has(pattern: str) -> bool:
        return any(re.fullmatch(pattern, word) for word in words)

    def consume(patterns: tuple[str, ...], replacement: str) -> str:
        return replacement + " " + " ".join(word for word in words
            if not any(re.fullmatch(pattern, word) for pattern in patterns))

    # A contribution is a part of a change in another measure, never a bank
    # deposit. Only the recognised subject/relation is consumed; industry,
    # net/gross and denominator qualifiers stay required.
    contribution = has(r"contributions?|contribut(?:e|es|ed|ing)|вклад.*")
    change = has(r"changes?|changing|изменени.*")
    if contribution and has(r"gdp|ввп") and has(r"growth|рост.*"):
        # The verb expresses the same contribution relation as the noun. GDP
        # growth, its sector, and explicit percentage-point units remain facets.
        words = ["contribution" if re.fullmatch(r"contribut(?:e|es|ed|ing)", word)
            else word for word in words]
        text = " ".join(words)
    if contribution and change and has(r"earnings|заработк.*") and has(r"income|доход.*"):
        return consume((r"contributions?|contribut(?:e|es|ed|ing)|вклад.*", r"changes?|changing|изменени.*",
            r"earnings|заработк.*", r"income|доход.*", r"внес(?:ли|ла|ло|ен|ена)|внос(?:ят|ит)"), "earnings contribution to income change")
    if contribution and change and has(r"consumption|потреблени.*"):
        return consume((r"contributions?|contribut(?:e|es|ed|ing)|вклад.*", r"changes?|changing|изменени.*",
            r"consumption|потреблени.*", r"categories|категори.*", r"внес(?:ли|ла|ло|ен|ена)|внос(?:ят|ит)"), "contribution to consumption change")

    # Farm earnings include proprietors' earnings; employee compensation also
    # includes supplements. Neither compound means an average nominal salary.
    if has(r"farm|farms|фермерск.*") and has(r"earnings|заработк.*"):
        return consume((r"farm|farms|фермерск.*", r"earnings|заработк.*", r"хозяйств.*"), "farm earnings")
    compensation = has(r"compensation") and has(r"employees?|employee")
    russian_compensation = has(r"оплат.*") and has(r"труда") and has(r"работник.*|наемн.*")
    if (compensation or russian_compensation) and not has(r"salary|salaries|wages?|заработн.*|зарплат.*"):
        return consume((r"compensation|employees?|employee", r"оплат.*|труда|работник.*|наемн.*"),
            "employee compensation")

    # A weekly expense item is part of the deprivation definition. Negative
    # polarity is explicit; a positive ability to afford spending is different.
    weekly = has(r"weekly|еженедельн.*") or (has(r"each|every") and has(r"week"))
    spending = has(r"spending|spend|трат.*")
    small = has(r"small|little|небольш.*")
    negative_span = re.search(r"(?<!\w)(?:cannot afford|не (?:могу|могут|может|мог|могла|могли) позволить|недоступн[а-я]*)(?!\w)", text)
    personal = has(r"personal|themselves|себе|себя")
    if weekly and spending and small and negative_span and personal:
        # Consume the matched negation and complete each-week span only. A
        # second negation or an each/every subset elsewhere stays mandatory.
        remainder = text[:negative_span.start()] + " " + text[negative_span.end():]
        remainder = re.sub(r"(?<!\w)(?:each|every) week(?!\w)", "weekly", remainder, count=1)
        patterns = (r"weekly|еженедельн.*", r"spending|spend|трат.*",
            r"small|little|небольш.*", r"personal|themselves|себе|себя")
        return "cannot afford small weekly personal spending " + " ".join(word for word in remainder.split()
            if not any(re.fullmatch(pattern, word) for pattern in patterns))

    credit = has(r"credits?|loans?|lending|кредит.*|заем.*|займ.*")
    stock = has(r"outstanding|balance|balances|задолженност.*|остат.*")
    rate = has(r"rates?|interest|ставк.*|процентн.*")
    household = has(r"individuals?|households?|физическ.*")
    legal_entities = has(r"юридическ.*|corporate") or (has(r"legal") and has(r"entities|entity"))
    business = has(r"businesses|business|corporate|юридическ.*") or legal_entities
    if credit and rate and legal_entities and not household:
        return consume((r"credits?|loans?|lending|кредит.*|заем.*|займ.*",
            r"rates?|interest|ставк.*|процентн.*", r"legal|entities|entity|corporate|юридическ.*|лиц.*",
            r"banks?|банковск.*"), "corporate loan rate legal entity borrowers")
    if credit and stock and not rate and household != business:
        sector = r"individuals?|households?|физическ.*|лиц.*" if household else r"businesses|business|corporate|юридическ.*|лиц.*"
        replacement = "household credit outstanding" if household else "business credit outstanding"
        if legal_entities:
            replacement += " legal entity borrowers"
            sector += r"|legal|entities|entity"
        return consume((r"credits?|loans?|lending|кредит.*|заем.*|займ.*",
            r"outstanding|balance|balances|задолженност.*|остат.*", sector,
            r"banks?|банковск.*"), replacement)

    research = (has(r"нир|ниокр") or
        (has(r"research|исследован.*") and has(r"development|разработ.*|научн.*")) or
        (has(r"r") and has(r"d")))
    personnel = has(r"personnel|staff|people|persons?|headcount|персонал.*|сотрудник.*|люд.*")
    organizations = has(r"organizations?|organisations?|institutions?|организац.*|учреждени.*")
    if research and personnel != organizations:
        role = r"personnel|staff|people|persons?|headcount|персонал.*|сотрудник.*|люд.*" if personnel else r"organizations?|organisations?|institutions?|организац.*|учреждени.*"
        return consume((r"research|development|научн.*|исследован.*|разработ.*|нир|ниокр|r|d", role,
            r"perform|performs|performing|выполня.*"),
            "research and development personnel" if personnel else "research and development organizations")

    # Programme identifiers are ordinary public domain vocabulary. They never
    # encode a native series, geographic destination or an observed visitor query.
    programme = None
    if has(r"snap"):
        programme = ("supplemental nutrition assistance program",
            (r"snap|продовольственн.*|помощ.*|supplemental|nutrition|assistance|program(?:me)?s?",))
        if has(r"assistance|benefits?") and not has(r"prices?|inflation|index|цен.*|инфляц.*"):
            programme = (programme[0], programme[1] + (r"food",))
    elif has(r"medicare|медикэр|медикер"):
        programme = ("medicare benefits", (r"medicare|медикэр|медикер|benefits?",))
    elif has(r"medicaid|медикейд"):
        programme = ("medicaid benefits", (r"medicaid|медикейд|benefits?",))
    elif has(r"social") and has(r"security") and has(r"benefits?"):
        programme = ("social security benefits", (r"social|security|benefits?",))
    elif has(r"railroad|железнодорожн.*") and has(r"retirement|пенси.*") and has(r"disability|инвалидност.*"):
        programme = ("railroad retirement and disability benefits",
            (r"railroad|железнодорожн.*|retirement|пенси.*|disability|инвалидност.*|benefits?|пособи.*",))
    elif has(r"workers") and has(r"compensation"):
        programme = ("workers compensation benefits", (r"workers|compensation|benefits?",))
    elif has(r"income|доход.*") and has(r"maintenance|поддержани.*") and has(r"benefits?|пособи.*"):
        programme = ("income maintenance benefits", (r"income|доход.*|maintenance|поддержани.*|benefits?|пособи.*",))
    elif has(r"veterans?|ветеран.*") and has(r"pensions?|пенси.*") and has(r"disability|инвалидност.*"):
        programme = ("veterans pension and disability benefits",
            (r"veterans?|ветеран.*|pensions?|пенси.*|disability|инвалидност.*|benefits?|пособи.*",))
    elif has(r"education") and has(r"training") and has(r"assistance"):
        programme = ("education and training assistance", (r"education|training|assistance",))
    if programme:
        replacement, patterns = programme
        explicit_money = has(r"amount|amounts|money|сумм.*|денег|деньги")
        payment = has(r"payments?|выплат.*")
        counted_payments = has(r"number|count|many|число|количество|сколько|численност.*")
        if explicit_money or (payment and not counted_payments):
            replacement += " monetary value"
            patterns += (r"amount|amounts|money|payments?|сумм.*|денег|деньги|выплат.*",)
        return consume(patterns, replacement)
    return text


def prepare_vocabulary(text: str) -> str:
    """Resolve recognised subject/relationship roles; preserve remaining words."""
    text = prepare_subject_roles(text)
    words = text.split()
    def has(pattern):
        return any(re.fullmatch(pattern, word) for word in words)
    def consume(patterns, replacement):
        return replacement + " " + " ".join(word for word in words if not any(re.fullmatch(p, word) for p in patterns))
    if has(r"gdp|ввп"):
        # These verbs ask for the amount produced; they are grammar only next
        # to an explicit GDP measure. They remain meaningful elsewhere.
        words = [word for word in words if not re.fullmatch(r"generat(?:e|es|ed|ing)", word)]
        text = " ".join(words)
    if has(r"ввп|gdp|продукт|product|economy|экономик.*") and (has(r"текущ.*|current|nominal") or has(r"постоянн.*|constant|real")):
        current = has(r"текущ.*|current|nominal")
        constant = has(r"постоянн.*|constant|real")
        per_capita = re.search(r"\b(?:per capita|на душу(?: населения)?)\b", text)
        if per_capita:
            # Per capita is the measure; valuation is an independent mandatory
            # descriptor. A current-price qualifier cannot erase its denominator.
            words = (text[:per_capita.start()] + " " + text[per_capita.end():]).split()
            replacement = "gdp per capita"
            if current:
                replacement += " current prices"
            if constant:
                replacement += " constant prices"
        elif current and constant:
            # Contradictory valuations remain two AND constraints, never choose
            # one silently because its branch happens to run first.
            replacement = "gdp current prices constant prices"
        else:
            replacement = "real gdp" if constant else "nominal gdp"
        return consume((r"ввп|gdp|продукт|product|economy|экономик.*|gross|domestic|валов.*|внутренн.*", r"текущ.*|current|nominal|постоянн.*|constant|real", r"ценах|цен|prices?"), replacement)
    if has(r"международн.*|international") and has(r"резерв.*|reserves?"):
        return consume((r"международн.*|international", r"резерв.*|reserves?"), "international reserves")
    if has(r"наличн.*|cash") and has(r"обращени.*|circulation"):
        return consume((r"наличн.*|cash", r"обращени.*|circulation", r"денег|money|находит.*"), "cash in circulation")
    if has(r"вклад.*|deposit.*") and has(r"держ.*|hold.*|households?|people|россияне|населен.*") and not has(r"ставк.*|rates?|interest|corporate|организац.*"):
        return consume((r"вклад.*|deposit.*", r"держ.*|hold.*|households?|people|россияне|населен.*", r"банковск.*|bank.*|денег|money|объем|объём"), "household deposits")
    if has(r"loan.*|автокредит.*|кредит.*") and has(r"cars?|auto|авто.*") and has(r"interest|rates?|ставк.*|процент.*"):
        return consume((r"loan.*|автокредит.*|кредит.*", r"cars?|auto|авто.*", r"interest|rates?|ставк.*|процент.*", r"households?|населен.*"), "auto loan interest rate")
    if has(r"government|государств.*") and has(r"budget|бюджет.*") and has(r"spend.*|расход.*"):
        return consume((r"government|государств.*", r"budget|бюджет.*", r"spend.*|расход.*"), "budget expenditure")
    if has(r"babies|born|родил.*|родив.*") and has(r"many|сколько|число|численность"):
        return consume((r"babies|born|родил.*|родив.*", r"many|сколько|число|численность"), "number of births")
    if has(r"hour|час.*") and has(r"earn.*|pay|paid|wages?|зарабатыва.*"):
        return consume((r"hour|час.*", r"earn.*|pay|paid|wages?|зарабатыва.*", r"employees?|работник.*|work|работ.*|one|один|companies|компани.*"), "hourly earnings")
    if has(r"сбережени.*|savings?") and has(r"доля|share|доход.*|income"):
        return consume((r"сбережени.*|savings?", r"доля|share|доход.*|income", r"остает.*|оста.*|remains?|left"), "personal saving rate")
    if has(r"jobs?|занят.*") and has(r"share|доля|rate"):
        return consume((r"jobs?|занят.*", r"share|доля|rate", r"working|age|residents?|работ.*|трудоспособн.*"), "employment rate")
    if has(r"jobs?|работают|work") and has(r"people|person.*|сколько|число"):
        return consume((r"jobs?|работают|work", r"people|person.*|сколько|число"), "employment count")
    if has(r"безработн.*|unemployed") and has(r"сколько|число|численность|many"):
        return consume((r"безработн.*|unemployed", r"сколько|число|численность|many", r"жител.*|people|person.*"), "unemployed persons")
    if has(r"безработн.*|unemployed") and has(r"доля|share|rate"):
        return consume((r"безработн.*|unemployed", r"доля|share|rate"), "unemployment rate")
    if has(r"пенсионер.*|pensioners?"):
        return consume((r"пенсионер.*|pensioners?", r"жив.*|live|lives"), "pensioners")
    if has(r"people|person.*|жител.*") and has(r"live|lives|жив.*"):
        return consume((r"people|person.*|жител.*", r"live|lives|жив.*"), "population")
    if has(r"housing|homes?|жиль.*") and has(r"prices?|cost|цен.*|стоим.*") and has(r"new|нов.*|existing|вторичн.*") and not has(r"рынке|market"):
        secondary = has(r"existing|вторичн.*")
        return consume((r"housing|homes?|жиль.*", r"prices?|cost|цен.*|стоим.*", r"new|нов.*|existing|вторичн.*", r"average|средн.*", r"square|metre|meter"), "average prices on secondary housing market" if secondary else "average prices on primary housing market")
    if has(r"students?|студент.*") and has(r"вуз.*|universit.*"):
        return consume((r"students?|студент.*", r"вуз.*|universit.*", r"учит.*|study|studies"), "university students")
    if has(r"зерн.*|grain") and has(r"засеян.*|sown|площад.*|area"):
        return consume((r"зерн.*|grain", r"засеян.*|sown|площад.*|area", r"земли|land"), "grain sown area")
    per_hectare = re.search(r"\b(?:per\s+(?:one\s+)?hectares?|(?:с|на)\s+(?:одного\s+|один\s+)?гектар[а-я]*)\b", text)
    if has(r"зерн.*|grain") and (has(r"yield|урожайност.*") or per_hectare):
        patterns = (r"зерн.*|grain", r"yield|урожайност.*", r"получа.*|get|gets")
        if per_hectare:
            words = (text[:per_hectare.start()] + " " + text[per_hectare.end():]).split()
        return consume(patterns, "grain yield")
    if has(r"roads?|дорог.*") and has(r"share|доля|удельный") and has(r"hard|surfaced|paved|тверд.*"):
        return consume((r"roads?|дорог.*", r"share|доля|удельный", r"hard|surfaced|paved|тверд.*", r"surface|public|покрыти.*|общего|пользования"), "paved public roads share")
    if has(r"roads?|дорог.*") and has(r"dense|density|плотност.*|густот.*"):
        return consume((r"roads?|дорог.*", r"dense|density|плотност.*|густот.*", r"surfaced|public|hard|surface|network|тверд.*|покрыти.*|общего|пользования"), "surfaced public road density")
    return text
