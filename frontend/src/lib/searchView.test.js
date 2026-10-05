import { describe, expect, it } from 'vitest';
import { translate } from '../i18n/messages';
import { buildSearchView, matchRatingConcept, ratingRowsFor } from './searchView';

const t = (key, vars) => translate(key, vars, 'ru');
const nameOf = (row) => row.name;
const titleOf = (row) => row.name;
const detailOf = (row) => [row.country_name, row.frequency].filter(Boolean).join(', ');

const RATINGS = [
  { slug: 'gdp-usd', name: 'ВВП' },
  { slug: 'gdp-per-capita-usd', name: 'ВВП на душу населения' },
  { slug: 'population', name: 'Население' },
  { slug: 'hicp-index', name: 'Инфляция' },
  { slug: 'unemployment-rate', name: 'Безработица' },
];
const ratingLabelOf = (concept) => concept.name;

function row(key, name, extra = {}) {
  return {
    key, kind: 'world', code: key, name, country_slug: 'germany', country_name: 'Германия', frequency: 'monthly', unit: '%', path: `/p/${key}`, ...extra,
  };
}

function view(rows, query, extra = {}) {
  return buildSearchView(rows, {
    query, nameOf, titleOf, detailOf, t, ratingConcepts: RATINGS, ratingLabelOf, ...extra,
  });
}

const ids = (sections) => sections.map((section) => [section.id, section.rows.map((r) => r.id)]);

describe('ratingRowsFor', () => {
  it('«gdp» без страны даёт рейтинг ВВП первым', () => {
    const rows = ratingRowsFor('gdp', { concepts: RATINGS, labelOf: ratingLabelOf, t });
    expect(rows[0].name).toBe('ВВП: рейтинг стран');
    expect(rows[0].open.path).toBe('/world/rating/gdp-usd');
  });
  it('с явной страной или регионом рейтингов нет', () => {
    expect(ratingRowsFor('gdp germany', { intent: { countries: ['germany'] }, concepts: RATINGS, labelOf: ratingLabelOf, t })).toEqual([]);
    expect(ratingRowsFor('gdp', { intent: { regions: ['r'] }, concepts: RATINGS, labelOf: ratingLabelOf, t })).toEqual([]);
  });
  it('нет каталога или слишком короткий запрос: пусто', () => {
    expect(ratingRowsFor('gdp', { concepts: [], labelOf: ratingLabelOf, t })).toEqual([]);
    expect(ratingRowsFor('g', { concepts: RATINGS, labelOf: ratingLabelOf, t })).toEqual([]);
  });
});

describe('matchRatingConcept', () => {
  it('находит показатель рейтинга по смыслу названия, а не по словам', () => {
    expect(matchRatingConcept('численность населения', RATINGS).slug).toBe('population');
    expect(matchRatingConcept('валовой продукт', RATINGS)?.slug).toBe('gdp-usd');
    expect(matchRatingConcept('кактус', RATINGS)).toBeNull();
  });
});

describe('buildSearchView: разделы и порядок', () => {
  it('«gdp»: сначала раздел «Рейтинги», потом «Показатели», российские кварталы не первыми', () => {
    const rows = [
      row('ru-gdp', 'ВВП номинальный', { kind: 'russia', country_slug: 'russia', country_name: 'Россия', frequency: 'quarterly', unit: 'млрд руб.' }),
      row('al-gdp', 'ВВП в постоянных ценах', { country_slug: 'albania', country_name: 'Албания', frequency: 'annual' }),
    ];
    const result = view(rows, 'gdp', { intent: { countries: [], regions: [] } });
    expect(result.sections.map((section) => section.id)).toEqual(['ratings', 'indicators']);
    expect(result.sections[0].rows[0].name).toBe('ВВП: рейтинг стран');
  });

  it('страны идут раньше рейтингов и показателей, когда запрос без явной страны', () => {
    const rows = [
      { key: 'country:germany', kind: 'country', name: 'Германия', path: '/germany' },
      row('de-gdp', 'ВВП'),
    ];
    const result = view(rows, 'герм', { intent: { countries: [], regions: [] } });
    expect(result.sections[0].id).toBe('countries');
  });

  it('запрос с явной страной: показатели первыми, рейтингов нет', () => {
    const rows = [
      { key: 'country:germany', kind: 'country', name: 'Германия', path: '/germany' },
      row('de-un', 'Безработица'),
    ];
    const result = view(rows, 'безработица германия', { intent: { countries: ['germany'], regions: [] } });
    expect(result.sections.map((section) => section.id)).toEqual(['indicators', 'countries']);
  });

  it('больше восьми строк: лишнее уходит под «Ещё варианты»', () => {
    const rows = Array.from({ length: 14 }, (_v, i) => row(`k${i}`, `Показатель ${i}`, { country_slug: `c${i}` }));
    const result = view(rows, 'показатель', { intent: { countries: [], regions: [] } });
    expect(result.flat).toHaveLength(8);
    expect(result.hiddenCount).toBe(6);
    expect(new Set([...result.flat, ...result.more].map((r) => r.item.key)).size).toBe(14);
  });
});

