/**
 * Группы взаимосвязанных индикаторов, между которыми пользователь может
 * переключаться pill-ссылками («Состав ИПЦ», «Режим ВВП», варианты ППИ,
 * первичное/вторичное жильё). Один индикатор принадлежит максимум одной
 * группе. Если код не входит ни в одну — pill-блок не показывается.
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
    label: 'Режим ВВП',
    codes: [
      { code: 'gdp-nominal', label: 'Номинальный' },
      { code: 'gdp-real', label: 'Реальный (поквартально)' },
      { code: 'gdp-real-annual', label: 'Реальный (годовая)' },
      { code: 'gdp-yoy', label: 'Год к году' },
      { code: 'gdp-qoq', label: 'Квартал к кварталу' },
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
