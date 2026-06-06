import { Formula, ProdLimits } from '../components/MathFormula';
import { getHousingViewModeContent } from './housingViewModeContent';
import { getPpiViewModeContent } from './ppiViewModeContent';
import { getAutoLoanViewModeContent, isAutoLoanFamily } from './autoLoanViewModeContent';
import { getMortgageViewModeContent, isMortgageFamily } from './mortgageRateViewModeContent';
import { getCbrTermSliceViewModeContent, isCbrTermSliceFamily } from './cbrTermSliceRateContent';
import { getKeyRateViewModeContent, isKeyRateFamily } from './keyRateViewModeContent';
import { getRuoniaViewModeContent, isRuoniaFamily } from './ruoniaViewModeContent';
import { getBtcUsdViewModeContent, isBtcUsdFamily } from './btcUsdViewModeContent';
import { getBrentViewModeContent, isBrentFamily } from './brentViewModeContent';
import { getGoldPriceViewModeContent, isGoldPriceFamily } from './goldPriceViewModeContent';
import { getCnyRubViewModeContent, isCnyRubFamily } from './cnyRubViewModeContent';
import { getBudgetViewModeContent, isBudgetFamily } from './budgetViewModeContent';
import { getBankCreditViewModeContent, isBankCreditFamily } from './bankCreditViewModeContent';
import {
  getHouseholdFinanceViewModeContent,
  isHouseholdFinanceFamily,
} from './householdFinanceViewModeContent';
import {
  getExternalDebtViewModeContent,
  isExternalDebtFamily,
} from './externalDebtViewModeContent';
import {
  getInternationalReservesViewModeContent,
  isInternationalReservesFamily,
} from './internationalReservesViewModeContent';
import {
  getMonetaryMassViewModeContent,
  isMonetaryMassFamily,
} from './monetaryMassViewModeContent';
import {
  getLaborMarketViewModeContent,
  isLaborMarketFamily,
} from './laborMarketViewModeContent';
import {
  getUnemploymentViewModeContent,
  isUnemploymentFamily,
} from './unemploymentViewModeContent';
import {
  getWagesNominalViewModeContent,
  isWagesNominalFamily,
} from './wagesNominalViewModeContent';
import {
  getGdpNominalViewModeContent,
  isGdpNominalFamily,
} from './gdpNominalViewModeContent';
import {
  getGdpRealViewModeContent,
  isGdpRealFamily,
} from './gdpRealViewModeContent';
import {
  getGdpUseViewModeContent,
  isGdpUseFamily,
} from './gdpUseViewModeContent';
import { getEurRubViewModeContent, isEurRubFamily } from './eurRubViewModeContent';
import { getUsdRubViewModeContent, isUsdRubFamily } from './usdRubViewModeContent';

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
    case 'inflation':
      return code === 'cpi'
        ? 'Инфляция за 12 мес. (все товары и услуги, %)'
        : `Инфляция за 12 мес. (${s.prices}, %)`;
    case 'quarterly':
      return `Квартальная инфляция — ${s.prices} (%)`;
    case 'annual':
      return `Годовая инфляция — ${s.prices} (%)`;
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
    case 'inflation':
      return code === 'cpi'
        ? 'Исторические данные — инфляция 12 мес. (все товары и услуги)'
        : `Исторические данные — инфляция 12 мес. (${s.prices})`;
    case 'quarterly':
      return `Исторические данные — квартальная инфляция (${s.prices})`;
    case 'annual':
      return `Исторические данные — годовая инфляция (${s.prices})`;
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

