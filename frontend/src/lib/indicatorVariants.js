/**
 * Группы взаимосвязанных индикаторов, между которыми пользователь может
 * переключаться pill-ссылками («Состав ИПЦ», «Режим ВВП», варианты ППИ,
 * первичное/вторичное жильё). Один индикатор принадлежит максимум одной
 * группе. Если код не входит ни в одну — pill-блок не показывается.
 *
 * Вторичные коды (YoY, QoQ, квартальные агрегаты) скрыты из листинга категории
 * через INDICATOR_HIDDEN_FROM_LISTING в backend/app/data/indicator_seo.py.
 */
export const VARIANT_GROUPS = [
  {
    label: 'Состав индекса потребительских цен',
    codes: [
      { code: 'cpi', label: 'Все товары и услуги' },
      { code: 'cpi-food', label: 'Продовольствие' },
      { code: 'cpi-nonfood', label: 'Непродовольственные' },
      { code: 'cpi-services', label: 'Услуги' },
    ],
  },
  {
    label: 'Номинальный ВВП',
    codes: [
      { code: 'gdp-nominal', label: 'Поквартально' },
      { code: 'gdp-qoq', label: 'Кв/кв' },
      { code: 'gdp-yoy', label: 'Г/г' },
      { code: 'gdp-nominal-annual', label: 'Годовой' },
    ],
  },
  {
    label: 'Реальный ВВП',
    codes: [
      { code: 'gdp-real', label: 'Поквартально' },
      { code: 'gdp-real-qoq', label: 'Кв/кв' },
      { code: 'gdp-real-yoy', label: 'Г/г' },
      { code: 'gdp-real-annual', label: 'Годовой' },
    ],
  },
  {
    label: 'Режим индекса цен производителей',
    codes: [
      { code: 'ppi', label: 'Помесячно' },
      { code: 'ppi-yoy', label: 'Год к году' },
      { code: 'ppi-annual', label: 'Годовая (декабрь к декабрю)' },
    ],
  },
  {
    label: 'Индекс промышленного производства',
    codes: [
      { code: 'ipi-yoy', label: 'Год к году' },
      { code: 'ipi', label: 'Помесячно' },
    ],
  },
  {
    label: 'Уровень безработицы',
    codes: [
      { code: 'unemployment', label: 'Помесячно' },
      { code: 'unemployment-quarterly', label: 'Среднее за квартал' },
      { code: 'unemployment-annual', label: 'Скользящее 12 мес.' },
    ],
  },
  {
    label: 'Средняя заработная плата',
    codes: [
      { code: 'wages-nominal', label: 'Номинальная' },
      { code: 'wages-yoy', label: 'Год к году' },
    ],
  },
  // Phase 1 (звонок 2026-05-22): trade-семьи (exports / imports / current-account)
  // переехали с VariantGroupPicker (отдельные URL'ы для каждого режима) на
  // ViewModePicker (in-page ?mode=yoy|qoq). См. `lib/tradeViewModes.js` и
  // `pages/IndicatorDetail.jsx::isTrade`. Эти записи удалены сознательно —
  // дублирующие pills'ы над FrequencySwitcher.
  {
    label: 'Первичное жильё',
    codes: [
      { code: 'housing-price-primary', label: 'Индекс' },
      { code: 'housing-yoy-primary', label: 'Год к году' },
    ],
  },
  {
    label: 'Вторичное жильё',
    codes: [
      { code: 'housing-price-secondary', label: 'Индекс' },
      { code: 'housing-yoy-secondary', label: 'Год к году' },
    ],
  },
  {
    label: 'Ставки по кредитам юридическим лицам',
    codes: [
      { code: 'credit-rate-corp-short', label: 'До 1 года' },
      { code: 'credit-rate-corp-1to3y', label: 'От 1 до 3 лет' },
      { code: 'credit-rate-corp-over3y', label: 'Свыше 3 лет' },
    ],
  },
  {
    label: 'Ставки по кредитам физическим лицам',
    codes: [
      { code: 'credit-rate-ind-short', label: 'До 1 года' },
      { code: 'credit-rate-ind-1to3y', label: 'От 1 до 3 лет' },
      { code: 'credit-rate-ind-over3y', label: 'Свыше 3 лет' },
    ],
  },
  {
    label: 'Ставки по вкладам физических лиц',
    codes: [
      { code: 'deposit-rate', label: 'До 1 года' },
      { code: 'deposit-rate-medium', label: 'От 1 до 3 лет' },
      { code: 'deposit-rate-long', label: 'Свыше 3 лет' },
    ],
  },
];

export function findVariantGroup(code) {
  return VARIANT_GROUPS.find((group) => group.codes.some((item) => item.code === code));
}

/** Все коды, входящие в variant-группы (для тестов и аудита). */
export function allVariantMemberCodes() {
  return VARIANT_GROUPS.flatMap((g) => g.codes.map((c) => c.code));
}
