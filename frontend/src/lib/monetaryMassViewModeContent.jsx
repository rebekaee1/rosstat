/**
 * Денежные агрегаты М0, М1, М2 (срез × частота ряда).
 * Правила: .cursor/rules/methodology-language.mdc
 */

import { isMonetaryMassFamily } from './monetaryMassViewModeResolve';

function sliceMeta(indicatorCode) {
  if (indicatorCode === 'm0') {
    return {
      sliceLabel: 'денежная масса М0 (наличные в обращении)',
      sliceLabelShort: 'денежная масса М0',
      sliceLabelCap: 'Денежная масса М0',
      aggName: 'М0',
      composition:
        'только банкноты и монеты у населения, организаций и в кассах вне банковской системы',
      readHint:
        'сезонный спрос на наличность перед праздниками, комиссии за переводы '
        + 'и доверие к безналу',
      siblingNarrow: 'М1',
      siblingBroad: 'М2',
      historyFrom: '1993',
    };
  }
  if (indicatorCode === 'm1') {
    return {
      sliceLabel: 'денежный агрегат М1',
      sliceLabelShort: 'денежная масса М1',
      sliceLabelCap: 'Денежная масса М1',
      aggName: 'М1',
      composition:
        'наличные (М0) и переводные депозиты до востребования резидентов в банках',
      readHint:
        'налоговые даты, зарплатные волны и перетоки между текущими счетами '
        + 'и срочными вкладами',
      siblingNarrow: 'М0',
      siblingBroad: 'М2',
      historyFrom: '1995',
    };
  }
  return {
    sliceLabel: 'широкая денежная масса М2',
    sliceLabelShort: 'денежная масса М2',
    sliceLabelCap: 'Денежная масса М2',
    aggName: 'М2',
    composition:
      'наличные, переводные и срочные депозиты, прочие счета резидентов в определении регулятора',
    readHint:
      'ставки по вкладам, кредитование банков и решения по обязательным резервам',
    siblingNarrow: 'М0',
    siblingBroad: 'М1',
    historyFrom: '1995',
  };
}

function contentLevel(indicatorCode) {
  const s = sliceMeta(indicatorCode);
  const isM0 = indicatorCode === 'm0';
  const isM1 = indicatorCode === 'm1';
  return {
    description:
      `На графике — ${s.sliceLabel} в млрд рублей на конец каждого месяца: `
      + `${s.composition}. `
      + (isM0
        ? 'Это самый узкий из трёх агрегатов на сайте: только «живые» деньги вне банков, '
          + 'без остатков на счетах и без срочных вкладов.'
        : isM1
          ? 'М1 — «узкие» деньги для расчётов: всё, что можно быстро потратить или перевести, '
            + 'но ещё без срочных депозитов, которые входят в М2.'
          : 'М2 — основной показатель ликвидности в рублях для макроанализа: '
            + 'он шире М1 за счёт срочных сбережений и прочих депозитных остатков.')
      + ' Каждая точка — официальная оценка Банка России на дату, а не эмиссия за месяц '
      + 'и не темп прироста в процентах. '
      + `Вкладки ${s.siblingNarrow} и ${s.siblingBroad} в семье «Денежные агрегаты» `
      + 'показывают соседние определения денег на тех же календарных датах.',
    methodology:
      `Режим «помесячно» для ${s.aggName} — исходный ежемесячный ряд Банка России `
      + `(история с ${s.historyFrom} года на Forecast Economy). `
      + 'Значение — остаток агрегата на последний день месяца, а не оборот за 30 дней. '
      + 'Прогноз не строится. Переключение М0 / М1 / М2 в одной семье сохраняет '
      + 'выбранный режим графика. Если один месяц сильно выбивается из ряда, '
      + 'откройте «Среднее за период» — по кварталам или по годам.',
  };
}

