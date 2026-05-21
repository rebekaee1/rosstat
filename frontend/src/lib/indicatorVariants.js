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
  {
    label: 'Экспорт товаров',
    codes: [
      { code: 'exports', label: 'Уровень' },
      { code: 'exports-yoy', label: 'Год к году' },
      { code: 'exports-qoq', label: 'Квартал к кварталу' },
    ],
  },
  {
    label: 'Импорт товаров',
    codes: [
      { code: 'imports', label: 'Уровень' },
      { code: 'imports-yoy', label: 'Год к году' },
      { code: 'imports-qoq', label: 'Квартал к кварталу' },
    ],
  },
  {
    label: 'Сальдо текущего счёта',
    codes: [
      { code: 'current-account', label: 'Уровень' },
      { code: 'current-account-yoy', label: 'Год к году' },
    ],
  },
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
];

export function findVariantGroup(code) {
  return VARIANT_GROUPS.find((group) => group.codes.some((item) => item.code === code));
}

/** Все коды, входящие в variant-группы (для тестов и аудита). */
export function allVariantMemberCodes() {
  return VARIANT_GROUPS.flatMap((g) => g.codes.map((c) => c.code));
}
