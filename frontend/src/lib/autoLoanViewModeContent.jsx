/**
 * Описание и методология: ставка по автокредитам (один режим на карточке).
 * Аналог ячейки «состав × режим» у ИПЦ, без переключателя режимов.
 * Правила: .cursor/rules/methodology-language.mdc
 */

import { AUTO_LOAN_CODES } from './autoLoanViewModeResolve';

export function getAutoLoanChartTitle(chartMode = 'level') {
  void chartMode;
  return 'Ставка по автокредитам — средневзвешенная (%)';
}

export function getAutoLoanTableTitle(chartMode = 'level') {
  void chartMode;
  return 'Исторические данные — ставка по автокредитам (%)';
}

export function getAutoLoanViewModeContent({ chartMode = 'level', indicator }) {
  void chartMode;
  void indicator;
  return {
    description:
      'На графике — средневзвешенная годовая процентная ставка по автокредитам '
      + 'в рублях: сколько в среднем стоят заимствования на покупку автомобиля '
      + 'по отчётности банков за отчётный месяц. Это уровень ставки, а не прирост '
      + 'к прошлому месяцу.',
    methodology:
      'Единственный режим карточки — «уровень ставки». Банк России '
      + 'публикует агрегат по новым и пролонгированным договорам физических лиц; '
      + 'взвешивание — по объёмам выдач. Срез «по всем срокам» объединяет краткие '
      + 'и длинные договоры без отдельной разбивки на графике. Данные выходят '
      + 'ежемесячно с лагом около месяца; последняя точка и источник указаны '
      + 'в карточке над графиком и в таблице истории.',
  };
}

export function isAutoLoanFamily(code) {
  return AUTO_LOAN_CODES.includes(code);
}
