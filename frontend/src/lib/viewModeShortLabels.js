/**
 * Короткие человеческие названия для переключателя «Что показать» на странице показателя страны.
 *
 * Источники отдают канцелярские названия («Государственный долг сектора государственного управления»,
 * «Валовой внутренний продукт на душу населения в т…»): в чипе они обрезались посреди слова.
 * Источник правды (данные, URL, заголовок страницы) не меняется: короткое имя только для подписи чипа,
 * полное остаётся в `title` и в подписи для скринридера. Чистые функции без React, их проверяют тестами.
 *
 * Если два варианта дали одинаковое короткое имя (ВВП в текущих и в постоянных ценах), оба остаются полными.
 */

const NBSP = '\u00A0';

function capitalize(text) {
  const t = String(text || '').trim();
  return t ? t.charAt(0).toUpperCase() + t.slice(1) : t;
}

function tidy(text) {
  return String(text || '').replace(/\s+/g, ' ').replace(/\s+,/g, ',').replace(/[\s,;:-]+$/, '').trim();
}

/** Короткое имя по-русски; null, если правило не нашлось и подпись нужно оставить как есть. */
function shortRu(label) {
  const text = tidy(label);
  if (!text) return null;
  if (/^численность\s+населения/i.test(text)) return 'Население';
  if (/^(валовой\s+внутренний\s+продукт|ввп)(?![а-яё]).*на\s+душу/i.test(text)) {
    return /ппс|паритет/i.test(text) ? `ВВП на душу${NBSP}населения, ППС` : `ВВП на душу${NBSP}населения`;
  }
  if (/^(валовой\s+внутренний\s+продукт|ввп)(?![а-яё])/i.test(text)) {
    if (/постоянн/i.test(text)) return 'ВВП, постоянные цены';
    if (/ппс|паритет/i.test(text)) return 'ВВП по ППС';
    if (/рост|темп|реальн/i.test(text)) return 'Рост ВВП';
    return 'ВВП';
  }
  if (/^государственный\s+долг/i.test(text)) {
    return /%\s*(от\s+)?ввп/i.test(text) ? 'Госдолг, % ВВП' : 'Госдолг';
  }
  if (/^(баланс\s+бюджета|чистое\s+(кредитование|заимствование))/i.test(text)) {
    return /%\s*(от\s+)?ввп/i.test(text) ? 'Баланс бюджета, % ВВП' : 'Баланс бюджета';
  }
  if (/^изменение\s+потребительских\s+цен/i.test(text)) return 'Инфляция за год';
  if (/^%\s*(от\s+рабочей\s+силы|эан)/i.test(text)) return 'Безработица';
  const cleaned = tidy(
    text
      .replace(/\s+сектора\s+государственного\s+управлен\S*/gi, '')
      .replace(/\s+в\s+текущих\s+ценах(?![а-яё])/gi, '')
      .replace(/\s+в\s+т\S{0,6}$/i, ''),
  );
  return cleaned && cleaned !== text ? capitalize(cleaned) : null;
}

/** Короткое имя по-английски; null, если подпись и так короткая. */
function shortEn(label) {
  const text = tidy(label);
  if (!text) return null;
  if (/^gross\s+domestic\s+product\b.*per\s+capita/i.test(text)) {
    return /ppp|purchasing/i.test(text) ? 'GDP per capita, PPP' : 'GDP per capita';
  }
  if (/^gross\s+domestic\s+product\b/i.test(text)) {
    if (/constant/i.test(text)) return 'GDP, constant prices';
    if (/ppp|purchasing/i.test(text)) return 'GDP, PPP';
    return 'GDP';
  }
  if (/^general\s+government\s+gross\s+debt/i.test(text)) {
    return /%\s*of\s+gdp/i.test(text) ? 'Government debt, % of GDP' : 'Government debt';
  }
  if (/^general\s+government\s+(net\s+lending|overall\s+balance|primary\s+net)/i.test(text)) {
    return /%\s*of\s+gdp/i.test(text) ? 'Budget balance, % of GDP' : 'Budget balance';
  }
  if (/^inflation,?\s+average\s+consumer\s+prices/i.test(text)) return 'Inflation, yearly average';
  if (/^average\s+consumer\s+prices/i.test(text)) return 'Average consumer prices';
  if (/^unemployment\s+rate/i.test(text)) return 'Unemployment rate';
  if (/^population\b/i.test(text)) return 'Population';
  if (text !== text.charAt(0).toUpperCase() + text.slice(1)) return capitalize(text);
  return null;
}

/** Короткое имя варианта для чипа (всегда с заглавной); если правила нет, то сама подпись. */
export function shortVariantLabel(label, locale = 'ru') {
  const text = String(label ?? '').trim();
  if (!text) return text;
  const short = locale === 'en' ? shortEn(text) : shortRu(text);
  return capitalize(short || text);
}

// Чем меньше число, тем раньше стоит чип: сначала то, зачем приходят чаще всего.
const IMPORTANCE = [
  [/^(валовой\s+внутренний\s+продукт|ввп|gross\s+domestic\s+product|gdp)(?![а-яёa-z])(?!.*(на\s+душу|per\s+capita))/i, 1],
  [/(на\s+душу|per\s+capita)/i, 2],
  [/^(численность\s+населения|население|population)/i, 3],
  [/(инфляц|потребительских\s+цен|consumer\s+price|inflation)/i, 4],
  [/(безработиц|рабочей\s+силы|эан|unemployment|labou?r\s+force)/i, 5],
  [/(баланс\s+бюджета|кредитование|заимствование|net\s+lending|budget)/i, 6],
  [/(государственный\s+долг|госдолг|gross\s+debt|government\s+debt)/i, 7],
];

export function variantImportance(label) {
  const text = String(label ?? '');
  for (const [re, rank] of IMPORTANCE) {
    if (re.test(text)) return rank;
  }
  return 50;
}

/**
 * Группа вариантов для `VariantGroupPicker`: короткие имена, полное имя в `title`, чипы по важности.
 * Исходная группа не меняется. Одинаковые короткие имена (после сокращения) остаются полными.
 */
export function prepareVariantGroup(group, { locale = 'ru', sort = true } = {}) {
  if (!group || !Array.isArray(group.codes)) return group;
  const withShort = group.codes.map((item, index) => ({
    item, index, short: shortVariantLabel(item.label, locale),
  }));
  const seen = new Map();
  withShort.forEach(({ short }) => seen.set(short, (seen.get(short) || 0) + 1));
  const codes = withShort.map(({ item, index, short }) => {
    const full = capitalize(String(item.label ?? '').trim());
    const unique = seen.get(short) === 1;
    return {
      ...item,
      label: full || item.label,
      short: unique && short !== full ? short : undefined,
      title: unique && short !== full ? full : undefined,
      _index: index,
    };
  });
  if (sort) {
    codes.sort((a, b) => (variantImportance(a.label) - variantImportance(b.label)) || (a._index - b._index));
  }
  return {
    ...group,
    codes: codes.map(({ _index, ...rest }) => rest),
  };
}
