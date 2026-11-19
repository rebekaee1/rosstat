"""Банк России: максимальная ставка по вкладам 10 крупнейших банков и инфляционные ожидания населения (19.11.2026).

Спрос (боевая БД, 20.10–19.11.2026): страницу ставки по вкладам `deposit-rate` открыли как первую 179 человек,
фраз Яндекса про вклады — 180 человек («максимальная ставка по вкладам», «какие проценты по вкладам были в 2025»);
внутренний поиск «наблюдаемая инфляция vs ожидаемая инфляция» возвращал пусто. На сайте была только
средневзвешенная ставка по новым вкладам (помесячно, с опозданием на полтора месяца).

- `deposit-rate-max` — максимальная процентная ставка по вкладам в рублях десяти банков, привлекающих больше всего
  вкладов (`cbr.ru/statistics/avgprocstav/`): раз в декаду (1, 11 и 21-го числа), со II декады июля 2009 года.
  Частота карточки — `weekly`: ближайшая из поддерживаемых (семьи view-mode у ряда нет, только уровень; как карточка
  подписывает частоту, глазами не проверено 19.11.2026); порог свежести 14 дней подходит к ритму «раз в 10 дней».
- `inflation-expected`, `inflation-observed` — медианные оценки инфляции на год вперёд и за прошедший год из
  опроса населения «инФОМ» по заказу Банка России (`Infl_exp_YY-MM.xlsx`, лист «Данные за все годы»), с декабря
  2009 года; до 2014 года опрос шёл не каждый месяц.
- `consumer-sentiment` — индекс потребительских настроений из того же файла, пункты (100 — оптимистов и
  пессимистов поровну).

Ставки — проценты годовых, ожидания — проценты, индекс — пункты. Прогноз не строится: ряд опросов и ставок банков
зависит от решений Банка России, а не от собственной динамики.
"""

from __future__ import annotations

from dataclasses import dataclass

DEPOSIT_MAX_CODE = "deposit-rate-max"
DEPOSIT_MAX_URL = "https://www.cbr.ru/statistics/avgprocstav/"
DEPOSIT_MAX_FIRST = "01.07.2009"

EXPECTATIONS_PAGE = "https://www.cbr.ru/analytics/dkp/inflationary_expectations/"
EXPECTATIONS_SHEET = "Данные за все годы"


@dataclass(frozen=True)
class SurveySeries:
    section: str        # строка-заголовок блока в листе «Данные за все годы» (начало текста)
    label: str          # строка ряда (начало текста), первая после заголовка
    name: str
    name_en: str
    unit: str
    unit_en: str
    category: str
    description: str
    description_en: str
    keywords: str
    seo_title: str
    seo_description: str


