/**
 * Описание и методология: ставки ЦБ по сроку (кредиты / вклады).
 * Правила: .cursor/rules/methodology-language.mdc
 */

import { isCbrTermSliceFamily } from './cbrTermSliceRateResolve';

const SLICE_META = {
  'credit-rate-corp-short': {
    kind: 'corp',
    chart: 'до 1 года',
    table: 'до 1 года',
    phrase: 'со сроком погашения до 1 года, включая «до востребования»',
    variant: 'краткосрочный срез',
  },
  'credit-rate-corp-1to3y': {
    kind: 'corp',
    chart: 'от 1 до 3 лет',
    table: 'от 1 до 3 лет',
    phrase: 'со сроком погашения от 1 года до 3 лет',
    variant: 'среднесрочный срез',
  },
  'credit-rate-corp-over3y': {
    kind: 'corp',
    chart: 'свыше 3 лет',
    table: 'свыше 3 лет',
    phrase: 'со сроком погашения свыше 3 лет',
    variant: 'долгосрочный срез',
  },
  'credit-rate-ind-short': {
    kind: 'ind',
    chart: 'до 1 года',
    table: 'до 1 года',
    phrase: 'со сроком погашения до 1 года, включая «до востребования»',
    variant: 'краткосрочный срез',
  },
  'credit-rate-ind-1to3y': {
    kind: 'ind',
    chart: 'от 1 до 3 лет',
    table: 'от 1 до 3 лет',
    phrase: 'со сроком погашения от 1 года до 3 лет',
    variant: 'среднесрочный срез',
  },
  'credit-rate-ind-over3y': {
    kind: 'ind',
    chart: 'свыше 3 лет',
    table: 'свыше 3 лет',
    phrase: 'со сроком погашения свыше 3 лет',
    variant: 'долгосрочный срез',
  },
  'deposit-rate': {
    kind: 'deposit',
    chart: 'до 1 года',
    table: 'до 1 года',
    phrase: 'со сроком до 1 года, включая «до востребования»',
    variant: 'краткосрочный срез',
  },
  'deposit-rate-medium': {
    kind: 'deposit',
    chart: 'от 1 до 3 лет',
    table: 'от 1 до 3 лет',
    phrase: 'со сроком от 1 года до 3 лет',
    variant: 'среднесрочный срез',
  },
  'deposit-rate-long': {
    kind: 'deposit',
    chart: 'свыше 3 лет',
    table: 'свыше 3 лет',
    phrase: 'со сроком свыше 3 лет',
    variant: 'долгосрочный срез',
  },
};

function meta(code) {
  return SLICE_META[code] ?? SLICE_META['credit-rate-corp-short'];
}

function productLabel(kind) {
  if (kind === 'deposit') return 'вкладам физических лиц';
  if (kind === 'ind') return 'кредитам физических лиц';
  return 'кредитам юридическим лицам';
}

function subjectPhrase(kind) {
  if (kind === 'deposit') {
    return 'по рублёвым вкладам (депозитам) физических лиц';
  }
  if (kind === 'ind') {
    return 'по рублёвым потребительским кредитам физических лиц';
  }
  return 'по рублёвым кредитам нефинансовым организациям';
}

export function getCbrTermSliceChartTitle(chartMode, code) {
  void chartMode;
  const m = meta(code);
  const product = productLabel(m.kind);
  return `Ставка по ${product} — ${m.chart} (%)`;
}

export function getCbrTermSliceTableTitle(chartMode, code) {
  void chartMode;
  const m = meta(code);
  if (m.kind === 'deposit') {
    return `Исторические данные — вклады, ${m.table}`;
  }
  if (m.kind === 'ind') {
    return `Исторические данные — кредиты физлицам, ${m.table}`;
  }
  return `Исторические данные — кредиты юрлицам, ${m.table}`;
}

export function getCbrTermSliceViewModeContent({ chartMode = 'level', indicator }) {
  void chartMode;
  const code = indicator?.code ?? 'credit-rate-corp-short';
  const m = meta(code);
  const subject = subjectPhrase(m.kind);
  const depositNote = m.kind === 'deposit'
    ? 'Речь о ставке привлечения средств вкладчиками, а не о доходности одного продукта банка. '
    : '';
  return {
    description:
      `На графике — средневзвешенная годовая ставка ${subject} `
      + `${m.phrase}: ${depositNote}`
      + 'значение за отчётный месяц по отчётности банков. '
      + 'Это уровень ставки, а не прирост к прошлому месяцу.',
    methodology:
      `Режим «уровень ставки» для ${m.variant}. Банк России публикует `
      + 'средневзвешенные ставки с разбивкой по сроку; срок выбирается '
      + 'переключателем над графиком («До 1 года / От 1 до 3 лет / '
      + 'Свыше 3 лет»). Данные ежемесячные с лагом около месяца; '
      + 'последняя точка — в карточке и в таблице истории.',
  };
}

export { isCbrTermSliceFamily };
