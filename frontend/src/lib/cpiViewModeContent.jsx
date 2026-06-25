import { Formula, ProdLimits } from '../components/MathFormula';
import { getHousingViewModeContent } from './housingViewModeContent';
import { getPpiViewModeContent } from './ppiViewModeContent';
import { getCbrTermSliceViewModeContent } from './cbrTermSliceRateContent';
import { getUnemploymentViewModeContent } from './unemploymentViewModeContent';

/**
 * Описание + методология для каждого режима CPI-графика.
 *
 * Редакционные правила: `.cursor/rules/methodology-language.mdc`
 * (состав × режим, description vs methodology, орфография, формулы).
 */

const CPI_SLICE = {
  cpi: {
    prices: 'потребительские цены',
    pricesGen: 'потребительских цен',
    ipcMonthly: 'месячных индексов ИПЦ',
    ipcMonthlyNom: 'месячные индексы ИПЦ',
    ipcFoot: 'индекс потребительских цен',
    indexLevel: 'общий уровень потребительских цен',
    weeklyBasket: 'всей потребительской корзине',
  },
  'cpi-food': {
    prices: 'цены на продовольственные товары',
    pricesGen: 'цен на продовольственные товары',
    ipcMonthly: 'месячных индексов ИПЦ на продовольственные товары',
    ipcMonthlyNom: 'месячные индексы ИПЦ на продовольственные товары',
    ipcFoot: 'индекс потребительских цен на продовольственные товары',
    indexLevel: 'уровень цен на продовольственные товары',
    weeklyBasket: 'продовольственным позициям корзины',
  },
  'cpi-nonfood': {
    prices: 'цены на непродовольственные товары',
    pricesGen: 'цен на непродовольственные товары',
    ipcMonthly: 'месячных индексов ИПЦ на непродовольственные товары',
    ipcMonthlyNom: 'месячные индексы ИПЦ на непродовольственные товары',
    ipcFoot: 'индекс потребительских цен на непродовольственные товары',
    indexLevel: 'уровень цен на непродовольственные товары',
    weeklyBasket: 'непродовольственным позициям корзины',
  },
  'cpi-services': {
    prices: 'цены на услуги',
    pricesGen: 'цен на услуги',
    ipcMonthly: 'месячных индексов ИПЦ на услуги',
    ipcMonthlyNom: 'месячные индексы ИПЦ на услуги',
    ipcFoot: 'индекс потребительских цен на услуги',
    indexLevel: 'уровень цен на услуги',
    weeklyBasket: 'позициям услуг в еженедельной корзине',
  },
};

function cpiSlice(code) {
  return CPI_SLICE[code] ?? CPI_SLICE.cpi;
}

/** Заголовок графика (H3 в IndicatorChart) — состав × режим. */
export function getCpiChartTitle(chartMode, code, urlMode = null) {
  const s = cpiSlice(code);
  const mode = urlMode ?? chartMode;
  if (mode === 'period-weekly') {
    return `Рост с начала месяца — ${s.prices} (%)`;
  }
  switch (chartMode) {
    case 'inflation': {
      const period = mode === 'inflation-quarter' ? ' (по кварталам)'
        : mode === 'inflation-year' ? ' (по годам)' : '';
      return code === 'cpi'
        ? `Инфляция к соответствующему периоду предыдущего года (все товары и услуги, %)${period}`
        : `Инфляция к соответствующему периоду предыдущего года (${s.prices}, %)${period}`;
    }
    case 'quarterly':
      return `Квартальная инфляция — ${s.prices} (%)`;
    case 'annual':
      return `Годовое изменение (г/г) — ${s.prices} (%)`;
    case 'period-monthly':
      return `Рост за месяц (по неделям) — ${s.prices} (%)`;
    case 'yoy':
      return `Год к году — ${s.prices} (%)`;
    case 'qoq':
      return `Квартал к кварталу — ${s.prices} (%)`;
    case 'weekly':
      return mode === 'period-weekly'
        ? `Рост с начала месяца — ${s.prices} (%)`
        : `Изменение ${s.pricesGen}, н/н (%)`;
    case 'index': {
      const period = mode === 'index-quarterly' ? ' на конец квартала'
        : mode === 'index-annual' ? ' на конец года' : '';
      return code === 'cpi'
        ? `Накопленный ИПЦ${period} (уровень, 2000=100)`
        : `Накопленный индекс${period} — ${s.prices} (2000=100)`;
    }
    case 'cpi':
      return `Изменение ${s.pricesGen}, м/м (%)`;
    default:
      return `Динамика ${s.pricesGen} (%)`;
  }
}

