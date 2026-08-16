/** Публичный origin сайта (canonical / embed / Метрика file). Дефолт = текущий прод. */
export const SITE_ORIGIN = (
  import.meta.env.VITE_PUBLIC_BASE_URL || 'https://forecasteconomy.com'
).replace(/\/$/, '');

export const SITE_HOST = SITE_ORIGIN.replace(/^https?:\/\//, '');
