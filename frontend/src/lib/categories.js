/**
 * 9 категорий платформы (Фаза 1 плана Forecast Economy).
 * apiCategory — точное значение Indicator.category в БД; null = раздел в разработке.
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
  },
  {
    slug: 'finance',
    name: 'Финансы и валюты',
    nameEn: 'Finance & FX',
    icon: 'Wallet',
    apiCategory: 'Финансы',
    status: 'active',
    flagshipCode: 'usd-rub',
    sentiment: 'inverse',
    description: 'Курсы валют. Денежные агрегаты М0, М1, М2. Резервы, внешний долг, расходы бюджета и депозиты.',
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
    description: 'Индекс промышленного производства, розничная торговля, износ основных фондов, инвестиции.',
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
  },
];

export function getCategoryBySlug(slug) {
  return CATEGORIES.find((c) => c.slug === slug);
}

export const HIDDEN_FROM_LISTING = new Set([
  'inflation-annual',
  'inflation-quarterly',
  'inflation-weekly',
  'cpi-food-quarterly',
  'cpi-food-annual',
  'cpi-nonfood-quarterly',
  'cpi-nonfood-annual',
  'cpi-services-quarterly',
  'cpi-services-annual',
  'ppi-yoy',
  'housing-yoy-primary',
  'housing-yoy-secondary',
  'gdp-real',
  'gdp-yoy',
  'gdp-qoq',
]);

/** Подсчёт индикаторов по полю category в API (исключая скрытые карточки) */
export function countInCategory(indicators, apiCategory) {
  if (!apiCategory || !indicators?.length) return 0;
  return indicators.filter((i) => i.category === apiCategory && !HIDDEN_FROM_LISTING.has(i.code)).length;
}
