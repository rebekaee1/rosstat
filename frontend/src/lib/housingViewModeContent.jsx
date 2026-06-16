/**
 * Описание и методология: рынок (первичное/вторичное) × режим (кв/кв, г/г, индекс).
 * Правила: .cursor/rules/methodology-language.mdc
 */

const SLICE = {
  'housing-price-primary': {
    marketShort: 'первичное жильё',
    marketGen: 'первичного рынка жилья',
    marketWhat: 'квартиры в новостройках',
    sample: 'застройщиков и договоров долевого участия',
    drivers: 'себестоимость строительства, проектное финансирование, льготная ипотека и темпы ввода жилья',
  },
  'housing-price-secondary': {
    marketShort: 'вторичное жильё',
    marketGen: 'вторичного рынка жилья',
    marketWhat: 'квартиры на вторичном рынке',
    sample: 'сделок между физическими лицами и риелторских наблюдений',
    drivers: 'предложение на вторичке, ипотечные условия, миграция спроса из первички и доходы домохозяйств',
  },
};

function slice(code) {
  return SLICE[code] ?? SLICE['housing-price-primary'];
}

function indexPeriodSuffix(safeViewMode) {
  return safeViewMode === 'index-annual' ? ' на конец года' : '';
}

export function getHousingChartTitle(chartMode, code, safeViewMode) {
  const s = slice(code);
  switch (chartMode) {
    case 'yoy':
      return `К соотв. периоду пред. года — ${s.marketShort} (%)`;
    case 'annual':
      return `Г/г — ${s.marketShort} (%)`;
    case 'qoq':
      return `Кв/Кв — ${s.marketShort} (%)`;
    case 'index':
      return `Индекс цен — ${s.marketShort} (2010=100)${indexPeriodSuffix(safeViewMode)}`;
    default:
      return `Динамика цен — ${s.marketShort}`;
  }
}

export function getHousingTableTitle(chartMode, code, safeViewMode) {
  const s = slice(code);
  switch (chartMode) {
    case 'yoy':
      return `Исторические данные — к соотв. периоду пред. года (${s.marketGen})`;
    case 'annual':
      return `Исторические данные — г/г по годам (${s.marketGen})`;
    case 'qoq':
      return `Исторические данные — кв/кв (${s.marketGen})`;
    case 'index':
      return safeViewMode === 'index-annual'
        ? `Исторические данные — индекс на конец года (${s.marketWhat}, 2010=100)`
        : `Исторические данные — индекс (${s.marketWhat}, 2010=100)`;
    default:
      return `Исторические данные — ${s.marketGen}`;
  }
}

function contentYoy(code) {
  const s = slice(code);
  return {
    description:
      `Темп изменения цен на ${s.marketWhat} по сравнению с тем же кварталом `
      + 'предыдущего года, в процентах. Четыре точки в год — каждый квартал '
      + 'сопоставляется с аналогичным кварталом годом ранее.',
    methodology:
      'Режим «к соответствующему периоду предыдущего года»: показывает, насколько '
      + `изменился квартальный индекс цен на ${s.marketGen} относительно того же `
      + 'квартала прошлого года. Ряд строится по накопленному индексу с базой '
      + '2010 = 100, который Росстат обновляет ежеквартально. Положительное '
      + 'значение — рост цен, отрицательное — снижение.',
  };
}

function contentAnnual(code) {
  const s = slice(code);
  return {
    description:
      `Годовое изменение цен на ${s.marketWhat} «год к году»: уровень цен на конец `
      + 'года к уровню на конец предыдущего года, в процентах. Одна точка на каждый '
      + 'завершённый год.',
    methodology:
      'Режим «к прошлому периоду — г/г»: годовой прирост цен на '
      + `${s.marketGen}, рассчитанный как отношение индекса на конец года к значению `
      + 'на конец предыдущего года. В отличие от режима «к соответствующему периоду '
      + 'предыдущего года» (поквартальное сравнение, четыре точки в год), здесь — '
      + 'одна точка на год. Положительное значение — рост цен, отрицательное — снижение.',
  };
}

function contentQoq(code) {
  const s = slice(code);
  return {
    description:
      `Темп изменения цен на ${s.marketWhat} по сравнению с предыдущим `
      + 'кварталом (кв/кв), в процентах.',
    methodology:
      'Режим «к прошлому периоду — кв/кв»: прирост к непосредственно предшествующему '
      +       'кварталу. В ежемесячном макроэкономическом обзоре Росстата для '
      + `${s.marketGen} публикуются квартальные приросты в процентах; по ним пересчитывается `
      + `квартальный индекс. Выборка — ${s.sample}; на графике показан восстановленный `
      + 'квартальный ряд, согласованный с официальной публикацией.',
  };
}

function contentIndex(code, safeViewMode) {
  const s = slice(code);
  const primaryExtra = code === 'housing-price-primary'
    ? ' Учитываются сделки по договорам долевого участия в новостройках; переуступки и котлованы в официальную выборку не входят.'
  : ' Отражает сделки с квартирами в существующем жилищном фонде, а не цены застройщиков.';
  if (safeViewMode === 'index-annual') {
    return {
      description:
        `Уровень цен на ${s.marketWhat} на конец каждого года в базе 2010 = 100. `
        + 'Режим укрупняет квартальный ряд до годовой частоты: показывается значение '
        + 'последнего квартала года, удобно для сравнения долгосрочной динамики.',
      methodology:
        'Режим «Индекс — по годам»: квартальный уровень цен, приведённый к базе '
        + '2010 = 100, прорежённый до значения на конец года (последний квартал). '
        + `Росстат взвешивает наблюдения по регионам и характеристикам жилья.${primaryExtra} `
        + `На динамику уровня влияют ${s.drivers}.`,
    };
  }
  return {
    description:
      `Накопленный индекс цен на ${s.marketWhat} в базе 2010 года = 100: `
      + 'показывает, во сколько раз изменился уровень цен с опорного года.',
    methodology:
      'Режим «Индекс»: квартальный уровень цен, приведённый к базе 2010 = 100. '
      + 'Росстат взвешивает наблюдения по регионам и характеристикам жилья; '
      + `история с 1998 года восстановлена по архивным таблицам.${primaryExtra} `
      + `На динамику уровня влияют ${s.drivers}.`,
  };
}

export function getHousingViewModeContent({ chartMode, safeViewMode, indicator }) {
  const code = indicator?.code ?? 'housing-price-primary';
  if (chartMode === 'yoy') return contentYoy(code);
  if (chartMode === 'annual') return contentAnnual(code);
  if (chartMode === 'qoq') return contentQoq(code);
  if (chartMode === 'index') return contentIndex(code, safeViewMode);
  return {
    description: indicator?.description ?? '',
    methodology: indicator?.methodology ?? '',
  };
}
