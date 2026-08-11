import { CATEGORIES } from './categories';
import { visitorId } from './behavior';

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

// Идентичность пользователя для аналитики. Заполняется AuthProvider'ом при
// резолве /me: гость → { authed:false }, зарегистрированный → { authed:true,
// userId }. Признак authed уходит В КАЖДОЕ событие (ym + first-party collector),
// поэтому в Метрике сегментируем «гость vs зарегистрированный» по параметру
// визита, а на бэкенде — по authed/user_id в frontend_events. userId (хэш из
// /me) дополнительно уходит в ym setUserID для кросс-девайс склейки.
let _identity = { authed: false, userId: null };
let _ymIdentityApplied = null;

function applyYmIdentity() {
  const key = `${_identity.authed ? 1 : 0}:${_identity.userId || ''}`;
  if (key === _ymIdentityApplied) return;
  _ymIdentityApplied = key;
  if (_identity.userId) ym(COUNTER_ID, 'setUserID', String(_identity.userId));
  ym(COUNTER_ID, 'userParams', {
    authed: _identity.authed ? 1 : 0,
    audience: _identity.authed ? 'registered' : 'guest',
  });
}

/**
 * Устанавливает идентичность для аналитики. Вызывается из AuthProvider при
 * каждом изменении состояния авторизации. Идемпотентно для Метрики.
 */
export function setTrackedIdentity({ authed, userId } = {}) {
  _identity = { authed: !!authed, userId: userId || null };
  applyYmIdentity();
  // Поведенческий слой (behavior.js) получает ту же идентичность: батчи
  // сырых событий несут authed-флаг для разреза гость/зарегистрированный.
  import('./behavior').then((m) => m.behaviorSetIdentity(_identity)).catch(() => {});
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
  // Признак аудитории — в каждое событие. authed уже мог прийти в params
  // (напр. compare_image_download), но здесь гарантируем его всегда.
  payload = { ...(payload || {}), authed: _identity.authed ? 1 : 0 };
  ym(COUNTER_ID, 'reachGoal', event, payload);
  sendEvent(event, payload);
}

