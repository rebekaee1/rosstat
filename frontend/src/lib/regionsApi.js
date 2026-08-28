// API-слой регионального блока (bounded context «Регионы России»).
// Отдельно от макро-hooks: своя ось (регион × показатель × год).
import { useQuery } from '@tanstack/react-query';
import api from './api';
import { resolveBrowserLocale } from '../i18n/locale';
import { t } from '../i18n/messages';

const STALE = 10 * 60 * 1000;
const GC = 30 * 60 * 1000;

function localeKey() {
  return resolveBrowserLocale();
}

function numberLocale(locale = localeKey()) {
  return locale === 'en' ? 'en-US' : 'ru-RU';
}

export function useRegionsLanding() {
  return useQuery({
    queryKey: ['regions-landing', localeKey()],
    queryFn: ({ signal }) => api.get('/regions', { signal }).then(r => r.data),
    staleTime: STALE,
    gcTime: GC,
  });
}

export function useRegionsCatalog(enabled = true) {
  return useQuery({
    queryKey: ['regions-catalog', localeKey()],
    queryFn: ({ signal }) => api.get('/regions/catalog', { signal }).then(r => r.data),
    staleTime: STALE,
    gcTime: GC,
    enabled,
  });
}

export function useRegionProfile(slug) {
  return useQuery({
    queryKey: ['region-profile', slug, localeKey()],
    queryFn: ({ signal }) => api.get(`/regions/${slug}`, { signal }).then(r => r.data),
    enabled: !!slug,
    staleTime: STALE,
    gcTime: GC,
  });
}

export function useRegionIndicator(slug, code) {
  return useQuery({
    queryKey: ['region-indicator', slug, code, localeKey()],
    queryFn: ({ signal }) =>
      api.get(`/regions/${slug}/i/${code}`, { signal }).then(r => r.data),
    enabled: !!slug && !!code,
    staleTime: STALE,
    gcTime: GC,
  });
}

/** Помесячный ряд (цены на топливо и будущие месячные витрины). */
export function useRegionIndicatorMonthly(slug, code, enabled = true) {
  return useQuery({
    queryKey: ['region-indicator-monthly', slug, code, localeKey()],
    queryFn: ({ signal }) =>
      api.get(`/regions/${slug}/i/${code}/monthly`, { signal }).then(r => r.data),
    enabled: !!slug && !!code && enabled,
    staleTime: STALE,
    gcTime: GC,
  });
}

/** Значения показателя по всем регионам за последний год — для карты. */
export function useRegionsHeatmap(code, enabled = true) {
  return useQuery({
    queryKey: ['regions-heatmap', code, localeKey()],
    queryFn: ({ signal }) =>
      api.get(`/regions/heatmap/${code}`, { signal }).then(r => r.data),
    enabled: !!code && enabled,
    staleTime: STALE,
    gcTime: GC,
  });
}

/** Значения показателя по всем регионам за ВСЕ годы — для карты-таймлайна. */
export function useRegionsHeatmapSeries(code, enabled = true) {
  return useQuery({
    queryKey: ['regions-heatmap-series', code, localeKey()],
    queryFn: ({ signal }) =>
      api.get(`/regions/heatmap-series/${code}`, { signal }).then(r => r.data),
    enabled: !!code && enabled,
    staleTime: STALE,
    gcTime: GC,
  });
}

/**
 * Число знаков дробной части по природе величины (не по коду показателя).
 * Крупные счётные (население, рубли) — целые; десятки–сотни — один знак;
 * величины порядка единиц и доли (коэффициенты, индексы) — до трёх,
 * иначе 1,152 и 1,195 оба становятся «1,2» при разной геометрии графика.
 */
export function regionValueDigits(value) {
  const abs = Math.abs(Number(value));
  if (!Number.isFinite(abs)) return 0;
  if (abs >= 10000) return 0;
  if (abs >= 10) return 1;
  return 3;
}

/** Форматирование чисел региональных рядов: большие — с разрядами, малые — с дробью. */
export function formatRegionValue(value, locale) {
  if (value == null || Number.isNaN(value)) return '—';
  const loc = (locale === 'en' || locale === 'ru') ? locale : localeKey();
  return Number(value).toLocaleString(numberLocale(loc), {
    minimumFractionDigits: 0,
    maximumFractionDigits: regionValueDigits(value),
  });
}

/**
 * Компактный тик оси Y: большие числа сокращаются («1,2 млн» / «1.2 mln»),
 * остальные — с разрядными пробелами. Сокращается ЧИСЛО (не единица ряда):
 * ось всегда в единицах индикатора. Пробелы неразрывные — иначе SVG-текст
 * recharts переносит суффикс на вторую строку и подпись обрезается.
 */