describe('buildSearchView: свёртка вариаций', () => {
  it('курс доллара: частоты в одну строку с переключателем, повторы под «Ещё»', () => {
    const base = { kind: 'russia', country_slug: 'russia', country_name: 'Россия', unit: 'руб.' };
    const rows = [
      row('usd-d', 'Курс доллара США', { ...base, frequency: 'daily' }),
      row('usd-m', 'Курс доллара США (средняя за месяц)', { ...base, frequency: 'monthly' }),
      row('usd-m-end', 'Курс доллара США (на конец месяца)', { ...base, frequency: 'monthly' }),
      row('usd-w', 'Курс доллара США (средняя за неделю)', { ...base, frequency: 'weekly' }),
      row('usd-q', 'Курс доллара США (средняя за квартал)', { ...base, frequency: 'quarterly' }),
      row('usd-y', 'Курс доллара США (средняя за год)', { ...base, frequency: 'annual' }),
    ];
    const result = view(rows, 'курс доллара', { intent: { countries: [], regions: [] } });
    const [family] = result.flat;
    expect(family.type).toBe('family');
    expect(family.chips.map((chip) => chip.frequency)).toEqual(['daily', 'weekly', 'monthly', 'quarterly', 'annual']);
    expect(family.chips.find((chip) => chip.frequency === 'monthly').item.key).toBe('usd-m');
    expect(result.flat.filter((r) => r.type !== 'rating')).toHaveLength(1);
    expect(result.more.map((r) => r.item.key)).toEqual(['usd-m-end']);
  });

  it('один показатель в разных странах: одна строка «Численность населения» с кнопками стран, популярные первыми', () => {
    const countries = ['albania', 'armenia', 'australia', 'germany', 'united-states', 'china'];
    const rows = countries.map((slug) => row(`pop-${slug}`, 'Численность населения', { country_slug: slug, country_name: slug, frequency: 'annual', unit: 'человек' }));
    const result = view(rows, 'population', { intent: { countries: [], regions: [] } });
    const indicators = result.sections.find((section) => section.id === 'indicators');
    expect(indicators.rows).toHaveLength(1);
    const group = indicators.rows[0];
    expect(group.type).toBe('byCountry');
    expect(group.countries.map((c) => c.country_slug).slice(0, 3)).toEqual(['united-states', 'china', 'germany']);
    expect(group.open.path).toBe('/world/rating/population');
    expect(group.detail).toBe('Выберите страну: доступно 6');
    expect(result.more).toEqual([]);
  });

  it('два показателя в одной стране не склеиваются в «по странам»', () => {
    const rows = [row('a', 'Население'), row('b', 'Население', { frequency: 'annual' }), row('c', 'Население', { frequency: 'quarterly' })];
    const result = view(rows, 'население', { intent: { countries: ['germany'], regions: [] } });
    expect(result.flat.some((r) => r.type === 'byCountry')).toBe(false);
  });
});