SURVEY: dict[str, SurveySeries] = {
    "inflation-expected": SurveySeries(
        "Прямые оценки годовой инфляции: медианные значения", "ожидаемая инфляция (в %)",
        "Инфляционные ожидания населения", "Household inflation expectations", "%", "%", "Цены",
        "Какую инфляцию на ближайшие 12 месяцев ждут люди: медиана ответов в ежемесячном опросе населения по заказу "
        "Банка России. Половина опрошенных ждёт роста цен меньше этого числа, половина — больше.",
        "Inflation that people expect over the next 12 months: the median answer in the monthly household survey "
        "commissioned by the Bank of Russia. Half of respondents expect lower price growth, half expect higher.",
        "инфляционные ожидания, ожидаемая инфляция, ожидания инфляции населения, инфляционные ожидания населения, "
        "ожидания по инфляции, инФОМ, опрос Банка России, inflation expectations",
        "Инфляционные ожидания населения России — опрос Банка России по месяцам",
        "Ожидаемая инфляция на год вперёд по опросу населения для Банка России: медиана ответов по месяцам с 2009 "
        "года, в сравнении с наблюдаемой инфляцией.",
    ),
    "inflation-observed": SurveySeries(
        "Прямые оценки годовой инфляции: медианные значения", "наблюдаемая инфляция (в %)",
        "Наблюдаемая инфляция (оценка населения)", "Perceived inflation (household survey)", "%", "%", "Цены",
        "Насколько, по ощущениям людей, выросли цены за последние 12 месяцев: медиана ответов в ежемесячном опросе "
        "населения по заказу Банка России. Обычно она выше официальной инфляции Росстата.",
        "How much people feel prices have risen over the past 12 months: the median answer in the monthly household "
        "survey commissioned by the Bank of Russia. It is usually higher than the official inflation rate.",
        "наблюдаемая инфляция, ощущаемая инфляция, инфляция по ощущениям, оценка инфляции населением, "
        "наблюдаемая и ожидаемая инфляция, perceived inflation",
        "Наблюдаемая инфляция — как люди оценивают рост цен, опрос Банка России",
        "Наблюдаемая населением инфляция за прошедший год: медиана ответов в опросе для Банка России по месяцам с "
        "2009 года.",
    ),
    "consumer-sentiment": SurveySeries(
        "Индекс потребительских настроений", "индекс потребительских настроений (в пунктах)",
        "Индекс потребительских настроений", "Consumer sentiment index", "пункты", "points", "Бизнес",
        "Как люди оценивают своё материальное положение, экономику страны и время для крупных покупок — сводный "
        "индекс по опросу населения для Банка России. 100 пунктов — оптимистов и пессимистов поровну; выше — "
        "оптимистов больше.",
        "How people rate their own finances, the national economy and the timing of major purchases — a composite "
        "index from the household survey for the Bank of Russia. 100 means optimists and pessimists are balanced; "
        "above 100, optimists prevail.",
        "индекс потребительских настроений, потребительские настроения, потребительская уверенность, "
        "настроения населения, consumer sentiment",
        "Индекс потребительских настроений в России по месяцам — Банк России",
        "Индекс потребительских настроений населения России по опросу для Банка России, пункты, по месяцам с 2009 "
        "года.",
    ),
}

SURVEY_METHODOLOGY = (
    "Опрос проводит «инФОМ» по заказу Банка России каждый месяц: около 2 тысяч взрослых жителей "
    "разных регионов России. Людей спрашивают, насколько, по их мнению, выросли "
    "цены за год и насколько вырастут за следующий год; в ряд входит медиана ответов. Индекс потребительских "
    "настроений собран из ответов о личном положении, экономике страны и покупках. До 2014 года опрос "
    "проходил несколько раз в год, поэтому в начале ряда есть пропуски. Точка месяца — результат опроса в этом "
    "месяце; Банк России публикует его в конце месяца или в начале следующего."
)
SURVEY_METHODOLOGY_EN = (
    "The survey is carried out monthly by inFOM for the Bank of Russia: about 2,000 adults "
    "across the regions of Russia. People are asked how much prices have risen "
    "over the past year and how much they will rise over the next year; the series is the median answer. The "
    "consumer sentiment index combines answers about personal finances, the national economy and purchases. "
    "Before 2014 the survey ran several times a year, so the early series has gaps. A month's value is the survey "
    "taken that month; the Bank of Russia publishes it at the end of the month or early the next."
)

DEPOSIT_MAX_NAME = "Максимальная ставка по вкладам в 10 крупнейших банках"
DEPOSIT_MAX_NAME_EN = "Maximum deposit rate of the 10 largest banks"
DEPOSIT_MAX_DESCRIPTION = (
    "Средняя из максимальных ставок по рублёвым вкладам частных лиц в десяти банках, которые привлекают больше всего "
    "вкладов. Банк России считает её раз в десять дней — это ориентир «сколько сейчас дают по вкладу»."
)
DEPOSIT_MAX_DESCRIPTION_EN = (
    "The average of the maximum interest rates on rouble deposits of individuals at the ten banks that attract the "
    "most deposits. The Bank of Russia calculates it every ten days; it shows what a deposit pays right now."
)
DEPOSIT_MAX_METHODOLOGY = (
    "Банк России каждые десять дней (в первой, второй и третьей декаде месяца) смотрит на сайтах десяти банков, "
    "привлекающих больше всего вкладов населения, самую высокую ставку по рублёвому вкладу у каждого банка и считает "
    "среднее. Список банков пересматривается раз в квартал. Ставка показывает, что банки предлагают сейчас; "
    "средневзвешенная ставка по вкладам («Ставка по вкладам физических лиц») показывает, под какой процент люди "
    "фактически положили деньги за месяц, и выходит позже. Точка ставится на первый день декады: 1, 11 или 21-е "
    "число."
)
DEPOSIT_MAX_METHODOLOGY_EN = (
    "Every ten days (in the first, second and third ten-day period of the month) the Bank of Russia checks the "
    "websites of the ten banks that attract the most household deposits, takes each bank's highest rate on a rouble "
    "deposit and averages them. The list of banks is reviewed quarterly. The rate shows what banks offer now; the "
    "weighted average deposit rate shows the rate people actually received over a month and is published later. "
    "Each value is dated to the first day of its ten-day period: the 1st, 11th or 21st."
)
DEPOSIT_MAX_KEYWORDS = (
    "максимальная ставка по вкладам, максимальная процентная ставка, ставка по вкладам сейчас, проценты по вкладам, "
    "ставки по вкладам в крупнейших банках, ставки вкладов 10 банков, ставка по вкладам 2025, ставка по вкладам "
    "2026, депозиты, вклады, maximum deposit rate"
)


