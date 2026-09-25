/**
 * Компактный SSR-bootstrap главной (`#fe-bootstrap`): flagships + world
 * catalogue counters (+ default map snapshot) из render_home_html.
 * Живёт в <head>, createRoot его не стирает. Полный map-series (~385KB)
 * сюда не кладём — snapshot хватает для первого кадра карты.
 */
import { resolveBrowserLocale } from '../i18n/locale';
import { indicatorsListQueryKey } from './hooks';
import { DEFAULT_HOME_COUNTRY_CONCEPT } from './homeWorkbench';
import {
  worldCompareSnapshotQueryKey,
  worldCountriesQueryKey,
} from './worldApi';

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

/**
 * Seed React Query from #fe-bootstrap before first paint.
 * Flagships are a slice → invalidate so full /indicators refetches.
 * worldCountries / mapSnapshot are full endpoint shapes → setQueryData only
 * (no invalidate), otherwise the SPA would still wait on cold TTFB.
 */
export function seedQueryClientFromHomeBootstrap(queryClient) {
  const data = readHomeBootstrap();
  if (!queryClient || !data) return false;
  const locale = data.locale || resolveBrowserLocale();
  let seeded = false;

  const list = data.indicators;
  if (Array.isArray(list) && list.length > 0) {
    const key = indicatorsListQueryKey(locale);
    queryClient.setQueryData(key, list);
    // Срез flagships не должен заморозить каталог на staleTime 5 мин.
    void queryClient.invalidateQueries({ queryKey: key });
    seeded = true;
  }

  const world = data.worldCountries;
  if (
    world
    && typeof world === 'object'
    && (
      Array.isArray(world.countries)
      || Number(world.world_indicators_count) > 0
      || Number(world.total) > 0
    )
  ) {
    queryClient.setQueryData(worldCountriesQueryKey(locale), world);
    seeded = true;
  }

  const snap = data.mapSnapshot;
  const concept = data.mapConcept || DEFAULT_HOME_COUNTRY_CONCEPT;
  if (snap && typeof snap === 'object' && Array.isArray(snap.items)) {
    queryClient.setQueryData(worldCompareSnapshotQueryKey(concept, locale), snap);
    seeded = true;
  }

  return seeded;
}
