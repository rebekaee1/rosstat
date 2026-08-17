/**
 * RU → EN map for view-mode picker / daily-agg labels.
 * Keep in sync with backend seo_i18n._VIEW_MODE_LABEL_EN.
 */

const LABELS_EN = {
  'На конец периода': 'Period end',
  'Средняя за период': 'Period average',
  'К прошлому периоду': 'Vs previous period',
  'К году': 'Year on year',
  'К соотв. периоду пред. года': 'Vs same period previous year',
  'Г/г': 'YoY',
  'Год к году': 'Year on year',
  'Кв/Кв': 'QoQ',
  'Кв/кв': 'QoQ',
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
  'к пред. кварталу': 'vs prev. quarter',
  'к пред. году': 'vs prev. year',
  'к пред. неделе': 'vs prev. week',
  'к пред. дню': 'vs prev. day',
  'к пред. значению': 'vs prev. value',
  'к пред. месяцу': 'vs prev. month',
  'Предыдущий квартал': 'Previous quarter',
  'Предыдущий год': 'Previous year',
  'Предыдущая неделя': 'Previous week',
  'Предыдущий день': 'Previous day',
  'Предыдущий месяц': 'Previous month',
  'Предыдущее значение': 'Previous value',
  'Текущее значение': 'Current value',
  'Абсолютный максимум': 'All-time high',
  'Среднее значение': 'Average',
  'Недельные': 'Weekly',
  'Месячные': 'Monthly',
  'Квартальные': 'Quarterly',
  'Годовые': 'Annual',
  'К прошлому году': 'Vs previous year',
  'Значение': 'Value',
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
  'Статистическое управление Канады': 'Statistics Canada',
  'Банк Канады': 'Bank of Canada',
  'Австралийское бюро статистики': 'Australian Bureau of Statistics',
  'Резервный банк Австралии': 'Reserve Bank of Australia',
  'Управление национальной статистики Великобритании': 'Office for National Statistics',
  'Банк Англии': 'Bank of England',
  'Федеральный резервный банк Сент-Луиса': 'Federal Reserve Bank of St. Louis',
  'Бюро трудовой статистики США': 'U.S. Bureau of Labor Statistics',
  'Бюро экономического анализа США': 'U.S. Bureau of Economic Analysis',
  'Банк Японии': 'Bank of Japan',
  'Статистическое бюро Японии': 'Statistics Bureau of Japan',
  'Банк Кореи': 'Bank of Korea',
  'Банк Бразилии': 'Central Bank of Brazil',
  'Банк Мексики': 'Bank of Mexico',
  'Национальное статистическое бюро Китая': 'National Bureau of Statistics of China',
  'Китайская система валютных торгов': 'China Foreign Exchange Trade System',
  'Министерство статистики и программной реализации Индии':
    'Ministry of Statistics and Programme Implementation',
  'Резервный банк Индии': 'Reserve Bank of India',
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