def seed_indicators():
    yield {
        "code": DEPOSIT_MAX_CODE,
        "name": DEPOSIT_MAX_NAME,
        "name_en": DEPOSIT_MAX_NAME_EN,
        "unit": "%",
        "frequency": "weekly",
        "source": "Банк России",
        "source_url": DEPOSIT_MAX_URL,
        "description": DEPOSIT_MAX_DESCRIPTION,
        "methodology": DEPOSIT_MAX_METHODOLOGY,
        "parser_type": "cbr_deposit_max_html",
        "model_config_json": {"forecast_steps": 0, "validation": {"min": 1, "max": 40}},
        "is_active": True,
        "category": "Ставки",
    }
    for code, s in SURVEY.items():
        yield {
            "code": code,
            "name": s.name,
            "name_en": s.name_en,
            "unit": s.unit,
            "frequency": "monthly",
            "source": "Банк России",
            "source_url": EXPECTATIONS_PAGE,
            "description": s.description,
            "methodology": SURVEY_METHODOLOGY,
            "parser_type": "cbr_inflation_expectations_xlsx",
            "model_config_json": {"forecast_steps": 0},
            "is_active": True,
            "category": s.category,
        }


def copy_en() -> dict[str, dict[str, str]]:
    out = {
        DEPOSIT_MAX_CODE: {
            "name": DEPOSIT_MAX_NAME_EN,
            "description": DEPOSIT_MAX_DESCRIPTION_EN,
            "methodology": DEPOSIT_MAX_METHODOLOGY_EN,
            "unit": "%",
        },
    }
    for code, s in SURVEY.items():
        out[code] = {"name": s.name_en, "description": s.description_en,
                     "methodology": SURVEY_METHODOLOGY_EN, "unit": s.unit_en}
    return out


def seo_keywords() -> dict[str, str]:
    out = {DEPOSIT_MAX_CODE: DEPOSIT_MAX_KEYWORDS}
    out.update({code: s.keywords for code, s in SURVEY.items()})
    return out


def seo_meta() -> dict[str, dict[str, str]]:
    out = {
        DEPOSIT_MAX_CODE: {
            "seo_title": "Максимальная ставка по вкладам в 10 крупнейших банках — Банк России, по декадам",
            "seo_description": (
                "Средняя максимальная ставка по рублёвым вкладам в десяти крупнейших банках России: каждые десять "
                "дней с 2009 года, данные Банка России."
            ),
        },
    }
    out.update({code: {"seo_title": s.seo_title, "seo_description": s.seo_description}
                for code, s in SURVEY.items()})
    return out


