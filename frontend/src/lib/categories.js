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
    description:
      'ИПЦ и инфляция: официальные данные Росстата, скользящая годовая инфляция и прогноз.',
  },
  {
    slug: 'rates',
    name: 'Процентные ставки',
    nameEn: 'Interest Rates',
    icon: 'Percent',
    apiCategory: 'Ставки',
    status: 'active',
    description: 'Ключевая ставка ЦБ, RUONIA, ипотека, депозиты, автокредиты — актуальные данные Банка России.',
  },
  {
    slug: 'finance',
    name: 'Финансы и валюты',
    nameEn: 'Finance & FX',
    icon: 'Wallet',
    apiCategory: 'Финансы',
    status: 'active',
    description: 'Курсы валют, золото, М0–М2, резервы, внешний долг, кредиты, депозиты, доходы/расходы бюджета — данные ЦБ РФ и Минфина.',
  },
  {
    slug: 'labor',
    name: 'Рынок труда',
    nameEn: 'Labor Market',
    icon: 'Briefcase',
    apiCategory: 'Рынок труда',
    status: 'active',
    description: 'Безработица, зарплаты, рабочая сила, занятость — ежемесячные данные Росстата.',
  },
  {
    slug: 'gdp',
    name: 'ВВП и рост',
    nameEn: 'GDP & Growth',
    icon: 'BarChart3',
    apiCategory: 'ВВП',
    status: 'active',
    description: 'ВВП, темпы роста, потребление, госрасходы — структура экономики по данным Росстата.',
  },
  {
    slug: 'population',
    name: 'Население',
    nameEn: 'Population',
    icon: 'UserCircle',
    apiCategory: 'Население',
    status: 'active',
    description: 'Численность, естественный и миграционный прирост населения — данные Росстата с 1990 года.',
  },
  {
    slug: 'trade',
    name: 'Внешняя торговля',
    nameEn: 'Foreign Trade',
    icon: 'Globe',
    apiCategory: 'Торговля',
    status: 'active',
    description: 'Экспорт, импорт товаров и услуг, торговый баланс, текущий счёт, ПИИ — квартальные данные Банка России.',
  },
  {
    slug: 'business',
    name: 'Бизнес и инвестиции',
    nameEn: 'Business & Investment',
    icon: 'Factory',
    apiCategory: 'Бизнес',
    status: 'active',
    description: 'ИПП, ИЦП, инвестиции в капитал, ПИИ — данные Росстата и Банка России.',
  },
  {
    slug: 'science',
    name: 'Наука и образование',
    nameEn: 'Science & Education',
    icon: 'GraduationCap',
    apiCategory: null,
    status: 'planned',
    description: 'Наука, образование, инновации — в разработке.',
  },
];

export function getCategoryBySlug(slug) {
  return CATEGORIES.find((c) => c.slug === slug);
}

const HIDDEN_FROM_LISTING = new Set(['inflation-annual', 'inflation-quarterly', 'inflation-weekly']);

/** Подсчёт индикаторов по полю category в API (исключая скрытые карточки) */
export function countInCategory(indicators, apiCategory) {
  if (!apiCategory || !indicators?.length) return 0;
  return indicators.filter((i) => i.category === apiCategory && !HIDDEN_FROM_LISTING.has(i.code)).length;
}