export function formatCompactTick(value, { narrow = false, locale = localeKey() } = {}) {
  if (value == null || !Number.isFinite(Number(value))) return '';
  const num = Number(value);
  const abs = Math.abs(num);
  const loc = numberLocale(locale);
  const short = (v, suffix) => {
    const s = v.toLocaleString(loc, { minimumFractionDigits: 0, maximumFractionDigits: 1 });
    return `${s}\u00A0${suffix}`;
  };
  if (abs >= 1e9) return short(num / 1e9, t('map.compact.billion'));
  if (abs >= 1e6) return short(num / 1e6, t('map.compact.million'));
  if (abs >= 1e5) {
    return short(num / 1e3, narrow ? t('regions.home.compact.thsNarrow') : t('map.compact.thousand'));
  }
  return num
    .toLocaleString(loc, { maximumFractionDigits: abs < 10 ? 1 : 0 })
    .replace(/\s/g, '\u00A0');
}

/**
 * Ширина оси Y под самые длинные подписи ряда — чтобы «148,5 тыс» не
 * обрезалось узкой осью (фикс 2026-07-05, скрин руководителя).
 * narrow=true — бюджет под короткие суффиксы («т» вместо «тыс») на мобилке.
 */
export function compactTickAxisWidth(values, { narrow = false } = {}) {
  const nums = (values || []).filter((v) => v != null && Number.isFinite(Number(v)));
  if (!nums.length) return narrow ? 40 : 52;
  const longest = Math.max(
    formatCompactTick(Math.max(...nums), { narrow }).length,
    formatCompactTick(Math.min(...nums), { narrow }).length,
  );
  const minW = narrow ? 34 : 40;
  const maxW = narrow ? 44 : 80;
  return Math.max(minW, Math.min(maxW, Math.round(longest * (narrow ? 6.2 : 6.8)) + (narrow ? 8 : 12)));
}

/** Русское склонение: pluralRu(471, ['показатель','показателя','показателей']). */
export function pluralRu(n, [one, few, many]) {
  const abs = Math.abs(n) % 100;
  const d = abs % 10;
  if (abs > 10 && abs < 20) return many;
  if (d === 1) return one;
  if (d >= 2 && d <= 4) return few;
  return many;
}

/** Короткая единица для компактных подписей. */
export function shortUnit(unit = '') {
  const u = unit.trim().toLowerCase();
  const map = [
    [/^million rubles/, 'mln ₽'],
    [/^billion rubles/, 'bln ₽'],
    [/^thousand rubles/, 'thous. ₽'],
    [/^thousand people/, 'thous. people'],
    [/^million people/, 'mln people'],
    [/^миллионов рублей/, 'млн ₽'],
    [/^миллиардов рублей/, 'млрд ₽'],
    [/^тысяч рублей/, 'тыс ₽'],
    [/^рублей/, '₽'],
    [/^тысяч человек/, 'тыс чел.'],
    [/^миллионов человек/, 'млн чел.'],
    [/^человек/, 'чел.'],
    [/^% к предыдущему году/, '% г/г'],
    [/^в процентах к предыдущему году/, '% г/г'],
    [/^в процентах/, '%'],
    [/^процентов/, '%'],
    [/^%$/, '%'],
    [/^thousand hectares/, 'thous. ha'],
    [/^тысяч гектаров/, 'тыс га'],
    [/^тысяч тонн/, 'тыс т'],
    [/^миллионов тонн/, 'млн т'],
    [/^миллиардов киловатт-часов/, 'млрд кВт·ч'],
    [/^тысяч м2/, 'тыс м²'],
    [/^тысяч квадратных метров/, 'тыс м²'],
    [/^м2/, 'м²'],
    [/^центнеров с одного гектара/, 'ц/га'],
    [/^километров/, 'км'],
    [/^штук/, 'шт.'],
  ];
  for (const [re, short] of map) {
    if (re.test(u)) return short;
  }
  return unit.length > 26 ? '' : unit;
}

/** Дельта к прошлому году: направление и текст.
 *
 * В-20 (CTO-аудит 2026-07-06): при отрицательной базе или переходе через ноль
 * процент нечитаем (сальдо −5 → +5 это не «+200%») — бейдж не показываем.
 */
export function yearDelta(value, prevValue) {
  if (value == null || prevValue == null || prevValue === 0) return null;
  if (prevValue < 0 || value < 0) return null;
  const pct = ((value - prevValue) / Math.abs(prevValue)) * 100;
  if (!Number.isFinite(pct)) return null;
  return { pct, up: pct > 0.005, down: pct < -0.005 };
}

// Публичные SPA-пути регионального блока (ADR-0013). API выше — /api/v1/regions*.
export {
  regionHubPath,
  regionPath,
  regionIndicatorPath,
  regionMapPath,
  regionRatingPath,
  regionVsPath,
} from './sitePaths';

