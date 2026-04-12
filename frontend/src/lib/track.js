const COUNTER_ID = 107136069;

function ym(...args) {
  if (typeof window.ym === 'function') {
    window.ym(...args);
  }
}

export function track(event, params) {
  ym(COUNTER_ID, 'reachGoal', event, params);
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

  OUTBOUND_LINK: 'outbound_link',
  CONTACT_EMAIL: 'contact_email',
  API_RETRY: 'api_retry',
  ERROR_RELOAD: 'error_reload',
};
