/**
 * Generic view-mode движок (frontend).
 *
 * Источник истины — `viewModelFamilies.generated.json`, экспортируемый из
 * backend `app/data/view_model_families.py` (скрипт `scripts/export-view-models.py`).
 * Один и тот же конфиг описывает derived-коды на backend и режимы на UI, поэтому
 * коды/частоты/единицы физически не рассинхронятся (ADR-0001).
 *
 * Этот модуль заменяет ~135 per-family `*ViewModeResolve/Groups`-файлов: вся
 * логика «URL-режим → derived-код / двухуровневые группы / нормализация /
 * канонический редирект» здесь, параметризована конфигом.
 *
 * Вариант-ось (какой именно индикатор: M0/M1/M2, первичное/вторичное жильё)
 * ОРТОГОНАЛЬНА оси режима и живёт в `indicatorVariants.js` (ADR-0006). Движок
 * работает per-base.
 */

import FAMILIES from './viewModelFamilies.generated.json';

/** Индекс: derived-код режима → { base, mode } для канонических редиректов. */
const CHILD_INDEX = (() => {
  const idx = {};
  for (const fam of Object.values(FAMILIES)) {
    for (const m of fam.modes) {
      // first-write-wins: алиас pop-gg переиспользует code yoy-year, но
      // канонический редирект derived-URL должен указывать на основной режим
      // (yoy-year), а не на алиас в «К прошлому периоду».
      if (!m.isNative && !idx[m.code]) idx[m.code] = { base: fam.base, mode: m.mode };
    }
  }
  return idx;
})();

/** Семья по base-коду карточки, либо null. */
export function getViewModeFamily(code) {
  return FAMILIES[code] ?? null;
}

/** Является ли code base-картой generic-семьи. */
export function isViewModeFamily(code) {
  return Boolean(FAMILIES[code]);
}

/** Канонический таргет для derived-URL: m2-yoy → { base: 'm2', mode: 'yoy' }. */
export function viewModeCanonicalTarget(code) {
  return CHILD_INDEX[code] ?? null;
}

/** Метаданные режима по токену (или null). */
function modeMeta(family, mode) {
  return family.modes.find((m) => m.mode === mode) ?? null;
}

/** Нормализовать URL-режим: невалидный/пустой → defaultMode семьи. */
export function normalizeViewMode(family, urlMode) {
  if (!family) return urlMode;
  if (urlMode && modeMeta(family, urlMode)) return urlMode;
  return family.defaultMode;
}

/**
 * Разрешить (family, urlMode) в полные метаданные режима:
 * { mode, code, unit, frequency, group, label, isNative, forecastable }.
 * code — backend-код, чьи точки рендерятся (source для нативного уровня).
 */
export function resolveViewMode(family, urlMode) {
  const mode = normalizeViewMode(family, urlMode);
  return modeMeta(family, mode);
}

/**
 * Построить двухуровневую структуру переключателя из конфига семьи:
 *   [{ id, label, leafMode? , modes?: [{ mode, label }] }]
 * leaf-группа (например «Г/г») — одиночная кнопка (leafMode).
 */
export function buildViewModeGroups(family) {
  if (!family) return [];
  return family.groups.map((g) => {
    const groupModes = family.modes
      .filter((m) => m.group === g.id)
      .map((m) => ({ mode: m.mode, label: m.label }));
    if (g.leaf) {
      return { id: g.id, label: g.label, leafMode: groupModes[0]?.mode ?? null };
    }
    return { id: g.id, label: g.label, modes: groupModes };
  });
}

/** Верхняя группа, к которой принадлежит режим. */
export function topGroupForMode(family, mode) {
  const meta = modeMeta(family, mode);
  return meta?.group ?? family?.defaultMode ?? null;
}

/** Группа, которую надо развернуть для текущего режима (leaf → null). */
export function expandedGroupForMode(family, mode) {
  const meta = modeMeta(family, mode);
  if (!meta) return null;
  const group = family.groups.find((g) => g.id === meta.group);
  return group && !group.leaf ? group.id : null;
}

/** Подсветить верхнюю группу: развёрнутая приоритетнее группы текущего режима. */
export function highlightedTopGroup(family, expandedGroupId, currentMode) {
  return expandedGroupId ?? topGroupForMode(family, currentMode);
}

/** Первый подрежим группы (для перехода при клике по верхней группе). */
export function defaultSubModeForGroup(family, groupId) {
  const sub = family.modes.find((m) => m.group === groupId);
  return sub?.mode ?? null;
}

/** Все base-коды generic-семей (для интеграции/тестов). */
export function viewModeFamilyBases() {
  return Object.keys(FAMILIES);
}

export { FAMILIES as VIEW_MODE_FAMILIES_CONFIG };
