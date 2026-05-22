import { Formula, ProdLimits } from '../components/MathFormula';

/**
 * Описание + методология для каждого режима CPI-графика.
 *
 * Эти тексты используются и в блоке «Методология» внутри карточки,
 * и потенциально для backend SEO. Если нужно поправить формулировку —
 * меняй здесь, а не в IndicatorDetail.
 */

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

const INFLATION = {
  description:
    'Накопленная инфляция за 12 месяцев показывает, на сколько процентов выросли '
    + 'потребительские цены за последний год. Рассчитывается как произведение 12 '
    + 'последовательных месячных индексов ИПЦ, делённых на 100, минус 100%.',
  methodology: (
    <>
      <span className="block mb-1">Формула:</span>
      {ANNUAL_INFLATION_FORMULA}
      <span className="block mt-2 text-text-tertiary normal-case tracking-normal text-[10px]">
        ИПЦ<sub>i</sub> — индекс потребительских цен за i-й месяц (% к предыдущему месяцу).
      </span>
    </>
  ),
};

const QUARTERLY = {
  description:
    'Квартальная инфляция показывает, на сколько процентов выросли потребительские '
    + 'цены за квартал (3 месяца). Рассчитывается как произведение 3 последовательных '
    + 'месячных индексов ИПЦ, делённых на 100, минус 100%.',
  methodology: (
    <>
      <span className="block mb-1">Формула:</span>
      {QUARTERLY_INFLATION_FORMULA}
    </>
  ),
};

const ANNUAL = {
  description:
    'Годовая инфляция «декабрь к декабрю» — стандарт ЦБ и Росстата. '
    + 'Одна точка на каждый завершённый календарный год: рассчитывается как '
    + 'произведение 12 месячных индексов ИПЦ внутри года (январь…декабрь), '
    + 'делённых на 100, минус 100%. Прогноз — то же произведение по 12 точкам '
    + 'месячного прогноза ИПЦ.',
  methodology: (
    <>
      <span className="block mb-1">Формула (за календарный год Y, январь…декабрь):</span>
      {ANNUAL_INFLATION_FORMULA}
      <span className="block mt-2 text-text-tertiary normal-case tracking-normal text-[10px]">
        ИПЦ<sub>i</sub> — индекс потребительских цен за i-й месяц года Y (% к предыдущему месяцу).
      </span>
    </>
  ),
};

const WEEKLY = {
  description:
    'Недельный ИПЦ — изменение потребительских цен за неделю по данным Росстата. '
    + 'Публикуется еженедельно, является оперативным индикатором инфляционных процессов.',
  methodology:
    'Источник — еженедельные бюллетени Росстата «Об оценке индекса потребительских цен». '
    + 'Официальный агрегированный недельный ИПЦ по всей потребительской корзине. Значение 100 = без изменений.',
};

const CPI_MONTHLY = {
  description:
    'Месячная инфляция — процентное изменение потребительских цен к предыдущему месяцу. '
    + 'Положительное значение означает рост цен, отрицательное — снижение. '
    + 'Шкала по оси Y центрирована на нуле.',
  methodology:
    'Формула: ИПЦᵢ − 100, где ИПЦᵢ — индекс потребительских цен за i-й месяц '
    + 'в % к предыдущему месяцу. Источник — месячные индексы ИПЦ Росстата.',
};

const INDEX = {
  description:
    'Накопленный индекс потребительских цен — общий уровень цен относительно '
    + 'базы. За базу принят январь 2000 года (100 = уровень цен в январе 2000). '
    + 'Каждое значение получено цепным произведением месячных индексов ИПЦ '
    + 'к этой базе. Кривая показывает, во сколько раз вырос общий уровень '
    + 'потребительских цен с 2000 года.',
  methodology:
    'Формула: ИНДЕКСₜ = 100 × (ИПЦ₁/100) × (ИПЦ₂/100) × … × (ИПЦₜ/100), где '
    + 'ИПЦᵢ — месячный индекс к предыдущему месяцу. История 1991–1999 не '
    + 'включена: гипер-инфляция первой половины 90-х искажает шкалу. Прогноз — '
    + 'продолжение накопленной кривой по 12-месячному прогнозу ИПЦ.',
};

/**
 * Вернуть пару (description, methodology) для текущего режима графика.
 *
 * Все CPI-specific блоки (INFLATION/QUARTERLY/ANNUAL/WEEKLY/INDEX/CPI_MONTHLY)
 * включаются **только** при `isPriceCategory === true`. Не-CPI индикаторы,
 * у которых тоже есть режим `annual` / `quarterly` через viewModeFamilies
 * (wages-nominal, unemployment), падают в fallback на `indicator.{description,
 * methodology}` — общий текст индикатора из БД. См. ADR-0006 «Subsequent
 * additions» и trap «View-mode family metadata leak» в CONTEXT.md.
 */
export function getViewModeContent({ chartMode, safeViewMode, isPriceCategory, indicator }) {
  if (isPriceCategory) {
    if (chartMode === 'inflation') return INFLATION;
    if (safeViewMode === 'quarterly') return QUARTERLY;
    if (safeViewMode === 'annual') return ANNUAL;
    if (safeViewMode === 'weekly') return WEEKLY;
    if (safeViewMode === 'index') return INDEX;
    if (safeViewMode === 'cpi') return CPI_MONTHLY;
  }
  return {
    description: indicator?.description ?? '',
    methodology: indicator?.methodology ?? '',
  };
}
