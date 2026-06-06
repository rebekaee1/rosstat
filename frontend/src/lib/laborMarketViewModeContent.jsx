/**
 * Рабочая сила и занятое население (срез × частота ряда).
 * Правила: .cursor/rules/methodology-language.mdc
 */

import { isLaborMarketFamily } from './laborMarketViewModeResolve';

function sliceMeta(indicatorCode) {
  if (indicatorCode === 'labor-force') {
    return {
      sliceLabel: 'численность рабочей силы',
      sliceLabelShort: 'рабочая сила',
      sliceLabelCap: 'Рабочая сила',
      aggName: 'рабочей силы',
      definition:
        'экономически активное население: занятые и безработные, готовые и способные работать',
      readHint:
        'сезонность строительства и туризма, мобилизационные и демографические факторы',
      siblingLabel: 'занятое население',
      historyFrom: '2015',
    };
  }
  return {
    sliceLabel: 'численность занятого населения',
    sliceLabelShort: 'занятое население',
    sliceLabelCap: 'Занятое население',
    aggName: 'занятых',
    definition:
      'лица, которые в опросный период имели оплачиваемую работу или временно её не выполняли',
    readHint:
      'сокращения и найм в отраслях, уход в самозанятость и неформальную занятость',
    siblingLabel: 'рабочая сила',
    historyFrom: '2015',
  };
}

function contentLevel(indicatorCode) {
  const s = sliceMeta(indicatorCode);
  const isLf = indicatorCode === 'labor-force';
  return {
    description:
      `На графике — ${s.sliceLabel} в млн человек на конец каждого месяца по `
      + 'обследованию рабочей силы Росстата. '
      + (isLf
        ? 'В показатель входят и те, кто работает, и те, кто ищет работу: '
          + 'это широкая «воронка» участия в рынке труда, а не только занятые.'
        : 'Это узкий срез рабочей силы — только те, у кого есть работа '
          + '(включая временно отсутствующих на месте), без безработных.')
      + ' Каждая точка — оценка на дату, а не прирост за месяц в тысячах человек. '
      + `Вкладка «${s.siblingLabel}» в семье «Рынок труда: занятость» `
      + 'показывает соседний ряд на тех же календарных датах.',
    methodology:
      `Режим «помесячно» для ${s.sliceLabelCap} — исходный ежемесячный ряд `
      + `Росстата (история с ${s.historyFrom} года на Forecast Economy). `
      + `Значение — ${s.definition}. `
      + 'Прогноз не строится. Переключение между рабочей силой и занятостью '
      + 'сохраняет выбранный режим графика. Если один месяц выбивается, '
      + 'откройте «Среднее за период» — по кварталам или по годам.',
  };
}

function contentAggQuarterly(indicatorCode) {
  const s = sliceMeta(indicatorCode);
  const isEmp = indicatorCode === 'employment';
  return {
    description:
      `На графике — средний помесячный уровень ${s.sliceLabel} внутри `
      + 'каждого календарного квартала (млн чел.). '
      + (isEmp
        ? 'Так видно, был ли квартал в целом «трудоёмким» по занятости, '
          + 'даже если один месяц исказил картину из‑за отпусков или сокращений.'
        : 'Удобно сравнить эпохи по размеру экономически активного населения '
          + 'без доминирования одного сезонного месяца.')
      + ` Сравнивайте с «${s.siblingLabel}» на соседней вкладке семьи.`,
    methodology:
      `Режим «среднее за период — по кварталам» для ${s.sliceLabelCap}: `
      + 'простое среднее трёх помесячных оценок Росстата внутри квартала. '
      + 'Отдельной публикации «средняя рабочая сила за квартал» у Росстата нет — '
      + 'расчёт выполняется при отображении из того же официального ряда. '
      + `На динамику сильнее влияют ${s.readHint}. `
      + 'При смене вкладки на соседний показатель выбранный режим не сбрасывается.',
  };
}

function contentAggAnnual(indicatorCode) {
  const s = sliceMeta(indicatorCode);
  const isLf = indicatorCode === 'labor-force';
  return {
    description:
      `На графике — средний помесячный уровень ${s.sliceLabel} внутри `
      + 'каждого календарного года (млн чел.). '
      + 'Годовая точка — не декабрь «как есть», а средний уровень по всем месяцам: '
      + (isLf
        ? 'так честнее сопоставить годы с разной демографией и участием в труде.'
        : 'так отделяется устойчивый тренд занятости от одного сильного месяца.')
      + ` Переключение на «${s.siblingLabel}» сохраняет режим.`,
    methodology:
      `Режим «среднее за период — по годам» для ${s.sliceLabelCap}: среднее всех `
      + 'помесячных оценок внутри календарного года. '
      + 'Не путать с приростом численности в процентах за год — на графике '
      + 'только уровень в млн человек. '
      + (isLf
        ? 'Для безработицы и зарплат смотрите соседние индикаторы каталога — '
          + 'здесь только рабочая сила.'
        : 'Сопоставляйте с рабочей силой на соседней вкладке: разрыв между '
          + 'рядами отражает безработицу в широком смысле обследования.')
      + ' Семья «Рынок труда: занятость» не сбрасывает режим при смене показателя.',
  };
}

export function getLaborMarketChartTitle(chartMode, indicatorCode) {
  const s = sliceMeta(indicatorCode);
  switch (chartMode) {
    case 'quarterly':
      return `${s.sliceLabelCap} — среднее по кварталам (млн чел.)`;
    case 'annual':
      return `${s.sliceLabelCap} — среднее по годам (млн чел.)`;
    default:
      return `${s.sliceLabelCap} — помесячно (млн чел.)`;
  }
}

export function getLaborMarketTableTitle(chartMode, indicatorCode) {
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

export function getLaborMarketViewModeContent({ chartMode = 'level', indicatorCode }) {
  if (chartMode === 'quarterly') return contentAggQuarterly(indicatorCode);
  if (chartMode === 'annual') return contentAggAnnual(indicatorCode);
  return contentLevel(indicatorCode);
}

export { isLaborMarketFamily };
