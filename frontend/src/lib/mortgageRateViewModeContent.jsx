/**
 * Описание и методология: ставка по ипотеке (один режим на карточке).
 * Правила: .cursor/rules/methodology-language.mdc
 */

import { MORTGAGE_RATE_CODES } from './mortgageRateViewModeResolve';

export function getMortgageChartTitle(chartMode = 'level') {
  void chartMode;
  return 'Ставка по ипотеке — средневзвешенная (%)';
}

export function getMortgageTableTitle(chartMode = 'level') {
  void chartMode;
  return 'Исторические данные — ставка по ипотеке (%)';
}

export function getMortgageViewModeContent({ chartMode = 'level', indicator }) {
  void chartMode;
  void indicator;
  return {
    description:
      'На графике — средневзвешенная годовая процентная ставка по ипотечным '
      + 'жилищным кредитам в рублях: сколько в среднем стоит заимствование на '
      + 'покупку жилья по отчётности банков за отчётный месяц. Это уровень '
      + 'ставки, а не прирост к прошлому месяцу.',
    methodology:
      'Единственный режим карточки — «уровень ставки». Банк России '
      + 'публикует агрегат по новым и действующим ипотечным договорам '
      + 'физических лиц-резидентов; взвешивание — по объёмам выдач. '
      + 'Отдельных срезов по сроку на этой карточке нет — один ряд по всем '
      + 'ипотечным сделкам в статистике. Данные выходят ежемесячно с лагом '
      + 'около одного–двух месяцев; последняя точка и источник указаны над '
      + 'графиком и в таблице истории.',
  };
}

export function isMortgageFamily(code) {
  return MORTGAGE_RATE_CODES.includes(code);
}
