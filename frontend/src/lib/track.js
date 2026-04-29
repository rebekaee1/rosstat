import { CATEGORIES } from './categories';

const COUNTER_ID = 107136069;
const EVENT_COLLECTOR_PATH = '/api/v1/analytics/events';

function sessionId() {
  const key = 'fe:analytics:session';
  try {
    let value = window.sessionStorage.getItem(key);
    if (!value) {
      value = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
      window.sessionStorage.setItem(key, value);
    }
    return value;
  } catch {
    return null;
  }
}

function ym(...args) {
  if (typeof window.ym === 'function') {
    window.ym(...args);
  }
}

/**
 * Resolves a category slug from indicator's `category` field (apiCategory in CATEGORIES).
 * Returns null if no match — caller must guard against null when adding to params.
 */
export function categorySlugFromApi(apiCategory) {
  if (!apiCategory) return null;
  const c = CATEGORIES.find((cat) => cat.apiCategory === apiCategory);
  return c?.slug ?? null;
}

/**
 * Augments tracked params with `category` slug based on indicator object.
 * Used by call sites that have access to an indicator (or its api category).
 * Caller passes `indicator?.category` as `apiCategory`.
 */
export function withCategory(params, apiCategory) {
  const slug = categorySlugFromApi(apiCategory);
  if (!slug) return params;
  return { ...(params || {}), category: slug };
}

/**
 * Track event. If `params.indicatorCategory` is provided, it is converted into
 * a `category` slug via CATEGORIES lookup before sending to Yandex Metrika.
 * This lets call sites pass a single field instead of computing the slug each time.
 */
export function track(event, params) {
  let payload = params;
  if (params && typeof params === 'object' && 'indicatorCategory' in params) {
    const { indicatorCategory, ...rest } = params;
    payload = withCategory(rest, indicatorCategory);
  }
  ym(COUNTER_ID, 'reachGoal', event, payload);
  sendEvent(event, payload);
}

export function sendEvent(eventName, params) {
  if (typeof window === 'undefined') return;
  const body = JSON.stringify({
    event_name: eventName,
    session_id: sessionId(),
    url: window.location.href,
    referrer: document.referrer || null,
    params: params || {},
    occurred_at: new Date().toISOString(),
  });
  try {
    if (navigator.sendBeacon) {
      const blob = new Blob([body], { type: 'application/json' });
      navigator.sendBeacon(EVENT_COLLECTOR_PATH, blob);
      return;
    }
    fetch(EVENT_COLLECTOR_PATH, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
      keepalive: true,
    }).catch(() => {});
  } catch {
    // Analytics must never affect the product UX.
  }
}

export function trackFile(filename) {
  ym(COUNTER_ID, 'file', `https://forecasteconomy.com/downloads/${filename}`);
}

export function trackOutbound(url) {
  ym(COUNTER_ID, 'extLink', url);
}

export const events = {
  DOWNLOAD_CSV: 'download_csv',
  DOWNLOAD_EXCEL: 'download_excel',
  DOWNLOAD_ICAL: 'download_ical',

  CHART_MODE_CHANGE: 'chart_mode_change',
  CHART_RANGE_CHANGE: 'chart_range_change',
  CHART_ZOOM: 'chart_zoom',
  FORECAST_TOGGLE: 'forecast_toggle',

  TABLE_SEARCH: 'table_search',
  TABLE_SORT: 'table_sort',
  TABLE_PAGE: 'table_page',

  COMPARE_CHANGE: 'compare_change',
  COMPARE_RANGE: 'compare_range',

  CALC_DIRECTION: 'calc_direction',
  CALC_PRESET: 'calc_preset',
  CALC_SHARE: 'calc_share',
  CALC_COPY_RESULT: 'calc_copy_result',
  CALC_CHART_MODE: 'calc_chart_mode',
  CALC_BREAKDOWN: 'calc_breakdown',
  FAQ_TOGGLE: 'faq_toggle',

  CALENDAR_MONTH_NAV: 'calendar_month_nav',
  CALENDAR_SOURCE_FILTER: 'calendar_source_filter',
  CALENDAR_DAY_SELECT: 'calendar_day_select',
  CALENDAR_CLEAR_DAY: 'calendar_clear_day',

  DEMOGRAPHICS_CHART_TYPE: 'demographics_chart_type',
  DEMOGRAPHICS_CSV: 'demographics_csv',

  EMBED_TYPE_CHANGE: 'embed_type_change',
  EMBED_INDICATOR_SELECT: 'embed_indicator_select',
  EMBED_PERIOD_CHANGE: 'embed_period_change',
  EMBED_THEME_CHANGE: 'embed_theme_change',
  EMBED_SIZE_CHANGE: 'embed_size_change',
  EMBED_OPTION_TOGGLE: 'embed_option_toggle',
  EMBED_CODE_TAB: 'embed_code_tab',
  EMBED_CODE_COPY: 'embed_code_copy',

  NAV_CATEGORY_OPEN: 'nav_category_open',
  NAV_MOBILE_TOGGLE: 'nav_mobile_toggle',
  NAV_LINK_CLICK: 'nav_link_click',
  HOME_CATEGORY_CLICK: 'home_category_click',
  HOME_INDICATOR_CLICK: 'home_indicator_click',
  BREADCRUMB_CLICK: 'breadcrumb_click',
  RELATED_LINK_CLICK: 'related_link_click',
  SCROLL_DEPTH: 'scroll_depth',
  API_LOAD_ERROR: 'api_load_error',
  EMPTY_STATE: 'empty_state',
  EMBED_RUNTIME_VIEW: 'embed_runtime_view',
  EXPERIMENT_EXPOSURE: 'experiment_exposure',

  INDICATOR_VIEW: 'indicator_view',

  OUTBOUND_LINK: 'outbound_link',
  CONTACT_EMAIL: 'contact_email',
  API_RETRY: 'api_retry',
  ERROR_RELOAD: 'error_reload',
};
