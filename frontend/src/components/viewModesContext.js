import { createContext, useContext, useId, useLayoutEffect } from 'react';

/** Связь между панелью «Вид» и переключателями внутри неё. */
export const PanelContext = createContext(null);

/**
 * Сообщает ближайшей `ViewModesPanel` подпись выбранного варианта.
 * `key` склеивает дубли (один переключатель отрисован дважды для телефона и компьютера),
 * `order` задаёт порядок частей в строке.
 */
export function useViewModeSummary(key, order, text) {
  const ctx = useContext(PanelContext);
  const id = useId();
  const register = ctx?.register;
  useLayoutEffect(() => {
    if (!register) return undefined;
    register(id, key, order, text || '');
    return () => register(id, key, order, '');
  }, [register, id, key, order, text]);
}

// «Значения» и «Values» стоят по умолчанию: в короткой строке свёрнутой панели они только удлиняют её и обрезают главное.
const DEFAULT_GROUP_LABELS = new Set(['Значения', 'Values', 'Уровень', 'Level']);

/** «Год к году, по месяцам»: подпись группы и, строчными, выбранной детализации. */
export function modeSummaryText(groupLabel, subLabel) {
  const sub = subLabel ? subLabel.charAt(0).toLowerCase() + subLabel.slice(1) : '';
  const group = DEFAULT_GROUP_LABELS.has(groupLabel) ? '' : groupLabel;
  return [group, sub].filter(Boolean).join(', ');
}