/** Заголовок таблицы истории — состав × режим. */
export function getCpiTableTitle(chartMode, code, urlMode = null) {
  const s = cpiSlice(code);
  const mode = urlMode ?? chartMode;
  if (mode === 'period-weekly') {
    return `Исторические данные — рост с начала месяца (${s.pricesGen})`;
  }
  switch (chartMode) {
    case 'inflation': {
      const period = mode === 'inflation-quarter' ? ' (по кварталам)'
        : mode === 'inflation-year' ? ' (по годам)' : '';
      return code === 'cpi'
        ? `Исторические данные — инфляция к соотв. периоду предыдущего года (все товары и услуги)${period}`
        : `Исторические данные — инфляция к соотв. периоду предыдущего года (${s.prices})${period}`;
    }
    case 'quarterly':
      return `Исторические данные — квартальная инфляция (${s.prices})`;
    case 'annual':
      return `Исторические данные — годовое изменение г/г (${s.prices})`;
    case 'period-monthly':
      return `Исторические данные — рост за месяц по неделям (${s.prices})`;
    case 'yoy':
      return `Исторические данные — год к году (${s.prices})`;
    case 'qoq':
      return `Исторические данные — квартал к кварталу (${s.prices})`;
    case 'weekly':
      return mode === 'period-weekly'
        ? `Исторические данные — рост с начала месяца (${s.pricesGen})`
        : `Исторические данные — недельное изменение (${s.pricesGen})`;
    case 'index': {
      const period = mode === 'index-quarterly' ? ' на конец квартала'
        : mode === 'index-annual' ? ' на конец года' : '';
      return code === 'cpi'
        ? `Исторические данные — накопленный ИПЦ${period} (2000=100)`
        : `Исторические данные — накопленный индекс${period} (${s.prices}, 2000=100)`;
    }
    case 'cpi':
      return `Исторические данные — изменение м/м (${s.pricesGen})`;
    default:
      return 'Исторические данные';
  }
}

