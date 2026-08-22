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

/**
 * seoTitleEn / seoDescriptionEn обязаны совпадать побайтово с английскими
 * CATEGORY_META в backend/app/data/i18n/seo_en.py, nameEn — с их name.
 * Иначе SSR-мета разойдётся с клиентской, и поисковик переиндексирует страницу.
 */
const CATEGORY_DEFS = [
  {
    slug: 'prices',
    name: 'Цены и инфляция',
    nameEn: 'Prices and inflation',
    seoTitleEn: 'Prices and inflation in Russia',
    seoDescriptionEn: 'CPI, inflation, and housing prices — Rosstat data and forecasts.',
    icon: 'ShoppingCart',
    apiCategory: 'Цены',
    status: 'active',
    flagshipCode: 'cpi',
    sentiment: 'inverse',
    description:
      'Индекс потребительских цен на товары и услуги. Индекс цен производителей. Цены на недвижимость.',
    descriptionEn:
      'Consumer price index for goods and services. Producer prices. Housing prices.',
    relatedSlugs: ['rates', 'finance', 'labor'],
  },
  {
    slug: 'rates',
    name: 'Процентные ставки',
    nameEn: 'Interest rates',
    seoTitleEn: 'Interest rates in Russia',
    seoDescriptionEn: 'Key rate, RUONIA, mortgage and deposit rates — Bank of Russia data.',
    icon: 'Percent',
    apiCategory: 'Ставки',
    status: 'active',
    flagshipCode: 'key-rate',
    sentiment: 'neutral',
    description: 'Ключевая ставка ЦБ, RUONIA. Ставки по вкладам, автокредитам и ипотеке.',
    descriptionEn:
      'CBR key rate, RUONIA. Deposit, auto loan and mortgage rates.',
    relatedSlugs: ['prices', 'finance', 'business'],
  },
  {
    slug: 'currencies',
    name: 'Валюты',
    nameEn: 'Currencies',
    seoTitleEn: 'Bank of Russia exchange rates',
    seoDescriptionEn:
      'USD, EUR, and CNY against the ruble — official daily rates from the Bank of Russia.',
    icon: 'CircleDollarSign',
    apiCategory: 'Валюты',
    status: 'active',
    flagshipCode: 'usd-rub',
    sentiment: 'inverse',
    description: 'Официальные курсы доллара, евро и юаня к рублю — ежедневные котировки Банка России.',
    descriptionEn:
      'Official USD, EUR and CNY rates against the ruble — daily Bank of Russia quotes.',
    relatedSlugs: ['finance', 'rates', 'trade'],
  },
  {
    slug: 'finance',
    name: 'Деньги и бюджет',
    nameEn: 'Money and budget',
    seoTitleEn: 'Money and budget in Russia',
    seoDescriptionEn:
      'Money supply, reserves, credit, deposits, and the budget — Bank of Russia and Ministry of Finance data.',
    icon: 'Wallet',
    apiCategory: 'Финансы',
    status: 'active',
    flagshipCode: 'm2',
    sentiment: 'neutral',
    description: 'Денежные агрегаты М0, М1, М2. Резервы, внешний долг, кредиты, депозиты, бюджет.',
    descriptionEn:
      'Monetary aggregates M0, M1, M2. Reserves, external debt, credit, deposits, budget.',
    relatedSlugs: ['currencies', 'rates', 'trade'],
  },
  {
    slug: 'indices',
    name: 'Биржевые индексы',
    nameEn: 'Market indices',
    seoTitleEn: 'Russian market indices',
    seoDescriptionEn:
      'MOEX, RTS, RGBI, and bond indices — daily data from Moscow Exchange.',
    icon: 'LineChart',
    apiCategory: 'Индексы',
    status: 'active',
    flagshipCode: 'imoex',
    sentiment: 'positive',
    description: 'Индекс МосБиржи и РТС, индекс полной доходности, индексы государственных и корпоративных облигаций.',
    descriptionEn:
      'MOEX and RTS indices, total return index, government and corporate bond indices.',
    relatedSlugs: ['currencies', 'finance', 'rates'],
  },
  {
    slug: 'commodities',
    name: 'Товарные рынки',
    nameEn: 'Commodities',
    seoTitleEn: 'Commodity prices and markets',
    seoDescriptionEn:
      'Brent crude, natural gas, gold, copper, wheat — global commodity prices from official sources.',
    icon: 'Boxes',
    apiCategory: 'Товарные рынки',
    status: 'active',
    flagshipCode: 'brent',
    sentiment: 'neutral',
    description: 'Нефть, природный газ, уголь, золото, серебро, медь, пшеница и соя — мировые цены на сырьё.',
    descriptionEn:
      'Oil, natural gas, coal, gold, silver, copper, wheat and soy — global commodity prices.',
    relatedSlugs: ['indices', 'currencies', 'trade'],
  },
  {
    slug: 'labor',
    name: 'Рынок труда',
    nameEn: 'Labor market',
    seoTitleEn: 'Labor market in Russia',
    seoDescriptionEn: 'Unemployment, wages, and employment — monthly Rosstat data.',
    icon: 'Briefcase',
    apiCategory: 'Рынок труда',
    status: 'active',
    flagshipCode: 'unemployment',
    sentiment: 'inverse',
    description: 'Уровень безработицы, реальные и номинальные заработные платы. Рабочая сила и занятость.',
    descriptionEn:
      'Unemployment rate, real and nominal wages. Labour force and employment.',
    relatedSlugs: ['population', 'gdp', 'business'],
  },
  {
    slug: 'gdp',
    name: 'ВВП и рост',
    nameEn: 'GDP and growth',
    seoTitleEn: 'GDP and economic growth in Russia',
    seoDescriptionEn:
      'GDP, consumption, government spending, and investment — quarterly Rosstat data.',
    icon: 'BarChart3',
    apiCategory: 'ВВП',
    status: 'active',
    flagshipCode: 'gdp-nominal',
    sentiment: 'positive',
    description: 'Валовой внутренний продукт, госрасходы, расходы домохозяйств. Темпы роста экономики.',
    descriptionEn:
      'Gross domestic product, government spending, household consumption. Growth rates.',
    relatedSlugs: ['business', 'trade', 'labor'],
  },
  {
    slug: 'population',
    name: 'Население',
    nameEn: 'Population',
    seoTitleEn: 'Population of Russia',
    seoDescriptionEn:
      'Population size, births, deaths, and pensioners — Rosstat demographic data.',
    icon: 'UserCircle',
    apiCategory: 'Население',
    status: 'active',
    flagshipCode: 'population',
    sentiment: 'positive',
    description: 'Численность населения, рождаемость, смертность, численность пенсионеров, трудоспособное население.',
    descriptionEn:
      'Population size, births, deaths, pensioners, working-age population.',
    relatedSlugs: ['labor', 'science', 'gdp'],
  },
  {
    slug: 'trade',
    name: 'Внешняя торговля',
    nameEn: 'Foreign trade',
    seoTitleEn: 'Foreign trade of Russia',
    seoDescriptionEn:
      'Exports, imports, trade balance, and the current account — quarterly Bank of Russia data.',
    icon: 'Globe',
    apiCategory: 'Торговля',
    status: 'active',
    flagshipCode: 'current-account',
    sentiment: 'neutral',
    description: 'Экспорт товаров и услуг, импорт товаров и услуг, сальдо торгового баланса, сальдо текущего счёта.',
    descriptionEn:
      'Exports and imports of goods and services, trade balance, current account balance.',
    relatedSlugs: ['finance', 'gdp', 'business'],
  },
  {
    slug: 'business',
    name: 'Бизнес и инвестиции',
    nameEn: 'Business and investment',
    seoTitleEn: 'Business and investment in Russia',
    seoDescriptionEn:
      'Industrial production index (mining, manufacturing, energy, water supply), retail trade, and investment — Rosstat data.',
    icon: 'Factory',
    apiCategory: 'Бизнес',
    status: 'active',
    flagshipCode: 'ipi',
    sentiment: 'positive',
    description: 'Индекс промышленного производства и его разделы: добыча, обрабатывающие производства, энергетика, водоснабжение. Розничная торговля, износ основных фондов, инвестиции.',
    descriptionEn:
      'Industrial production index and its sections: mining, manufacturing, energy, water supply. Retail trade, fixed asset wear, investment.',
    relatedSlugs: ['gdp', 'rates', 'trade'],
  },
  {
    slug: 'science',
    name: 'Наука и образование',
    nameEn: 'Science and education',
    seoTitleEn: 'Science and education in Russia',
    seoDescriptionEn:
      'Postgraduate students, R&D organizations, and innovation activity — Rosstat data.',
    icon: 'GraduationCap',
    apiCategory: 'Наука',
    status: 'active',
    flagshipCode: 'rd-personnel',
    sentiment: 'positive',
    description: 'Аспиранты, докторанты. Число организаций НИР. Инновационная активность предприятий.',
    descriptionEn:
      'Postgraduate and doctoral students. Number of R&D organizations. Enterprise innovation activity.',
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
export function indicatorCategoryKey(indicator) {
  if (!indicator) return null;
  // Приоритет — ключ хранения; подпись берём, только если ключа нет (старые ответы API).
  return indicator.category_ru || indicator.category || null;
}

export function findCategoryByApiLabel(label) {
  if (!label) return null;
  return (
    CATEGORIES.find(
      (c) => c.apiCategory === label || c.nameEn === label || c.name === label,
    ) || null
  );
}

export function countInCategory(indicators, apiCategory) {
  if (!apiCategory || !indicators?.length) return 0;
  return indicators.filter(
    (i) => indicatorCategoryKey(i) === apiCategory && isIndicatorListed(i),
  ).length;
}
