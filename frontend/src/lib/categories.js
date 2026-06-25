/**
 * Категории платформы (карточки меню/главной).
 *
 * apiCategory — точное значение Indicator.category в БД.
 *
 * seoTitle/seoDescription — ровно те же тексты, что backend SEO-renderer
 * (`seo_content.py::CATEGORY_META.title/description`) кладёт в SSR-HTML.
 * Если эти строки разойдутся, Yandex/Google после JS-rendering увидят другой
 * <title>/<meta description> и расценят страницу как изменённую → удаление и
 * повторное добавление в индекс. Любые правки делать в обоих местах разом.
 *
 * relatedSlugs — соседи в смысле «о чём ещё посмотреть». Используется на
 * /category/:slug в нижнем блоке «Связанные категории». Симметрия НЕ
 * требуется: A → B не обязывает B → A. Решает product-смысл, не граф-структура.
 */
export const CATEGORIES = [
  {
    slug: 'prices',
    name: 'Цены и инфляция',
    nameEn: 'Prices & Inflation',
    icon: 'ShoppingCart',
    apiCategory: 'Цены',
    status: 'active',
    flagshipCode: 'cpi',
    sentiment: 'inverse',
    description:
      'Индекс потребительских цен на товары и услуги. Индекс цен производителей. Цены на недвижимость.',
    seoTitle: 'Цены и инфляция в России',
    seoDescription: 'ИПЦ, инфляция, цены на жильё — данные Росстата и прогнозы.',
    relatedSlugs: ['rates', 'finance', 'labor'],
  },
  {
    slug: 'rates',
    name: 'Процентные ставки',
    nameEn: 'Interest Rates',
    icon: 'Percent',
    apiCategory: 'Ставки',
    status: 'active',
    flagshipCode: 'key-rate',
    sentiment: 'neutral',
    description: 'Ключевая ставка ЦБ, RUONIA. Ставки по вкладам, автокредитам и ипотеке.',
    seoTitle: 'Процентные ставки в России',
    seoDescription: 'Ключевая ставка ЦБ, RUONIA, ипотека, депозиты — данные Банка России.',
    relatedSlugs: ['prices', 'finance', 'business'],
  },
  {
    slug: 'currencies',
    name: 'Валюты',
    nameEn: 'Currencies',
    icon: 'CircleDollarSign',
    apiCategory: 'Валюты',
    status: 'active',
    flagshipCode: 'usd-rub',
    sentiment: 'inverse',
    description: 'Официальные курсы доллара, евро и юаня к рублю — ежедневные котировки Банка России.',
    seoTitle: 'Курсы валют ЦБ РФ',
    seoDescription: 'Курсы доллара, евро и юаня к рублю — официальные ежедневные данные Банка России.',
    relatedSlugs: ['finance', 'rates', 'trade'],
  },
  {
    slug: 'finance',
    name: 'Деньги и бюджет',
    nameEn: 'Money & Budget',
    icon: 'Wallet',
    apiCategory: 'Финансы',
    status: 'active',
    flagshipCode: 'm2',
    sentiment: 'neutral',
    description: 'Денежные агрегаты М0, М1, М2. Резервы, внешний долг, кредиты, депозиты, бюджет.',
    seoTitle: 'Деньги и бюджет России',
    seoDescription: 'Денежная масса, резервы, кредиты, депозиты, бюджет — данные ЦБ РФ и Минфина.',
    relatedSlugs: ['currencies', 'rates', 'trade'],
  },
  {
    slug: 'indices',
    name: 'Биржевые индексы',
    nameEn: 'Market Indices',
    icon: 'LineChart',
    apiCategory: 'Индексы',
    status: 'active',
    flagshipCode: 'imoex',
    sentiment: 'positive',
    description: 'Индекс МосБиржи и РТС, индекс полной доходности, индексы государственных и корпоративных облигаций.',
    seoTitle: 'Биржевые индексы России',
    seoDescription: 'Индекс МосБиржи, РТС, RGBI, индексы облигаций — ежедневные данные Московской биржи.',
    relatedSlugs: ['currencies', 'finance', 'rates'],
  },
  {
    slug: 'commodities',
    name: 'Товарные рынки',
    nameEn: 'Commodities',
    icon: 'Boxes',
    apiCategory: 'Товарные рынки',
    status: 'active',
    flagshipCode: 'brent',
    sentiment: 'neutral',
    description: 'Нефть, золото, серебро, медь, природный газ, уголь, сталь, пшеница и соя — мировые цены на сырьё.',
    seoTitle: 'Цены на сырьё и товарные рынки',
    seoDescription: 'Нефть Brent, золото, медь, газ, пшеница — ежедневные мировые цены на сырьевые товары.',
    relatedSlugs: ['indices', 'currencies', 'trade'],
  },
  {
    slug: 'labor',
    name: 'Рынок труда',
    nameEn: 'Labor Market',
    icon: 'Briefcase',
    apiCategory: 'Рынок труда',
    status: 'active',
    flagshipCode: 'unemployment',
    sentiment: 'inverse',
    description: 'Уровень безработицы, реальные и номинальные заработные платы. Рабочая сила и занятость.',
    seoTitle: 'Рынок труда России',
    seoDescription: 'Безработица, зарплаты, занятость — ежемесячные данные Росстата.',
    relatedSlugs: ['population', 'gdp', 'business'],
  },
  {
    slug: 'gdp',
    name: 'ВВП и рост',
    nameEn: 'GDP & Growth',
    icon: 'BarChart3',
    apiCategory: 'ВВП',
    status: 'active',
    flagshipCode: 'gdp-nominal',
    sentiment: 'positive',
    description: 'Валовой внутренний продукт, госрасходы, расходы домохозяйств. Темпы роста экономики.',
    seoTitle: 'ВВП и экономический рост России',
    seoDescription: 'ВВП, потребление, госрасходы, инвестиции — квартальные данные Росстата.',
    relatedSlugs: ['business', 'trade', 'labor'],
  },
  {
    slug: 'population',
    name: 'Население',
    nameEn: 'Population',
    icon: 'UserCircle',
    apiCategory: 'Население',
    status: 'active',
    flagshipCode: 'population',
    sentiment: 'positive',
    description: 'Численность населения, рождаемость, смертность, численность пенсионеров, трудоспособное население.',
    seoTitle: 'Население России',
    seoDescription: 'Численность, рождаемость, смертность, пенсионеры — демографические данные Росстата.',
    relatedSlugs: ['labor', 'science', 'gdp'],
  },
  {
    slug: 'trade',
    name: 'Внешняя торговля',
    nameEn: 'Foreign Trade',
    icon: 'Globe',
    apiCategory: 'Торговля',
    status: 'active',
    flagshipCode: 'current-account',
    sentiment: 'neutral',
    description: 'Экспорт товаров и услуг, импорт товаров и услуг, сальдо торгового баланса, сальдо текущего счёта.',
    seoTitle: 'Внешняя торговля России',
    seoDescription: 'Экспорт, импорт, торговый баланс, текущий счёт — квартальные данные Банка России.',
    relatedSlugs: ['finance', 'gdp', 'business'],
  },
  {
    slug: 'business',
    name: 'Бизнес и инвестиции',
    nameEn: 'Business & Investment',
    icon: 'Factory',
    apiCategory: 'Бизнес',
    status: 'active',
    flagshipCode: 'ipi',
    sentiment: 'positive',
    description: 'Индекс промышленного производства и его разделы: добыча, обрабатывающие производства, энергетика, водоснабжение. Розничная торговля, износ основных фондов, инвестиции.',
    seoTitle: 'Бизнес и инвестиции в России',
    seoDescription: 'Индекс промышленного производства (добыча, обработка, энергетика, водоснабжение), розничная торговля, инвестиции — данные Росстата.',
    relatedSlugs: ['gdp', 'rates', 'trade'],
  },
  {
    slug: 'science',
    name: 'Наука и образование',
    nameEn: 'Science & Education',
    icon: 'GraduationCap',
    apiCategory: 'Наука',
    status: 'active',
    flagshipCode: 'rd-personnel',
    sentiment: 'positive',
    description: 'Аспиранты, докторанты. Число организаций НИР. Инновационная активность предприятий.',
    seoTitle: 'Наука и образование в России',
    seoDescription: 'Аспиранты, организации НИР, инновационная активность — данные Росстата.',
    relatedSlugs: ['population', 'business', 'labor'],
  },
];

export function getCategoryBySlug(slug) {
  return CATEGORIES.find((c) => c.slug === slug);
}

/**
 * Признак «индикатор должен быть видим в листинге категорий».
 *
 * Источник правды: API-поле `indicator.is_listed` (живёт в БД-колонке
 * indicators.is_listed, редактируется без деплоя).
 */
export function isIndicatorListed(indicator) {
  if (!indicator) return false;
  return indicator.is_listed !== false;
}

/** Подсчёт индикаторов по полю category в API (исключая скрытые карточки) */
export function countInCategory(indicators, apiCategory) {
  if (!apiCategory || !indicators?.length) return 0;
  return indicators.filter((i) => i.category === apiCategory && isIndicatorListed(i)).length;
}
