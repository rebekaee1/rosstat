/**
 * Представление ряда в режиме сравнения (письмо пользователя 2026-07).
 *
 * Проблема: в сравнении каждый индикатор грузился в НАТИВНОМ виде — ИПЦ помесячно
 * «к прошлому периоду», а ИЦП накопленным индексом. Ряды несопоставимы. Решение:
 * на каждый ряд — выбор представления (Индекс/Значение · К прошлому периоду · К
 * году), как в индивидуальном просмотре, чтобы привести оба ряда к одному виду.
 *
 * Ключевой принцип: НЕ считаем на фронте то, что уже есть derived-рядом. Резолвер
 * отображает (индикатор, представление) → {код ряда, transform, unit}:
 *   - generic-семьи (101 шт.) → sibling-код из `viewModelFamilies.generated.json`
 *     (первый режим группы pop/yoy — канонический по нативной частоте);
 *   - bespoke (cpi/ppi/housing) → реальные %-коды (`*-yoy`, `housing-qoq/yoy-*`) +
 *     минимальные клиентские трансформы, которые уже применяются на карточке
 *     (CPI m/m = база−100, CPI индекс = накопленная кривая, PPI m/m из индекса);
 *   - остальные (без семьи) → только «Значение».
 *
 * transform применяется поверх скачанного ряда: null | 'sub100' | 'mom' |
 * 'cpiCumulative'. Единая точка истины трансформов — здесь и на карточке.
 */

import { getViewModeFamily } from './viewModeEngine';
import { applyMoMTransform } from './viewModeFamilies';
import { buildCumulativeIndex } from './cpiCumulativeIndex';

export const REP_LEVEL = 'level';
export const REP_POP = 'pop';
export const REP_YOY = 'yoy';

// Порядок кнопок в переключателе представления.
export const REP_ORDER = [REP_LEVEL, REP_POP, REP_YOY];

// Подсказки к кнопкам представления — та же формулировка, что на карточке
// индикатора (группа «К соотв. периоду пред. года», см. view_model_families.py).
export const REP_HINT = {
  [REP_LEVEL]: 'Исходные значения ряда в его единицах измерения',
  [REP_POP]: 'Изменение к предыдущему месяцу или кварталу, в процентах',
  [REP_YOY]: 'Изменение к соответствующему периоду год назад (Г/г), в процентах',
};

const LABEL_POP = 'К прошлому периоду';
const LABEL_YOY = 'К прошлому году';

const CPI_CODES = ['cpi', 'cpi-food', 'cpi-nonfood', 'cpi-services'];
const HOUSING_CODES = ['housing-price-primary', 'housing-price-secondary'];

function levelLabel(unit) {
  return unit === 'индекс' ? 'Индекс' : 'Значение';
}

/**
 * Карта доступных представлений индикатора: { level, pop?, yoy? }.
 * Каждое значение — { code, transform, unit, label }.
 */
function buildRepMap(indicator) {
  const code = indicator?.code;
  if (!code) return {};

  if (CPI_CODES.includes(code)) {
    return {
      level: { code, transform: 'cpiCumulative', unit: 'индекс', label: 'Индекс' },
      pop: { code, transform: 'sub100', unit: '%', label: LABEL_POP },
      yoy: { code: `${code}-yoy`, transform: null, unit: '%', label: LABEL_YOY },
    };
  }

  if (code === 'ppi') {
    return {
      level: { code: 'ppi', transform: null, unit: 'индекс', label: 'Индекс' },
      pop: { code: 'ppi', transform: 'mom', unit: '%', label: LABEL_POP },
      yoy: { code: 'ppi-yoy', transform: null, unit: '%', label: LABEL_YOY },
    };
  }

  if (HOUSING_CODES.includes(code)) {
    const slice = code.endsWith('secondary') ? 'secondary' : 'primary';
    return {
      level: { code, transform: null, unit: 'индекс', label: 'Индекс' },
      pop: { code: `housing-qoq-${slice}`, transform: null, unit: '%', label: LABEL_POP },
      yoy: { code: `housing-yoy-${slice}`, transform: null, unit: '%', label: LABEL_YOY },
    };
  }

  const fam = getViewModeFamily(code);
  if (fam) {
    const native = fam.modes.find((m) => m.isNative) || fam.modes[0];
    const pop = fam.modes.find((m) => m.group === 'pop');
    const yoy = fam.modes.find((m) => m.group === 'yoy');
    const map = {
      level: {
        code: native.code,
        transform: null,
        unit: native.unit,
        label: levelLabel(native.unit),
      },
    };
    if (pop) map.pop = { code: pop.code, transform: null, unit: pop.unit || '%', label: LABEL_POP };
    if (yoy) map.yoy = { code: yoy.code, transform: null, unit: yoy.unit || '%', label: LABEL_YOY };
    return map;
  }

  // Одиночный ряд без семьи — только уровень.
  const unit = indicator?.unit;
  return { level: { code, transform: null, unit, label: levelLabel(unit) } };
}