const ANNUAL_INFLATION_FORMULA = (
  <Formula>
    <ProdLimits from="i=1" to="12" />
    (ИПЦ
    <sub>i</sub>
    {' / 100) × 100 − 100'}
  </Formula>
);

function inflationFootnote(ipcFoot) {
  return (
    <span className="block mt-2 text-text-tertiary normal-case tracking-normal text-[10px]">
      ИПЦ
      <sub>i</sub>
      {` — ${ipcFoot} за i-й месяц (% к предыдущему месяцу).`}
    </span>
  );
}

function buildInflation(code, period = null) {
  const s = cpiSlice(code);
  if (period === 'quarter') {
    return {
      description:
        `Инфляция к соответствующему кварталу предыдущего года: на сколько процентов ${s.prices} `
        + 'изменились по сравнению с тем же кварталом год назад. Помесячный годовой ряд укрупнён '
        + 'до квартальной частоты — показывается значение на конец каждого квартала.',
      methodology: (
        <>
          <span className="block mb-1">Формула (на конец квартала):</span>
          {ANNUAL_INFLATION_FORMULA}
          {inflationFootnote(s.ipcFoot)}
        </>
      ),
    };
  }
  if (period === 'year') {
    return {
      description:
        `Инфляция за год: на сколько процентов ${s.prices} изменились к концу года по сравнению `
        + 'с концом предыдущего года (декабрь к декабрю). Одна точка на каждый завершённый год.',
      methodology: (
        <>
          <span className="block mb-1">Формула (декабрь к декабрю):</span>
          {ANNUAL_INFLATION_FORMULA}
          {inflationFootnote(s.ipcFoot)}
        </>
      ),
    };
  }
  return {
    description:
      `Инфляция к соответствующему периоду предыдущего года: на сколько процентов ${s.prices} `
      + 'изменились по сравнению с тем же месяцем прошлого года. Рассчитывается как произведение 12 '
      + `последовательных ${s.ipcMonthly}, делённых на 100, минус 100%.`,
    methodology: (
      <>
        <span className="block mb-1">Формула:</span>
        {ANNUAL_INFLATION_FORMULA}
        {inflationFootnote(s.ipcFoot)}
      </>
    ),
  };
}

const WEEKLY = {
  description:
    'Недельный ИПЦ — изменение потребительских цен за неделю по данным Росстата. '
    + 'Публикуется еженедельно, является оперативным индикатором инфляционных процессов.',
  methodology:
    'Источник — еженедельные бюллетени Росстата «Об оценке индекса потребительских цен». '
    + 'Официальный агрегированный недельный ИПЦ по всей потребительской корзине. '
    + 'При значении 100 изменений цен нет.',
};

const WEEKLY_FOOD = {
  description:
    'Недельное изменение цен на продовольственные товары — оперативный срез '
    + 'по товарной корзине Росстата, сопоставимый с месячным продовольственным ИПЦ.',
  methodology:
    'Рассчитывается как взвешенное среднее еженедельных индексов по продовольственным '
    + 'позициям корзины (веса — по структуре потребительских расходов Росстата). '
    + 'Отдельного официального недельного бюллетеня по продовольствию Росстат не публикует; '
    + 'для общей корзины используются бюллетени «Об оценке индекса потребительских цен».',
};

const WEEKLY_NONFOOD = {
  description:
    'Недельное изменение цен на непродовольственные товары — оперативный срез '
    + 'по товарной корзине Росстата, сопоставимый с месячным ИПЦ на непродовольственные товары.',
  methodology:
    'Рассчитывается как взвешенное среднее еженедельных индексов по непродовольственным '
    + 'позициям корзины (веса — по структуре потребительских расходов Росстата). '
    + 'Отдельного официального недельного бюллетеня по этой группе Росстат не публикует.',
};

const WEEKLY_SERVICES = {
  description:
    'Недельное изменение цен на услуги — оперативный срез по позициям услуг '
    + 'в еженедельной корзине Росстата, сопоставимый с месячным ИПЦ на услуги.',
  methodology:
    'Рассчитывается как взвешенное среднее еженедельных индексов по услугам '
    + '(веса — по структуре потребительских расходов Росстата). '
    + 'Отдельного официального недельного бюллетеня только по услугам Росстат не публикует.',
};

const WEEKLY_BY_CODE = {
  cpi: WEEKLY,
  'cpi-food': WEEKLY_FOOD,
  'cpi-nonfood': WEEKLY_NONFOOD,
  'cpi-services': WEEKLY_SERVICES,
};

function buildStepMonthly(code) {
  const s = cpiSlice(code);
  return {
    description:
      `Месячное изменение (м/м) — на сколько процентов ${s.prices} изменились `
      + 'по сравнению с предыдущим месяцем. Положительное значение — рост, '
      + 'отрицательное — снижение.',
    methodology:
      `Формула: ИПЦᵢ − 100, где ИПЦᵢ — ${s.ipcFoot} за i-й месяц `
      + `в % к предыдущему месяцу. Источник — ${s.ipcMonthlyNom} Росстата.`,
  };
}

function buildStepWeekly(code) {
  const s = cpiSlice(code);
  const weekly = WEEKLY_BY_CODE[code] ?? WEEKLY;
  return {
    description:
      `Недельное изменение (н/н) — на сколько процентов ${s.prices} изменились `
      + 'по сравнению с предыдущей неделей. Положительное значение — рост, '
      + 'отрицательное — снижение.',
    methodology: weekly.methodology,
  };
}

function buildPeriodWeekly(code) {
  const s = cpiSlice(code);
  return {
    description:
      `Накопленный прирост ${s.pricesGen} с начала календарного месяца `
      + 'по состоянию на каждую отчётную неделю. Отличается от «н/н», '
      + 'где показано только изменение к предыдущей неделе.',
    methodology:
      'Формула на дату недели t в месяце M: (∏ недельных ИПЦᵢ / 100) × 100 − 100, '
      + 'где i — все недели месяца M с первой по t включительно. '
      + 'Источник недельных индексов — еженедельные оценки Росстата.',
  };
}

function buildPeriodMonthly(code) {
  const s = cpiSlice(code);
  return {
    description:
      `Рост ${s.pricesGen} за календарный месяц по оперативным недельным `
      + 'оценкам: перемножаются все недельные индексы, относящиеся к этому месяцу. '
      + 'Может немного отличаться от официального месячного индекса (режим «м/м»), '
      + 'который публикуется отдельно.',
    methodology:
      'Формула за месяц M: (∏ недельных ИПЦᵢ / 100) × 100 − 100, где i — все '
      + `недели календарного месяца M по срезу «${s.prices}». Точка привязана `
      + 'к последней неделе месяца.',
  };
}

function buildYoy(code) {
  const s = cpiSlice(code);
  return {
    description:
      `Годовое изменение (г/г) — на сколько процентов ${s.prices} изменились `
      + 'по сравнению с предыдущим годом. Положительное значение — рост, '
      + 'отрицательное — снижение. Считается по календарным годам — '
      + 'декабрь к декабрю, одна точка на каждый завершённый год.',
    methodology: (
      <>
        <span className="block mb-1">Формула (за календарный год, январь–декабрь):</span>
        {ANNUAL_INFLATION_FORMULA}
        <span className="block mt-2 text-text-tertiary normal-case tracking-normal text-[10px]">
          ИПЦ
          <sub>i</sub>
          {` — ${s.ipcFoot} за i-й месяц года (% к предыдущему месяцу). `}
          Прогноз — то же произведение по точкам месячного прогноза.
        </span>
      </>
    ),
  };
}

function buildQoq(code) {
  const s = cpiSlice(code);
  return {
    description:
      `Квартальное изменение (кв/кв) — на сколько процентов ${s.prices} изменились `
      + 'по сравнению с предыдущим кварталом. Положительное значение — рост, '
      + 'отрицательное — снижение.',
    methodology:
      'Формула на концах кварталов: (УРОВЕНЬ конец Q / УРОВЕНЬ конец Q−1 − 1) × 100, '
      + 'где УРОВЕНЬ — накопленный индекс цен, построенный из '
      + `${s.ipcMonthly}.`,
  };
}

function buildIndex(code, bucket = null) {
  const s = cpiSlice(code);
  const intro = code === 'cpi'
    ? 'Накопленный индекс потребительских цен — общий уровень потребительских цен относительно базы.'
    : `Накопленный индекс отражает ${s.indexLevel} относительно базы.`;
  if (bucket) {
    const periodWord = bucket === 'year' ? 'года' : 'квартала';
    const periodAdj = bucket === 'year' ? 'годовая' : 'квартальная';
    return {
      description:
        `${intro} Показана ${periodAdj} версия: одна точка — значение `
        + `накопленного индекса на конец каждого завершённого ${periodWord}. За базу принят `
        + 'январь 2000 года (100 = уровень цен в январе 2000). Удобно сравнивать '
        + `уровень ${s.pricesGen} по ${bucket === 'year' ? 'годам' : 'кварталам'} `
        + 'без помесячного шума.',
      methodology:
        `Сначала строится месячный накопленный индекс ИНДЕКСₜ = 100 × (ИПЦ₁/100) × `
        + `… × (ИПЦₜ/100), где ИПЦᵢ — месячный ${s.ipcFoot} к предыдущему месяцу. `
        + `Затем берётся последнее значение каждого завершённого ${periodWord}. История `
        + 'охватывает весь доступный ряд с 1991 года; значения до января 2000 года '
        + 'заметно меньше 100 — уровень цен тогда был во много раз ниже базы. '
        + 'Прогноз — продолжение накопленной кривой по месячному прогнозу, точки '
        + `на конец каждого завершённого ${periodWord} горизонта.`,
    };
  }
  return {
    description:
      `${intro} За базу принят январь 2000 года `
      + '(100 = уровень цен в январе 2000). Каждое значение получено цепным произведением '
      + `${s.ipcMonthly} к этой базе. Кривая показывает, как с 1991 года изменились `
      + `${s.prices}.`,
    methodology:
      `Формула: ИНДЕКСₜ = 100 × (ИПЦ₁/100) × (ИПЦ₂/100) × … × (ИПЦₜ/100), где `
      + `ИПЦᵢ — месячный ${s.ipcFoot} к предыдущему месяцу. История охватывает весь `
      + 'доступный ряд с 1991 года; значения до января 2000 года заметно меньше 100 — '
      + 'уровень цен тогда был во много раз ниже базы. Прогноз — '
      + `продолжение накопленной кривой по 12-месячному прогнозу ${s.ipcMonthly}.`,
  };
}

/**
 * Вернуть пару (description, methodology) для текущего режима графика.
 *
 * Все CPI-specific блоки включаются **только** при `isPriceCategory === true`.
 * Тексты зависят от `indicator.code` (состав корзины) и режима — см. правило
 * methodology-language.mdc. Не-CPI индикаторы берут тексты из полей индикатора в БД.
 */
export function getViewModeContent({
  chartMode, safeViewMode, isPriceCategory, isHousingFamily, isPpiFamily,
  isCbrTermSliceFamily,
  isUnemploymentFamily,
  indicator,
}) {
  if (isUnemploymentFamily) {
    return getUnemploymentViewModeContent({ chartMode });
  }
  if (isPpiFamily) {
    return getPpiViewModeContent({ chartMode, safeViewMode, indicator });
  }
  if (isCbrTermSliceFamily) {
    return getCbrTermSliceViewModeContent({ chartMode, indicator });
  }
  if (isHousingFamily) {
    return getHousingViewModeContent({ chartMode, safeViewMode, indicator });
  }
  if (isPriceCategory) {
    const code = indicator?.code ?? 'cpi';
    if (chartMode === 'inflation') {
      if (safeViewMode === 'inflation-quarter') return buildInflation(code, 'quarter');
      if (safeViewMode === 'inflation-year') return buildInflation(code, 'year');
      return buildInflation(code);
    }
    if (safeViewMode === 'period-weekly') return buildPeriodWeekly(code);
    if (safeViewMode === 'period-monthly') return buildPeriodMonthly(code);
    if (safeViewMode === 'step-weekly') return buildStepWeekly(code);
    if (safeViewMode === 'step-monthly') return buildStepMonthly(code);
    if (safeViewMode === 'yoy') return buildYoy(code);
    if (safeViewMode === 'qoq') return buildQoq(code);
    if (safeViewMode === 'index') return buildIndex(code);
    if (safeViewMode === 'index-quarterly') return buildIndex(code, 'quarter');
    if (safeViewMode === 'index-annual') return buildIndex(code, 'year');
    // совместимость со старым dataMode без url-режима
    if (chartMode === 'weekly') return WEEKLY_BY_CODE[code] ?? WEEKLY;
    if (chartMode === 'cpi') return buildStepMonthly(code);
  }
  return {
    description: indicator?.description ?? '',
    methodology: indicator?.methodology ?? '',
  };
}