# Поиск: фразы людей → коды и слова названий (19.11.2026: «максимальная ставка по вкладам» из Яндекса, «наблюдаемая
# инфляция vs ожидаемая инфляция» — пустой внутренний поиск). Длинная фраза про максимальную ставку стоит раньше
# общего «ставка по вкладам» (deposit-rate) в CONCEPTS. Ипотека по регионам — ряд регионов `stavka-ipoteki`.
SEARCH_CONCEPTS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("максимальная ставка по вкладам", "максимальная ставка вкладов", "максимальная процентная ставка по вкладам",
      "максимальные ставки по вкладам", "ставка по вкладам в крупнейших банках", "ставки 10 банков",
      "maximum deposit rate"), (DEPOSIT_MAX_CODE, "максимальная ставка")),
    (("инфляционные ожидания", "инфляционные ожидания населения", "ожидаемая инфляция", "ожидания инфляции",
      "ожидания по инфляции", "inflation expectations", "expected inflation"),
     ("inflation-expected", "инфляционные ожидания")),
    (("наблюдаемая инфляция", "ощущаемая инфляция", "инфляция по ощущениям", "perceived inflation"),
     ("inflation-observed", "наблюдаемая инфляция")),
    (("потребительские настроения", "индекс потребительских настроений", "consumer sentiment",
      "consumer confidence"), ("consumer-sentiment", "потребительских настроений")),
    (("ставка по ипотеке по регионам", "ставки по ипотеке в регионах", "ипотечная ставка в регионе",
      "ставка по ипотеке в регионе"), ("stavka-ipoteki", "ставка по ипотеке")),
    (("ставки по вкладам по регионам", "ставка по вкладам в регионах", "ставки по вкладам по округам"),
     ("stavka-vkladov-do-1-goda", "ставка по вкладам до 1 года")),
)


_READING = {
    "inflation-expected": (
        "Ожидания людей обычно выше официальной инфляции: на них влияют цены на то, что покупают часто, — продукты, "
        "бензин, услуги ЖКХ. Банк России следит за ожиданиями при решениях по ключевой ставке: когда люди ждут "
        "быстрого роста цен, они больше тратят и меньше сберегают, и это само разгоняет цены. Сравните ряд с "
        "наблюдаемой инфляцией и с индексом потребительских цен Росстата."
    ),
    "inflation-observed": (
        "Наблюдаемая инфляция — это ощущение роста цен, а не расчёт по корзине товаров, поэтому она обычно выше "
        "официальной. Важно направление: если ощущаемая инфляция снижается вместе с официальной, людям проще "
        "планировать расходы. Сравните ряд с ожидаемой инфляцией и с индексом потребительских цен Росстата."
    ),
    "consumer-sentiment": (
        "Выше 100 — оптимистов больше, чем пессимистов; ниже — наоборот. Индекс растёт, когда люди лучше оценивают "
        "свои доходы и считают время подходящим для крупных покупок, и падает в кризисы. От настроений зависят "
        "потребительские расходы и спрос на кредиты."
    ),
}


def seo_blocks() -> dict[str, list[dict[str, str]]]:
    """Блок «О показателе»: что показывает, как читать, как часто обновляется, откуда данные."""
    out = {
        DEPOSIT_MAX_CODE: [
            {"title": "Что показывает", "body": DEPOSIT_MAX_DESCRIPTION},
            {"title": "Как читать", "body": (
                "Это не ставка конкретного банка и не обещанный доход: у отдельных вкладов с надбавками ставка "
                "бывает выше. Сравните её со средневзвешенной ставкой по вкладам — той, под которую люди реально "
                "положили деньги за месяц, — и с инфляцией: если ставка выше роста цен, вклад сохраняет "
                "покупательную способность. Ставки банков идут вслед за ключевой ставкой Банка России."
            )},
            {"title": "Как часто обновляется", "body": (
                "Три раза в месяц: за первую, вторую и третью декаду. Точка на графике стоит на первом дне декады — "
                "1, 11 или 21-м числе. История — со второй декады июля 2009 года."
            )},
            {"title": "Откуда данные", "body": (
                "Банк России: максимальная процентная ставка по вкладам в рублях десяти банков, привлекающих "
                "больше всего вкладов населения."
            )},
        ],
    }
    for code, s in SURVEY.items():
        out[code] = [
            {"title": "Что показывает", "body": s.description},
            {"title": "Как читать", "body": _READING[code]},
            {"title": "Как часто обновляется", "body": (
                "Каждый месяц: Банк России публикует итоги опроса в конце месяца или в начале следующего. Ряд — с "
                "декабря 2009 года; до 2014 года опрос проходил несколько раз в год."
            )},
            {"title": "Откуда данные", "body": (
                "Банк России, «Инфляционные ожидания и потребительские настроения»: ежемесячный опрос населения, "
                "который проводит «инФОМ»."
            )},
        ]
    return out
