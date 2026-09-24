// Navigation taxonomy for the US national and state catalogs. Source sections
// and indicator codes remain intact; this is a presentation-only second level.
export const US_TOPICS = [
  { id: 'gdp', ru: 'ВВП и производство', en: 'GDP and production' },
  { id: 'labor', ru: 'Труд и зарплаты', en: 'Labor and pay' },
  { id: 'income', ru: 'Доходы и потребление', en: 'Income and consumption' },
  { id: 'prices', ru: 'Цены', en: 'Prices' },
  { id: 'public', ru: 'Бюджет, налоги и соцвыплаты', en: 'Public finance and benefits' },
  { id: 'population', ru: 'Население и жильё', en: 'Population and housing' },
  { id: 'business', ru: 'Бизнес и отрасли', en: 'Business and industries' },
  { id: 'finance', ru: 'Финансы и рынки', en: 'Finance and markets' },
];

// BEA table identity is stable across Russian label revisions and locales.
const BEA_TABLE_TOPIC = {
  SASUMMARY: 'gdp', SAGDP1: 'gdp', SAGDP2: 'gdp', SAGDP8: 'gdp',
  SAGDP9: 'gdp', SAGDP11: 'gdp', SQGDP1: 'gdp', SQGDP2: 'gdp',
  SQGDP8: 'gdp', SQGDP9: 'gdp', SQGDP11: 'gdp',
  SAGDP4: 'labor', SAINC5N: 'labor', SAINC6N: 'labor',
  SAINC7N: 'labor', SAINC11: 'labor', SQINC5N: 'labor',
  SQINC6N: 'labor', SQINC7N: 'labor', SQINC11: 'labor',
  SAINC1: 'income', SAINC4: 'income', SAINC12: 'income',
  SAINC30: 'income', SAINC40: 'income', SAINC51: 'income',
  SQINC1: 'income', SQINC4: 'income', SQINC12: 'income',
  SAPCE1: 'income', SAPCE2: 'income', SAPCE3: 'income',
  SAPCE4: 'income', SAPCE5: 'income', SARPI: 'income',
  SARPP: 'prices', SAIRPD: 'prices',
  SAGDP3: 'public', SAGDP5: 'public', SAGDP6: 'public',
  SAINC35: 'public', SAINC50: 'public', SAINC70: 'public',
  SQINC35: 'public',
  SAGDP7: 'business',
};

const BASE_CODE_TOPIC = {
  'unemployment-rate': 'labor', 'nonfarm-employment': 'labor',
  'labor-force-participation': 'labor', 'minimum-wage': 'labor',
  'civilian-labor-force': 'labor', 'civilian-employment': 'labor',
  'unemployed-persons': 'labor', 'government-employment': 'labor',
  'real-gdp': 'gdp', 'nominal-gdp': 'gdp',
  'personal-income-per-capita': 'income', 'median-household-income': 'income',
  population: 'population',
  'house-price-index': 'population', 'building-permits': 'population',
  'homeownership-rate': 'population',
};

const NATIONAL_SECTION_TOPIC = {
  'Бизнес и инвестиции': 'business',
  'ВВП': 'gdp',
  'Государственные финансы': 'public',
  'Население': 'population',
  'Национальные счета': 'gdp',
  'Рынок труда': 'labor',
  'Финансы': 'finance',
  'Цены': 'prices',
};

const OTHER = { id: 'other', ru: 'Другие показатели', en: 'Other indicators' };

export function usTopicForSection(section) {
  const code = section.indicators?.[0]?.code || '';
  const table = /^(?:us-)?bea-([a-z0-9]+)-\d+$/.exec(code)?.[1]?.toUpperCase();
  if (table) return BEA_TABLE_TOPIC[table] || OTHER.id;
  return BASE_CODE_TOPIC[code]
    || NATIONAL_SECTION_TOPIC[section.name_ru || section.name]
    || OTHER.id;
}

export function groupUsSections(sections, locale = 'ru') {
  const groups = new Map();
  for (const section of sections) {
    const id = usTopicForSection(section);
    if (!groups.has(id)) {
      const topic = US_TOPICS.find((entry) => entry.id === id) || OTHER;
      groups.set(id, { id, label: locale === 'en' ? topic.en : topic.ru, sections: [], count: 0 });
    }
    const group = groups.get(id);
    group.sections.push(section);
    group.count += section.indicators?.length || 0;
  }
  return [...US_TOPICS, OTHER].filter((topic) => groups.has(topic.id)).map((topic) => groups.get(topic.id));
}

export function shortUsIndicatorName(name, sectionName, locale) {
  if (locale !== 'ru' || !sectionName) return name;
  const prefix = `${sectionName}: `;
  return name?.startsWith(prefix) ? name.slice(prefix.length) : name;
}