describe('buildSearchView: релевантность и «главная» строка', () => {
  it('нерелевантное после двух верных уходит под «Ещё варианты»', () => {
    const rows = [
      row('de-un-m', 'Уровень безработицы', { frequency: 'monthly' }),
      row('de-un-y', 'Уровень безработицы', { frequency: 'annual' }),
      row('de-pop', 'Население, %'),
      row('de-kids', 'Дети в домохозяйствах без работающих, %'),
    ];
    const result = view(rows, 'безработица германии', { intent: { countries: ['germany'], regions: [] } });
    const shown = result.flat.flatMap((r) => (r.type === 'family' ? r.chips.map((c) => c.item.key) : [r.item.key]));
    expect(shown).toContain('de-un-m');
    expect(shown).not.toContain('de-pop');
    expect(result.more.map((r) => r.item.key)).toEqual(expect.arrayContaining(['de-pop', 'de-kids']));
  });

  it('без подтверждённых строк ничего не прячет', () => {
    const rows = [row('a', 'Alpha'), row('b', 'Beta'), row('c', 'Gamma'), row('d', 'Delta')];
    const result = view(rows, 'zzqq', { intent: { countries: [], regions: [] } });
    expect(result.flat).toHaveLength(4);
    expect(result.more).toEqual([]);
  });

  it('число в запросе (год) не делает все строки «нерелевантными»', () => {
    const rows = ['a', 'b', 'c', 'd'].map((key) => row(key, 'ВВП', { country_slug: `c-${key}` }));
    const result = view(rows, 'ввп 2024', { intent: { countries: [], regions: [], year: 2024 } });
    expect(result.more).toEqual([]);
  });

  it('«inflation Germany»: первой встаёт годовая инфляция в процентах, а не индекс с базой', () => {
    const rows = [
      row('idx', 'Inflation, average consumer prices', { unit: 'index 2015=100', frequency: 'annual' }),
      row('g20', 'G20 CPI inflation', { country_slug: 'g20', country_name: 'Group of Twenty' }),
      row('hicp', 'HICP inflation rate', { unit: 'percent', frequency: 'monthly' }),
      row('yoy', 'Inflation annual rate of change', { unit: '%', frequency: 'annual' }),
    ];
    const result = view(rows, 'inflation germany', { intent: { countries: ['germany'], regions: [] }, locale: 'en' });
    const first = result.flat[0];
    expect(first.item.key).toBe('yoy');
    expect(result.flat.map((r) => r.item.key)).not.toContain('g20');
  });

  it('не затрагивает запросы не про инфляцию', () => {
    const rows = [row('a', 'Уровень безработицы %'), row('b', 'Уровень безработицы по возрасту', { country_slug: 'france', country_name: 'Франция' })];
    const result = view(rows, 'безработица', { intent: { countries: [], regions: [] } });
    expect(result.flat.filter((r) => r.type !== 'rating')[0].item.key).toBe('a');
  });
});

describe('buildSearchView: главный показатель выше побочных', () => {
  it('«gdp china»: годовой ВВП в долларах выше квартального и «в постоянных ценах»', () => {
    const china = { country_slug: 'china', country_name: 'Китай' };
    const rows = [
      row('cn-real', 'ВВП в постоянных ценах', { ...china, frequency: 'annual', unit: '100 млн юаней', score: 1000 }),
      row('cn-q', 'ВВП', { ...china, frequency: 'quarterly', unit: 'млрд юаней', score: 1000 }),
      row('cn-usd', 'ВВП', { ...china, frequency: 'annual', unit: 'млрд $', score: 990 }),
    ];
    const result = view(rows, 'ввп китай', { intent: { countries: ['china'], regions: [] } });
    // Годовой и квартальный ВВП сворачиваются в одну строку с переключателем; «в постоянных ценах» идёт после.
    expect(result.flat.map((r) => r.item.key)).toEqual(['cn-usd', 'cn-real']);
    expect(result.flat[0].chips.map((chip) => chip.frequency)).toEqual(['quarterly', 'annual']);
  });

  it('строки с заметно большей оценкой сервера не вытесняются', () => {
    const rows = [
      row('exact', 'ВВП в постоянных ценах', { frequency: 'quarterly', unit: 'млрд евро', score: 1200 }),
      row('other', 'ВВП', { frequency: 'annual', unit: 'млрд $', score: 900, country_slug: 'france', country_name: 'Франция' }),
    ];
    const result = view(rows, 'ввп', { intent: { countries: [], regions: [] } });
    expect(result.flat.filter((r) => r.type !== 'rating')[0].item.key).toBe('exact');
  });
});

