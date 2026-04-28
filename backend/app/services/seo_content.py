"""Content registry for server-rendered SEO pages.

The registry keeps the page frame generic while allowing category- and
indicator-specific sections to grow over time without hardcoding them into
the renderer.
"""

from dataclasses import dataclass, field

DOMAIN = "https://forecasteconomy.com"
OG_IMAGE = f"{DOMAIN}/og-image-v2.png"


@dataclass(frozen=True)
class SeoBlock:
    title: str
    body: str


@dataclass(frozen=True)
class CategorySeo:
    slug: str
    name: str
    api_category: str
    title: str
    description: str
    intro: str
    flagship_code: str
    blocks: tuple[SeoBlock, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PageSeo:
    slug: str
    path: str
    title: str
    description: str
    h1: str
    intro: str
    links: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    blocks: tuple[SeoBlock, ...] = field(default_factory=tuple)


CATEGORY_META: dict[str, CategorySeo] = {
    "prices": CategorySeo(
        slug="prices",
        name="Цены и инфляция",
        api_category="Цены",
        title="Цены и инфляция в России",
        description="ИПЦ, инфляция, цены на жильё — данные Росстата и прогнозы.",
        intro=(
            "Раздел собирает показатели потребительских цен, инфляции и цен на жильё. "
            "Здесь можно смотреть динамику ИПЦ, годовые и квартальные изменения, "
            "а также связанные индексы по основным группам товаров и услуг."
        ),
        flagship_code="cpi",
        blocks=(
            SeoBlock(
                "Что важно в разделе",
                "Ценовые индикаторы помогают оценивать инфляционное давление, изменение покупательной способности и динамику отдельных компонентов потребительской корзины.",
            ),
        ),
    ),
    "rates": CategorySeo(
        slug="rates",
        name="Процентные ставки",
        api_category="Ставки",
        title="Процентные ставки в России",
        description="Ключевая ставка ЦБ, RUONIA, ипотека, депозиты — данные Банка России.",
        intro="Раздел объединяет ключевую ставку, рыночные денежные ставки и ставки по банковским продуктам.",
        flagship_code="key-rate",
    ),
    "finance": CategorySeo(
        slug="finance",
        name="Финансы и валюты",
        api_category="Финансы",
        title="Финансы и валюты России",
        description="Курсы валют, золото, денежная масса, кредиты, бюджет — данные ЦБ РФ и Минфина.",
        intro="Финансовые индикаторы показывают динамику валют, денежной массы, кредитов, депозитов и государственных финансов.",
        flagship_code="usd-rub",
    ),
    "labor": CategorySeo(
        slug="labor",
        name="Рынок труда",
        api_category="Рынок труда",
        title="Рынок труда России",
        description="Безработица, зарплаты, занятость — ежемесячные данные Росстата.",
        intro="Раздел помогает отслеживать занятость, безработицу и динамику заработной платы в России.",
        flagship_code="unemployment",
    ),
    "gdp": CategorySeo(
        slug="gdp",
        name="ВВП и рост",
        api_category="ВВП",
        title="ВВП и экономический рост России",
        description="ВВП, потребление, госрасходы, инвестиции — квартальные данные Росстата.",
        intro="Раздел посвящён экономическому росту, номинальному ВВП и производным темпам изменения экономики.",
        flagship_code="gdp-nominal",
    ),
    "population": CategorySeo(
        slug="population",
        name="Население",
        api_category="Население",
        title="Население России",
        description="Численность, рождаемость, смертность, пенсионеры — демографические данные Росстата.",
        intro="Демографические показатели описывают численность населения, естественное движение и миграцию.",
        flagship_code="population",
    ),
    "trade": CategorySeo(
        slug="trade",
        name="Внешняя торговля",
        api_category="Торговля",
        title="Внешняя торговля России",
        description="Экспорт, импорт, торговый баланс, текущий счёт — квартальные данные Банка России.",
        intro="Раздел показывает внешнеэкономические потоки и показатели платёжного баланса.",
        flagship_code="current-account",
    ),
    "business": CategorySeo(
        slug="business",
        name="Бизнес и инвестиции",
        api_category="Бизнес",
        title="Бизнес и инвестиции в России",
        description="ИПП, розничная торговля, ввод жилья, инвестиции — данные Росстата.",
        intro="Показатели бизнеса и инвестиций помогают оценивать промышленную активность и динамику капитальных вложений.",
        flagship_code="ipi",
    ),
    "science": CategorySeo(
        slug="science",
        name="Наука и образование",
        api_category="Наука",
        title="Наука и образование в России",
        description="Аспиранты, организации НИР, инновационная активность — данные Росстата.",
        intro="Раздел предназначен для показателей науки, образования и инновационной активности.",
        flagship_code="rd-personnel",
    ),
}

CATEGORIES = tuple(CATEGORY_META.keys())

STATIC_PAGES = [
    ("/", "daily", "1.0"),
    ("/about", "monthly", "0.5"),
    ("/privacy", "monthly", "0.3"),
    ("/calculator", "monthly", "0.6"),
    ("/compare", "monthly", "0.6"),
    ("/demographics", "monthly", "0.7"),
]

PAGE_META: dict[str, PageSeo] = {
    "home": PageSeo(
        slug="home",
        path="/",
        title="Forecast Economy — экономические данные и прогнозы по России",
        description="Бесплатная аналитическая платформа: ИПЦ, ставка ЦБ, курсы валют, ВВП, безработица — данные Росстата и ЦБ РФ с прогнозами. 80+ индикаторов, обновление ежедневно.",
        h1="Forecast Economy — экономические данные России",
        intro="Forecast Economy собирает макроэкономические индикаторы России из открытых источников: Росстата, Банка России и Минфина. На сайте доступны графики, таблицы, прогнозы и сравнение показателей.",
        links=(
            ("/category/prices", "Цены и инфляция"),
            ("/category/rates", "Процентные ставки"),
            ("/category/finance", "Финансы и валюты"),
            ("/indicator/cpi", "Индекс потребительских цен"),
            ("/demographics", "Возрастная структура населения"),
            ("/calculator", "Калькулятор инфляции"),
            ("/compare", "Сравнение индикаторов"),
        ),
    ),
    "about": PageSeo(
        slug="about",
        path="/about",
        title="О проекте Forecast Economy",
        description="Бесплатная аналитическая платформа макроэкономических данных России. 80+ индикаторов, данные Росстата и ЦБ РФ.",
        h1="О проекте Forecast Economy",
        intro="Forecast Economy — информационный проект о макроэкономических данных России. Мы приводим официальные показатели к удобному виду: графики, таблицы, источники и прогнозы.",
        links=(("/privacy", "Политика конфиденциальности"), ("/", "Главная")),
    ),
    "privacy": PageSeo(
        slug="privacy",
        path="/privacy",
        title="Политика конфиденциальности — Forecast Economy",
        description="Как Forecast Economy обрабатывает данные посетителей.",
        h1="Политика конфиденциальности",
        intro="На этой странице описано, какие технические данные могут обрабатываться при использовании сайта и сервисов веб-аналитики.",
        links=(("/about", "О проекте"), ("/", "Главная")),
    ),
    "compare": PageSeo(
        slug="compare",
        path="/compare",
        title="Сравнение индикаторов — Forecast Economy",
        description="Сравнивайте любые два макроэкономических индикатора России на одном графике.",
        h1="Сравнение макроэкономических индикаторов",
        intro="Инструмент сравнения помогает сопоставить динамику двух показателей на одном графике: например, инфляцию и ставку ЦБ, курс валюты и денежную массу.",
        links=(("/indicator/cpi", "ИПЦ"), ("/indicator/key-rate", "Ключевая ставка"), ("/category/finance", "Финансы и валюты")),
    ),
    "calculator": PageSeo(
        slug="calculator",
        path="/calculator",
        title="Калькулятор инфляции — Forecast Economy",
        description="Рассчитайте обесценивание денег за любой период. Данные ИПЦ Росстата с 1991 года.",
        h1="Калькулятор инфляции",
        intro="Калькулятор показывает, как менялась покупательная способность рубля за выбранный период по данным индекса потребительских цен.",
        links=(("/indicator/cpi", "ИПЦ"), ("/category/prices", "Цены и инфляция")),
    ),
    "calendar": PageSeo(
        slug="calendar",
        path="/calendar",
        title="Экономический календарь России — Forecast Economy",
        description="Расписание публикации макроэкономических данных: Росстат, ЦБ РФ, Минфин.",
        h1="Экономический календарь",
        intro="Календарь помогает отслеживать даты публикации макроэкономических данных и обновлений официальных источников.",
        links=(("/category/prices", "Цены"), ("/category/rates", "Ставки")),
    ),
    "demographics": PageSeo(
        slug="demographics",
        path="/demographics",
        title="Возрастная структура населения России — Forecast Economy",
        description="Дети, трудоспособные, старше трудоспособного — данные Росстата с 1990 года.",
        h1="Возрастная структура населения России",
        intro="Страница показывает распределение населения России по возрастным группам и помогает анализировать демографическую нагрузку.",
        links=(("/category/population", "Население"), ("/indicator/population", "Численность населения")),
    ),
    "widgets": PageSeo(
        slug="widgets",
        path="/widgets",
        title="Виджеты Forecast Economy",
        description="Встраиваемые графики, карточки и тикеры для вашего сайта.",
        h1="Виджеты Forecast Economy",
        intro="Виджеты позволяют встроить экономические графики и карточки Forecast Economy на внешний сайт.",
        links=(("/indicator/cpi", "ИПЦ"), ("/compare", "Сравнение")),
    ),
}

INDICATOR_BLOCKS: dict[str, tuple[SeoBlock, ...]] = {
    "cpi": (
        SeoBlock(
            "Как читать ИПЦ",
            "ИПЦ показывает изменение цен на потребительские товары и услуги относительно предыдущего периода. Значения выше 100 означают рост цен, ниже 100 — снижение.",
        ),
        SeoBlock(
            "Почему показатель важен",
            "Индекс потребительских цен используется для оценки инфляции, индексации выплат и анализа покупательной способности населения.",
        ),
    ),
    "key-rate": (
        SeoBlock(
            "Почему важна ключевая ставка",
            "Ключевая ставка влияет на стоимость денег в экономике, банковские кредиты, депозиты и ожидания по инфляции.",
        ),
    ),
}

GLOBAL_INDICATOR_BLOCKS = (
    SeoBlock(
        "Источник и обновление",
        "Страница использует открытые данные официальных источников. Источник, периодичность и дата последнего значения указаны в карточке индикатора.",
    ),
)
