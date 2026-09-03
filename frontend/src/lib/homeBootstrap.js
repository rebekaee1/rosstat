/**
 * Компактный SSR-bootstrap главной (`#fe-bootstrap`): flagships из render_home_html.
 * Живёт в <head>, createRoot его не стирает. Не содержит map-series.
 */
import { resolveBrowserLocale } from '../i18n/locale';
import { indicatorsListQueryKey } from './hooks';

export const HOME_BOOTSTRAP_ID = 'fe-bootstrap';

let cached;
let cachedRead = false;

export function resetHomeBootstrapCache() {
  cached = undefined;
  cachedRead = false;
}

export function readHomeBootstrap() {
  if (cachedRead) return cached;
  cachedRead = true;
  cached = null;
  if (typeof document === 'undefined') return null;
  const el = document.getElementById(HOME_BOOTSTRAP_ID);
  if (!el?.textContent) return null;
  try {
    const data = JSON.parse(el.textContent);
    if (!data || typeof data !== 'object') return null;
    cached = data;
    return cached;
  } catch {
    return null;
  }
}

export function seedQueryClientFromHomeBootstrap(queryClient) {
  const data = readHomeBootstrap();
  const list = data?.indicators;
  if (!queryClient || !Array.isArray(list) || list.length === 0) return false;
  const locale = data.locale || resolveBrowserLocale();
  const key = indicatorsListQueryKey(locale);
  queryClient.setQueryData(key, list);
  // Срез flagships не должен заморозить каталог на staleTime 5 мин.
  void queryClient.invalidateQueries({ queryKey: key });
  return true;
}
