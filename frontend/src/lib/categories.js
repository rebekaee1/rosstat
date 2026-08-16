/**
 * Категории платформы (карточки меню/главной).
 *
 * apiCategory — точное значение Indicator.category в БД.
 *
 * seoTitle / seoDescription / seoH1 / name подтягиваются из серверного
 * CATEGORY_META через withCategorySeo. UI-описание карточки
 * (`description`) и иконки остаются здесь.
 *
 * relatedSlugs — соседи в смысле «о чём ещё посмотреть». Используется на
 * /russia/category/:slug в нижнем блоке «Связанные категории». Симметрия НЕ
 * требуется: A → B не обязывает B → A. Решает product-смысл, не граф-структура.
 */
import { withCategorySeo } from './pageMeta';

const CATEGORY_DEFS = [
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
    description: 'Нефть, природный газ, уголь, золото, серебро, медь, пшеница и соя — мировые цены на сырьё.',
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
    relatedSlugs: ['population', 'business', 'labor'],
  },
];

export const CATEGORIES = withCategorySeo(CATEGORY_DEFS);

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
