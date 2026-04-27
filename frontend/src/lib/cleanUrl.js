// Список GET-параметров, которые игнорируем при отправке URL в Яндекс.Метрику.
// Синхронизирован с Clean-param в frontend/public/robots.txt.
// etext, ybaip, ysclid и пр. — служебные метки Яндекса и других трекеров;
// если оставить их в URL для ym('hit'), Метрика регистрирует каждый клик
// как уникальную «страницу входа» и не склеивает дубли.
const TRACKING_PARAMS = new Set([
  'etext', 'ybaip', 'yclid', 'ysclid', 'gclid', 'fbclid',
  '_openstat', 'openstat', 'clid', 'yandex_referrer', '_ga',
  'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'utm_referrer',
  'from', 'ref', 'ref_src', 'source',
  'mc_cid', 'mc_eid', 'igshid',
]);

export function cleanSearch(search) {
  if (!search || search === '?') return '';
  const params = new URLSearchParams(search);
  let changed = false;
  for (const key of Array.from(params.keys())) {
    if (TRACKING_PARAMS.has(key)) {
      params.delete(key);
      changed = true;
    }
  }
  if (!changed) return search.startsWith('?') ? search : `?${search}`;
  const cleaned = params.toString();
  return cleaned ? `?${cleaned}` : '';
}

export function cleanPathWithSearch(pathname, search) {
  return pathname + cleanSearch(search);
}
