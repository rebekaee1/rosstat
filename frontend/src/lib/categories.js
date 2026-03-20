/**
 * 9 категорий платформы (Фаза 1 плана Forecast Economy).
 * apiCategory — точное значение Indicator.category в БД; null = раздел в разработке.
 */
export const CATEGORIES = [
  {
    slug: 'prices',
    name: 'Цены и инфляция',
    nameEn: 'Prices & Inflation',
    icon: 'TrendingUp',
    apiCategory: 'Цены',
    status: 'active',
    description:
      'ИПЦ и инфляция: официальные данные Росстата, скользящая годовая инфляция и OLS-прогноз.',
  },
  {
    slug: 'rates',
    name: 'Процентные ставки',
    nameEn: 'Interest Rates',
    icon: 'Percent',
    apiCategory: 'Денежно-кредитная политика',
    status: 'active',
    description: 'Ключевая ставка ЦБ и связанные решения по денежно-кредитной политике.',
  },
  {
    slug: 'finance',
    name: 'Финансы и валюты',
    nameEn: 'Finance & FX',
    icon: 'Wallet',
    apiCategory: null,
    status: 'planned',
    description: 'Курсы валют, денежные агрегаты M0–M2, банковская статистика — в разработке.',
  },
  {
    slug: 'labor',
    name: 'Рынок труда',
    nameEn: 'Labor Market',
    icon: 'Users',
    apiCategory: 'Рынок труда',
    status: 'active',
    description: 'Безработица, зарплаты и занятость по данным Росстата.',
  },
  {
    slug: 'gdp',
    name: 'ВВП и рост',
    nameEn: 'GDP & Growth',
    icon: 'Landmark',
    apiCategory: null,
    status: 'planned',
    description: 'Валовой внутренний продукт и темпы роста — в разработке.',
  },
  {
    slug: 'population',
    name: 'Население',
    nameEn: 'Population',
    icon: 'UserCircle',
    apiCategory: null,
    status: 'planned',
    description: 'Численность, рождаемость, смертность и демографические ряды — в разработке.',
  },
  {
    slug: 'trade',
    name: 'Внешняя торговля',
    nameEn: 'Foreign Trade',
    icon: 'Globe',
    apiCategory: null,
    status: 'planned',
    description: 'Экспорт, импорт и торговый баланс — в разработке.',
  },
  {
    slug: 'business',
    name: 'Бизнес и инвестиции',
    nameEn: 'Business & Investment',
    icon: 'Factory',
    apiCategory: null,
    status: 'planned',
    description: 'Промышленность, розница, инвестиции — в разработке.',
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

/** Подсчёт индикаторов по полю category в API */
export function countInCategory(indicators, apiCategory) {
  if (!apiCategory || !indicators?.length) return 0;
  return indicators.filter((i) => i.category === apiCategory).length;
}