/**
 * Опции переключателя представления для индикатора (только доступные).
 * → [{ id, label }] в каноническом порядке.
 */
export function compareRepresentationsFor(indicator) {
  const map = buildRepMap(indicator);
  return REP_ORDER.filter((id) => map[id]).map((id) => ({ id, label: map[id].label }));
}

/**
 * Разрешить (индикатор, repId) в спецификацию загрузки:
 * { code, transform, unit, repId }. Неизвестное представление → level.
 */
export function resolveCompareSeries(indicator, repId) {
  const map = buildRepMap(indicator);
  const spec = map[repId] || map.level;
  if (!spec) return null;
  return { ...spec, repId: map[repId] ? repId : REP_LEVEL };
}

/**
 * Применить клиентский трансформ представления к скачанным точкам [{date,value}].
 * Единственное место, где живёт трансформ-логика сравнения.
 */
/**
 * Приводится ли ряд к общей базе (=100). Только положительный конечный УРОВЕНЬ:
 * знакопеременные (сальдо/счёт/дефицит) и %-приросты (пересекают ноль) дали бы
 * деление на ~0 (выброс) или переворот знака при отрицательной базе. Кроме того
 * (В-12), процентные ряды и представления «к прошлому периоду»/«к году» — это
 * уже темпы, а не уровни: «инфляция 5% = 100 пунктов» смыслово не то, такие ряды
 * в режиме общей базы исключаются и подписываются нотой. Единая точка истины
 * решения «индексируется/нет» — здесь (используется ComparePage и тестом).
 */
export function isIndexableBase(base, { unit, repId } = {}) {
  if (unit === '%' || unit === '‰') return false;
  if (repId === REP_POP || repId === REP_YOY) return false;
  return typeof base === 'number' && Number.isFinite(base) && base > 0;
}

/** Значение ряда, приведённое к базе-100. Вызывать только при isIndexableBase(base). */
export function rebaseToHundred(value, base) {
  return (value / base) * 100;
}

// Шаг переключателя времени → ключ `alternate_frequencies` на карточке
// индикатора (тот же справочник частот, что `frequencySwitcher.js`).
const STEP_FREQ_KEY = { month: 'monthly', quarter: 'quarterly', year: 'annual' };

/**
 * «Третий слой» сравнения (созвон «На правки 13», 2026-07-08): переключатель
 * «Шаг» по умолчанию просто усредняет уже загруженные точки клиентски —
 * для показателя с более глубоким альтернативным рядом на этой частоте
 * (напр. `wages-nominal` → `wages-nominal-annual`, 1991+, а не усреднение
 * помесячного 2015+) это даёт куцую историю вместо настоящей. Если у
 * индикатора есть `alternate_frequencies[freqKey]` — используем его код
 * вместо клиентской агрегации. Применяется только к представлению «Значение»
 * (level): pop/yoy уже разрешаются generic-семьёй на своей нативной глубине,
 * alternate_frequencies линкует именно уровневые ряды одного показателя.
 */
export function resolveStepOverride(indicator, repId, step) {
  if (repId !== REP_LEVEL || !step || step === 'auto') return null;
  const freqKey = STEP_FREQ_KEY[step];
  const altCode = freqKey && indicator?.alternate_frequencies?.[freqKey];
  return altCode || null;
}

export function applyCompareTransform(points, transform) {
  if (!Array.isArray(points) || !points.length) return [];
  if (!transform) return points;
  if (transform === 'sub100') {
    return points.map((p) => ({ ...p, value: Number(p.value) - 100 }));
  }
  if (transform === 'mom') return applyMoMTransform(points);
  if (transform === 'cpiCumulative') return buildCumulativeIndex(points);
  return points;
}