function contentAggQuarterly(indicatorCode) {
  const s = sliceMeta(indicatorCode);
  const isM0 = indicatorCode === 'm0';
  return {
    description:
      `На графике — средний помесячный уровень ${s.sliceLabel} внутри `
      + 'каждого календарного квартала (млрд руб.). '
      + (isM0
        ? 'Квартал с высоким декабрём и спокойным февралём даст одну усреднённую точку — '
          + 'удобно сравнить «типичный» уровень наличности без пика одного месяца.'
        : indicatorCode === 'm1'
          ? 'Так видно, был ли квартал в целом «жидким» по переводным остаткам, '
            + 'даже если отдельный месяц исказил картину из‑за дивидендов или налогов.'
          : 'Помогает отделить устойчивый рост широкой массы от разового всплеска '
            + 'вкладов в одном месяце.')
      + ` Сравнивайте с ${s.siblingNarrow} и ${s.siblingBroad} на соседних вкладках семьи.`,
    methodology:
      `Режим «среднее за период — по кварталам» для ${s.aggName}: простое среднее `
      + 'трёх помесячных оценок Банка России внутри квартала. '
      + `Отдельной публикации «средний ${s.aggName} за квартал» у регулятора нет — `
      + 'расчёт выполняется при отображении из того же официального ряда. '
      + `На динамику ${s.aggName} в этом режиме сильнее влияют ${s.readHint}. `
      + 'При смене вкладки на другой агрегат выбранный режим не сбрасывается.',
  };
}

function contentAggAnnual(indicatorCode) {
  const s = sliceMeta(indicatorCode);
  const isM2 = indicatorCode === 'm2';
  return {
    description:
      `На графике — средний помесячный уровень ${s.sliceLabel} внутри `
      + 'каждого календарного года (млрд руб.). '
      + 'Годовая точка — не декабрь «как есть», а средний уровень по всем месяцам: '
      + (isM2
        ? 'так честнее сопоставить годы с разной денежно-кредитной политикой и волнами '
          + 'притока в депозиты.'
        : indicatorCode === 'm0'
          ? 'так видно, менялась ли доля наличных в экономике в среднем за год, '
            + 'а не только в конце декабря.'
          : 'так отделяется устойчивый тренд «узких» денег от одного сильного месяца.')
      + ` Переключение на ${s.siblingNarrow} или ${s.siblingBroad} сохраняет режим.`,
    methodology:
      `Режим «среднее за период — по годам» для ${s.aggName}: среднее всех `
      + 'помесячных остатков внутри календарного года. '
      + 'Не путать с приростом денежной массы в процентах за год — на графике '
      + 'только уровень в млрд рублей. '
      + (isM2
        ? 'Для связи с инфляцией и ключевой ставкой смотрите соседние индикаторы '
          + 'каталога — здесь только агрегат М2.'
        : 'Сопоставляйте с широкой массой М2 на соседней вкладке, если нужен '
          + 'контекст общей ликвидности.')
      + ' Семья «Денежные агрегаты» не сбрасывает выбранный режим при смене М0, М1, М2.',
  };
}

export function getMonetaryMassChartTitle(chartMode, indicatorCode) {
  const s = sliceMeta(indicatorCode);
  switch (chartMode) {
    case 'quarterly':
      return `${s.sliceLabelCap} — среднее по кварталам (млрд руб.)`;
    case 'annual':
      return `${s.sliceLabelCap} — среднее по годам (млрд руб.)`;
    default:
      return `${s.sliceLabelCap} — помесячно (млрд руб.)`;
  }
}

export function getMonetaryMassTableTitle(chartMode, indicatorCode) {
  const s = sliceMeta(indicatorCode);
  switch (chartMode) {
    case 'quarterly':
      return `Исторические данные — ${s.sliceLabelShort}, среднее по кварталам`;
    case 'annual':
      return `Исторические данные — ${s.sliceLabelShort}, среднее по годам`;
    default:
      return `Исторические данные — ${s.sliceLabelShort} (помесячно)`;
  }
}

export function getMonetaryMassViewModeContent({ chartMode = 'level', indicatorCode }) {
  if (chartMode === 'quarterly') return contentAggQuarterly(indicatorCode);
  if (chartMode === 'annual') return contentAggAnnual(indicatorCode);
  return contentLevel(indicatorCode);
}

export { isMonetaryMassFamily };
