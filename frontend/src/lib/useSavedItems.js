/**
 * Круг 11 (зона B): хуки сохранённого. Гость сохраняет в браузере, вошедший в кабинете;
 * при входе браузерные записи переносятся сами (см. `cabinetStore.syncGuest`).
 */
import { useMemo } from 'react';
import { useCabinetBoot, useCabinetState } from './useCabinet';
import { findSavedIn, removeSaved, removeSavedById, renameSaved, saveItem } from './cabinetStore';

/**
 * Одна запись: `{ enabled, authed, saved, item, toggle }`.
 * `toggle({ title, payload })` сохраняет или убирает и возвращает `{ ok, local?, created?, reason? }`.
 */
export function useSaved(kind, itemKey) {
  const { authed } = useCabinetBoot();
  const s = useCabinetState();
  const enabled = s.config?.enabled === true;
  const item = enabled ? findSavedIn(s, kind, itemKey) : null;
  return useMemo(() => ({
    enabled,
    authed,
    saved: Boolean(item),
    item,
    limit: s.config?.limits?.saved,
    toggle: ({ title, payload } = {}) => (item
      ? removeSaved(kind, itemKey)
      : saveItem({ kind, itemKey, title, payload })),
  }), [enabled, authed, item, s.config, kind, itemKey]);
}

/**
 * Весь список для раздела «Избранное»: записи кабинета (у вошедшего) или браузера (у гостя).
 * `status`: idle | loading | ready | error.
 */
export function useSavedItems() {
  const { authed } = useCabinetBoot();
  const s = useCabinetState();
  const enabled = s.config?.enabled === true;
  return useMemo(() => ({
    enabled,
    authed,
    items: !enabled ? [] : authed ? s.saved : s.guest,
    pendingLocal: enabled && authed ? s.guest.length : 0,
    status: authed ? s.savedStatus : 'ready',
    limit: s.config?.limits?.saved,
    remove: removeSavedById,
    rename: renameSaved,
  }), [enabled, authed, s]);
}
