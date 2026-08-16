/**
 * RU → EN map for view-mode picker / daily-agg labels.
 * Keep in sync with backend seo_i18n._VIEW_MODE_LABEL_EN.
 */

const LABELS_EN = {
  'На конец периода': 'Period end',
  'Средняя за период': 'Period average',
  'К прошлому периоду': 'Vs previous period',
  'К соотв. периоду пред. года': 'Vs same period previous year',
  'Г/г': 'YoY',
  'Год к году': 'Year on year',
  'Кв/Кв': 'QoQ',
  'М/м': 'MoM',
  'Н/н': 'WoW',
  'По месяцам': 'Monthly',
  'По кварталам': 'Quarterly',
  'По годам': 'Annual',
  'По неделям': 'Weekly',
  'По дням': 'Daily',
  'Уровень': 'Level',
  'Индекс': 'Index',
  'За период': 'Over the period',
  'Помесячно': 'Monthly',
  'Ежеквартально': 'Quarterly',
  'Ежегодно': 'Annually',
  'Еженедельно': 'Weekly',
  'Нерегулярно': 'Irregular',
  'Сглаживание': 'Smoothing',
  '12М среднее': '12M average',
  'Уровень ставки': 'Rate level',
  'Ежедневно': 'Daily',
  'Понедельно': 'Weekly',
  'Поквартально': 'Quarterly',
  'Режим отображения': 'Display mode',
  'Частота отображения': 'Display frequency',
  'Годово': 'Annual',
  'среднее по неделям': 'weekly average',
  'среднее по месяцам': 'monthly average',
  'среднее по кварталам': 'quarterly average',
  'среднее по годам': 'annual average',
  'среднее за период': 'period average',
};

const SOURCE_EN = {
  Росстат: 'Rosstat',
  'Банк России': 'Bank of Russia',
  Минфин: 'Ministry of Finance',
  'Минфин России': 'Ministry of Finance',
  'Московская биржа': 'Moscow Exchange',
  Евростат: 'Eurostat',
  'Всемирный банк': 'World Bank',
  'Рыночные котировки': 'Market quotes',
};

export function localizeViewModeLabel(label, locale) {
  if (locale !== 'en' || label == null || label === '') return label;
  return LABELS_EN[label] || label;
}

export function localizeSource(source, locale) {
  if (locale !== 'en' || !source) return source;
  if (SOURCE_EN[source]) return SOURCE_EN[source];
  const entries = Object.entries(SOURCE_EN).sort((a, b) => b[0].length - a[0].length);
  let out = source;
  for (const [ru, en] of entries) {
    if (out.includes(ru)) out = out.split(ru).join(en);
  }
  return out;
}