const QUARTERLY_INFLATION_FORMULA = (
  <Formula>
    {'(ИПЦ'}<sub>1</sub>{' / 100) × (ИПЦ'}<sub>2</sub>{' / 100) × (ИПЦ'}<sub>3</sub>{' / 100) × 100 − 100'}
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

function buildInflation(code) {
  const s = cpiSlice(code);
  return {
    description:
      'Накопленная инфляция за скользящие 12 месяцев показывает, на сколько процентов '
      + `выросли ${s.prices} за этот период. Рассчитывается как произведение 12 `
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

function buildQuarterly(code) {
  const s = cpiSlice(code);
  return {
    description:
      'Квартальная инфляция показывает, на сколько процентов выросли '
      + `${s.prices} за квартал (3 месяца). Рассчитывается как произведение 3 последовательных `
      + `${s.ipcMonthly}, делённых на 100, минус 100%.`,
    methodology: (
      <>
        <span className="block mb-1">Формула:</span>
        {QUARTERLY_INFLATION_FORMULA}
        {inflationFootnote(s.ipcFoot)}
      </>
    ),
  };
}

function buildAnnual(code) {
  const s = cpiSlice(code);
  return {
    description:
      'Годовая инфляция «декабрь к декабрю» — стандарт ЦБ и Росстата. '
      + 'Одна точка на каждый завершённый календарный год: рассчитывается как '
      + `произведение 12 ${s.ipcMonthly} внутри года (январь–декабрь), `
      + 'делённых на 100, минус 100%. Прогноз — то же произведение по 12 точкам '
      + `месячного прогноза ${s.ipcMonthlyNom}.`,
    methodology: (
      <>
        <span className="block mb-1">Формула (за календарный год Y, январь–декабрь):</span>
        {ANNUAL_INFLATION_FORMULA}
        <span className="block mt-2 text-text-tertiary normal-case tracking-normal text-[10px]">
          ИПЦ
          <sub>i</sub>
          {` — ${s.ipcFoot} за i-й месяц года Y (% к предыдущему месяцу).`}
        </span>
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
      `Изменение ${s.pricesGen} неделя к неделе (н/н) по оперативному `
      + 'еженедельному ряду Росстата.',
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
      `Изменение ${s.pricesGen} по сравнению с тем же месяцем прошлого года (г/г). `
      + 'Не совпадает со скользящей инфляцией за 12 месяцев и с годовой '
      + 'инфляцией «декабрь к декабрю».',
    methodology:
      'Формула: (УРОВЕНЬₜ / УРОВЕНЬₜ₋₁₂ − 1) × 100, где УРОВЕНЬ — накопленный '
      + `индекс цен с января 2000 года (база 100), построенный из ${s.ipcMonthly} `
      + 'к предыдущему месяцу.',
  };
}

function buildQoq(code) {
  const s = cpiSlice(code);
  return {
    description:
      `Изменение ${s.pricesGen} к концу предыдущего квартала (к/к). `
      + 'Отличается от «квартальной инфляции», которая показывает рост '
      + 'внутри квартала (произведение трёх месяцев).',
    methodology:
      'Формула на концах кварталов: (УРОВЕНЬконец Q / УРОВЕНЬконец Q−1 − 1) × 100, '
      + 'где УРОВЕНЬ — накопленный индекс с января 2000 года из '
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
        + `накопленного индекса на конец каждого ${periodWord}. За базу принят `
        + 'январь 2000 года (100 = уровень цен в январе 2000). Удобно сравнивать '
        + `уровень ${s.pricesGen} по ${bucket === 'year' ? 'годам' : 'кварталам'} `
        + 'без помесячного шума.',
      methodology:
        `Сначала строится месячный накопленный индекс ИНДЕКСₜ = 100 × (ИПЦ₁/100) × `
        + `… × (ИПЦₜ/100), где ИПЦᵢ — месячный ${s.ipcFoot} к предыдущему месяцу. `
        + `Затем берётся последнее значение каждого ${periodWord}. История 1991–1999 `
        + 'не включена. На этом режиме прогноз не отображается.',
    };
  }
  return {
    description:
      `${intro} За базу принят январь 2000 года `
      + '(100 = уровень цен в январе 2000). Каждое значение получено цепным произведением '
      + `${s.ipcMonthly} к этой базе. Кривая показывает, как с 2000 года изменились `
      + `${s.prices}.`,
    methodology:
      `Формула: ИНДЕКСₜ = 100 × (ИПЦ₁/100) × (ИПЦ₂/100) × … × (ИПЦₜ/100), где `
      + `ИПЦᵢ — месячный ${s.ipcFoot} к предыдущему месяцу. История 1991–1999 не `
      + 'включена: гиперинфляция первой половины 90-х искажает шкалу. Прогноз — '
      + `продолжение накопленной кривой по 12-месячному прогнозу ${s.ipcMonthlyNom}.`,
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
  isAutoLoanFamily, isMortgageFamily, isCbrTermSliceFamily, isKeyRateFamily, isRuoniaFamily,
  isBtcUsdFamily, isBrentFamily, isGoldPriceFamily, isUsdRubFamily, isEurRubFamily, isCnyRubFamily,
  isBudgetFamily,
  isBankCreditFamily,
  isHouseholdFinanceFamily,
  isMonetaryMassFamily,
  isLaborMarketFamily,
  isUnemploymentFamily,
  isWagesNominalFamily,
  isGdpNominalFamily,
  isGdpRealFamily,
  isGdpUseFamily,
  isInternationalReservesFamily,
  isExternalDebtFamily,
  indicator,
}) {
  if (isGdpUseFamily) {
    return getGdpUseViewModeContent({ chartMode, indicatorCode: indicator?.code });
  }
  if (isGdpNominalFamily) {
    return getGdpNominalViewModeContent({ chartMode });
  }
  if (isGdpRealFamily) {
    return getGdpRealViewModeContent({ chartMode });
  }
  if (isWagesNominalFamily) {
    return getWagesNominalViewModeContent({ chartMode });
  }
  if (isUnemploymentFamily) {
    return getUnemploymentViewModeContent({ chartMode });
  }
  if (isLaborMarketFamily) {
    return getLaborMarketViewModeContent({ chartMode, indicatorCode: indicator?.code });
  }
  if (isExternalDebtFamily) {
    return getExternalDebtViewModeContent({ chartMode });
  }
  if (isInternationalReservesFamily) {
    return getInternationalReservesViewModeContent({ chartMode });
  }
  if (isMonetaryMassFamily) {
    return getMonetaryMassViewModeContent({ chartMode, indicatorCode: indicator?.code });
  }
  if (isHouseholdFinanceFamily) {
    return getHouseholdFinanceViewModeContent({ chartMode, indicatorCode: indicator?.code });
  }
  if (isBankCreditFamily) {
    return getBankCreditViewModeContent({ chartMode });
  }
  if (isBudgetFamily) {
    return getBudgetViewModeContent({ chartMode, indicatorCode: indicator?.code });
  }
  if (isUsdRubFamily) {
    return getUsdRubViewModeContent({ chartMode });
  }
  if (isEurRubFamily) {
    return getEurRubViewModeContent({ chartMode });
  }
  if (isCnyRubFamily) {
    return getCnyRubViewModeContent({ chartMode });
  }
  if (isBrentFamily) {
    return getBrentViewModeContent({ chartMode });
  }
  if (isGoldPriceFamily) {
    return getGoldPriceViewModeContent({ chartMode });
  }
  if (isBtcUsdFamily) {
    return getBtcUsdViewModeContent({ chartMode });
  }
  if (isRuoniaFamily) {
    return getRuoniaViewModeContent({ chartMode });
  }
  if (isKeyRateFamily) {
    return getKeyRateViewModeContent({ chartMode });
  }
  if (isMortgageFamily) {
    return getMortgageViewModeContent({ chartMode, indicator });
  }
  if (isPpiFamily) {
    return getPpiViewModeContent({ chartMode, safeViewMode, indicator });
  }
  if (isAutoLoanFamily) {
    return getAutoLoanViewModeContent({ chartMode, indicator });
  }
  if (isCbrTermSliceFamily) {
    return getCbrTermSliceViewModeContent({ chartMode, indicator });
  }
  if (isHousingFamily) {
    return getHousingViewModeContent({ chartMode, indicator });
  }
  if (isPriceCategory) {
    const code = indicator?.code ?? 'cpi';
    if (chartMode === 'inflation') return buildInflation(code);
    if (safeViewMode === 'quarterly') return buildQuarterly(code);
    if (safeViewMode === 'annual') return buildAnnual(code);
    if (safeViewMode === 'period-weekly') return buildPeriodWeekly(code);
    if (safeViewMode === 'period-monthly') return buildPeriodMonthly(code);
    if (safeViewMode === 'step-weekly') return buildStepWeekly(code);
    if (safeViewMode === 'step-monthly') return buildStepMonthly(code);
    if (safeViewMode === 'yoy') return buildYoy(code);
    if (safeViewMode === 'qoq') return buildQoq(code);
    if (safeViewMode === 'index') return buildIndex(code);
    if (safeViewMode === 'index-quarterly') return buildIndex(code, 'quarter');
    if (safeViewMode === 'index-annual') return buildIndex(code, 'year');
    // legacy dataMode без url-режима
    if (chartMode === 'weekly') return WEEKLY_BY_CODE[code] ?? WEEKLY;
    if (chartMode === 'cpi') return buildStepMonthly(code);
  }
  return {
    description: indicator?.description ?? '',
    methodology: indicator?.methodology ?? '',
  };
}