describe('buildSearchView: сохранность', () => {
  it('каждая строка сервера доступна: видна, в переключателе, у страны или под «Ещё»', () => {
    const base = { kind: 'russia', country_slug: 'russia', country_name: 'Россия' };
    const rows = [
      row('k1', 'Курс доллара США', { ...base, frequency: 'daily' }),
      row('k2', 'Курс доллара США (месяц)', { ...base, frequency: 'monthly' }),
      row('k3', 'Курс доллара США (конец месяца)', { ...base, frequency: 'monthly' }),
      ...['albania', 'armenia', 'austria', 'italy'].map((slug) => row(`p-${slug}`, 'Численность населения', { country_slug: slug, frequency: 'annual' })),
      row('x', 'Что-то совсем другое'),
    ];
    const result = view(rows, 'курс население', { intent: { countries: [], regions: [] } });
    const reachable = new Set();
    for (const r of [...result.flat, ...result.more]) {
      reachable.add(r.item.key);
      (r.chips || []).forEach((chip) => reachable.add(chip.item.key));
      (r.countries || []).forEach((c) => reachable.add(c.key));
    }
    for (const r of rows) expect(reachable.has(r.key)).toBe(true);
  });

  it('разделы описаны в порядке показа и непусты', () => {
    const result = view([row('a', 'ВВП')], 'ввп', { intent: { countries: [], regions: [] } });
    expect(ids(result.sections).every(([, list]) => list.length > 0)).toBe(true);
  });
});

describe('buildSearchView: раунд 2 (Z8)', () => {
  it('запрос из одной буквы: сначала страны и главные показатели, региональные ряды в конец', () => {
    const rows = [
      row('reg-fdi', 'Поступление ПИИ', { kind: 'russia', country_slug: 'russia', country_name: 'Россия', region_slug: 'cfo', region_name: 'ЦФО' }),
      row('reg-2', 'Население региона', { kind: 'russia', country_slug: 'russia', country_name: 'Россия', region_slug: 'pfo', region_name: 'ПФО' }),
      row('gdp', 'ВВП', { country_slug: 'germany' }),
      { key: 'c1', kind: 'subnational_region', name: 'Центральный', region_slug: 'cfo' },
      { key: 'c2', kind: 'country', name: 'Албания', country_slug: 'albania' },
    ];
    const result = view(rows, 'а', { intent: { countries: [], regions: [] } });
    const order = [...result.flat, ...result.more].map((r) => r.item.key);
    expect(order.indexOf('c2')).toBeLessThan(order.indexOf('c1'));
    expect(order.indexOf('gdp')).toBeLessThan(order.indexOf('reg-fdi'));
    expect(order.indexOf('gdp')).toBeLessThan(order.indexOf('reg-2'));
  });

  it('«usd» и «курс доллара»: курс первым, выше рейтингов ВВП', () => {
    const rows = [
      row('gdp-us', 'ВВП США', { country_slug: 'united-states', country_name: 'США', code: 'gdp-usd', frequency: 'annual' }),
      row('usd', 'Курс доллара США', { kind: 'russia', code: 'usd-rub', country_slug: 'russia', country_name: 'Россия', frequency: 'daily', unit: '₽' }),
    ];
    for (const query of ['usd', 'курс доллара']) {
      const result = view(rows, query, { intent: { countries: [], regions: [] } });
      expect(result.sections[0].id).toBe('indicators');
      expect(result.flat[0].item.key).toBe('usd');
    }
  });

  it('страна из запроса: её строки идут первыми', () => {
    const rows = [
      row('anon', 'Инфляция', { country_slug: '', country_name: '' }),
      row('tr', 'Инфляция', { country_slug: 'turkey', country_name: 'Турция', code: 'tr-cpi' }),
    ];
    const result = view(rows, 'инфляция турция', { intent: { countries: ['turkey'], regions: [] } });
    expect(result.flat[0].item.key).toBe('tr');
  });

  it('«Ещё варианты» разложены по темам, порядок строк равен порядку на экране', () => {
    const primary = Array.from({ length: 8 }, (_, i) => row(`p${i}`, `Показатель ${i}`, { country_slug: `c${i}` }));
    const extra = [
      row('pop1', 'Численность населения региона', { country_slug: 'zz' }),
      row('inf1', 'Инфляция в регионе', { country_slug: 'zz' }),
      row('inf2', 'Индекс потребительских цен, продукты', { country_slug: 'zz' }),
    ];
    const result = view([...primary, ...extra], 'показатель', { intent: { countries: [], regions: [] } });
    expect(result.moreGroups.length).toBeGreaterThan(0);
    expect(result.more.map((r) => r.item.key)).toEqual(result.moreGroups.flatMap((g) => g.rows.map((r) => r.item.key)));
    expect(result.moreTopics).toEqual(result.moreGroups.map((g) => g.id));
    // Крупная тема (две строки про цены) стоит раньше одиночной.
    const prices = result.moreGroups.find((g) => g.id === 'prices');
    if (prices) expect(result.moreGroups[0].id).toBe('prices');
  });
});
