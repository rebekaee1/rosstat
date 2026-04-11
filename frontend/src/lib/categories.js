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
      'Инфляция в России: индекс потребительских цен (ИПЦ), цены на жильё, индекс цен производителей. Официальные данные Росстата с 1991 года, графики и прогноз.',
    h1Suffix: 'в России — данные Росстата',
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
    description: 'Ключевая ставка ЦБ РФ на сегодня, RUONIA, ставки по ипотеке, вкладам и автокредитам. Актуальные данные Банка России, история и динамика.',
    h1Suffix: 'в России — Банк России',
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
    description: 'Курс доллара, евро и юаня к рублю, цена золота, денежная масса М0–М2, международные резервы, кредиты, вклады, доходы и расходы бюджета. Данные ЦБ РФ и Минфина.',
    h1Suffix: 'России — курсы, бюджет, резервы',
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
    description: 'Безработица в России, средняя зарплата, рабочая сила и занятость. Ежемесячные данные Росстата с 2015 года, графики и динамика.',
    h1Suffix: 'в России — данные Росстата',
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
    description: 'ВВП России: номинальный объём, темпы роста, потребление домохозяйств, госрасходы, инвестиции. Квартальные данные Росстата с 2011 года.',
    h1Suffix: 'России — квартальные данные',
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
    description: 'Население России: численность, рождаемость, смертность, естественный прирост, пенсионеры, возрастная структура. Данные Росстата с 1990 года.',
    h1Suffix: 'России — демографические данные',
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
    description: 'Внешняя торговля России: экспорт и импорт товаров и услуг, торговый баланс, текущий счёт, прямые иностранные инвестиции. Квартальные данные Банка России.',
    h1Suffix: 'России — данные ЦБ РФ',
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
    description: 'Бизнес в России: индекс промышленного производства (ИПП), розничная торговля, ввод жилья, строительство, инвестиции в основной капитал. Данные Росстата.',
    h1Suffix: 'в России — данные Росстата',
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
    description: 'Наука в России: аспиранты, докторанты, организации НИР, персонал исследований, уровень инновационной активности. Годовые данные Росстата.',
    h1Suffix: 'в России — данные Росстата',
  },
];

export function getCategoryBySlug(slug) {
  return CATEGORIES.find((c) => c.slug === slug);
}

export const HIDDEN_FROM_LISTING = new Set(['inflation-annual', 'inflation-quarterly', 'inflation-weekly']);

/** Подсчёт индикаторов по полю category в API (исключая скрытые карточки) */
export function countInCategory(indicators, apiCategory) {
  if (!apiCategory || !indicators?.length) return 0;
  return indicators.filter((i) => i.category === apiCategory && !HIDDEN_FROM_LISTING.has(i.code)).length;
}