export function sendEvent(eventName, params) {
  if (typeof window === 'undefined') return;
  const body = JSON.stringify({
    event_name: eventName,
    session_id: sessionId(),
    visitor_id: visitorId(),
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

  COMPARE_OPEN: 'compare_open',
  COMPARE_CHANGE: 'compare_change',
  COMPARE_RANGE: 'compare_range',
  COMPARE_ADD: 'compare_add',
  COMPARE_SEARCH: 'compare_search',
  COMPARE_IMAGE_DOWNLOAD: 'compare_image_download',
  COMPARE_IMAGE_BLOCKED: 'compare_image_blocked',
  COMPARE_LIMIT_HIT: 'compare_limit_hit',

  // Скачивание графика картинкой (per-indicator). Гость → гейт регистрации,
  // авторизованный → PNG без watermark (правило 2026-07-08). Каждое — цель Метрики.
  CHART_IMAGE_DOWNLOAD: 'chart_image_download',
  CHART_IMAGE_BLOCKED: 'chart_image_blocked',
  // GIF карты регионов по годам — тот же гейт, что PNG (только auth, без watermark).
  REGIONS_MAP_GIF_DOWNLOAD: 'regions_map_gif_download',
  REGIONS_MAP_GIF_BLOCKED: 'regions_map_gif_blocked',

  CALC_DIRECTION: 'calc_direction',
  CALC_PRESET: 'calc_preset',
  CALC_SHARE: 'calc_share',
  CALC_COPY_RESULT: 'calc_copy_result',
  CALC_CHART_MODE: 'calc_chart_mode',
  CALC_BREAKDOWN: 'calc_breakdown',
  CALC_MORTGAGE: 'calc_mortgage',
  CALC_COMPOUND: 'calc_compound',
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
  HOME_TODAY_CLICK: 'home_today_click',
  HOME_WORKBENCH_TAB: 'home_workbench_tab',
  HOME_REGIONS_METRIC: 'home_regions_metric',
  HOME_REGIONS_CTA: 'home_regions_cta',
  HOME_COUNTRIES_METRIC: 'home_countries_metric',
  HOME_COUNTRIES_MACROREGION: 'home_countries_macroregion',
  HOME_COUNTRIES_CTA: 'home_countries_cta',

  CATEGORY_TILE_CLICK: 'category_tile_click',
  RELATED_INDICATOR_CLICK: 'related_indicator_click',
  BREADCRUMB_CLICK: 'breadcrumb_click',
  RELATED_LINK_CLICK: 'related_link_click',
  SCROLL_DEPTH: 'scroll_depth',
  FORECAST_VIEW: 'forecast_view',
  SOURCE_LINK_CLICK: 'source_link_click',
  API_LOAD_ERROR: 'api_load_error',
  EMPTY_STATE: 'empty_state',
  EMBED_RUNTIME_VIEW: 'embed_runtime_view',
  EXPERIMENT_EXPOSURE: 'experiment_exposure',

  INDICATOR_VIEW: 'indicator_view',
  FREQUENCY_SWITCH: 'frequency_switch',

  OUTBOUND_LINK: 'outbound_link',
  CONTACT_EMAIL: 'contact_email',
  CONSENT_UPDATE: 'consent_update',
  API_RETRY: 'api_retry',
  ERROR_RELOAD: 'error_reload',

  // Личный кабинет / конверсия (ADR-0007 Phase 2). Каждое CTA — цель Метрики,
  // попадает в ежедневный Telegram-дайджест (бэкенд тянет все цели счётчика).
  // Чтобы достижения считались как цель, одноимённый goal должен существовать
  // в счётчике Метрики (id = это значение, тип «JavaScript-событие»).
  AUTH_SIGNUP: 'signup',
  AUTH_LOGIN: 'login_success',
  OAUTH_START: 'oauth_start',
  NEWSLETTER_OPT_IN: 'newsletter_opt_in',
  NEWSLETTER_OPT_OUT: 'newsletter_opt_out',
  DOWNLOAD_LIMIT_HIT: 'download_limit',
  REGISTER_NUDGE_VIEW: 'register_nudge_view',
  REGISTER_NUDGE_EXPAND: 'register_nudge_expand',
  REGISTER_NUDGE_CTA: 'register_nudge_cta',
  HEADER_LOGIN_CLICK: 'header_login_click',
  HEADER_REGISTER_CLICK: 'header_register_click',

  // Обратная связь (ADR-0007 Phase 2): плавающее окно для авторизованных +
  // форма в кабинете. Отправка уходит в Telegram-бот мгновенно.
  FEEDBACK_NUDGE_VIEW: 'feedback_nudge_view',
  FEEDBACK_NUDGE_EXPAND: 'feedback_nudge_expand',
  FEEDBACK_NUDGE_CTA: 'feedback_nudge_cta',
  FEEDBACK_SUBMIT: 'feedback_submit',

  // Спрос-аналитика поиска: что пользователи ищут — введённое (debounce),
  // выбранное и брошенное. Агрегируется в ежедневный Telegram-дайджест,
  // запросы с 0 результатов = карта пробелов в каталоге индикаторов.
  SEARCH_QUERY: 'search_query',
  SEARCH_SELECT: 'search_select',
  SEARCH_ABANDON: 'search_abandon',

  // Методология прогнозирования: переход с карточки индикатора (подсказка у
  // переключателя «Прогноз») на объясняющую страницу /methodology.
  METHODOLOGY_CLICK: 'methodology_click',

  // Региональный блок: карта, сравнение регионов, переходы макро ↔ регионы.
  REGIONS_VIEW_TOGGLE: 'regions_view_toggle',
  REGIONS_MAP_METRIC: 'regions_map_metric',
  REGIONS_MAP_SELECT: 'regions_map_select',
  REGIONS_MAP_TIMELINE: 'regions_map_timeline',
  // «Контрасты России» на /regions — цикл по следующей паре показателей.
  REGIONS_CONTRASTS_SHUFFLE: 'regions_contrasts_shuffle',
  REGION_COMPARE_ADD: 'region_compare_add',
  REGION_CROSSLINK_CLICK: 'region_crosslink_click',
  // Просмотр карточки регионального показателя — first-party аналог
  // indicator_view, чтобы просмотры регионов попадали в «Пульс», а не только
  // в хиты Метрики.
  REGION_INDICATOR_VIEW: 'region_indicator_view',
};
