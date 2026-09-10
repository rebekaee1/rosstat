// Same-origin return paths only: shared by email auth, OAuth, and auth links.
const KEY = 'fe_auth_export';
const VIEW_KEY = 'fe_auth_view';
const TTL = 30 * 60 * 1000;
const unsafeChars = value => [...value].some(char => char === '\\' || char.charCodeAt(0) < 32);
export function safeReturnTo(value) {
  if (typeof value !== 'string' || !value.startsWith('/') || value.startsWith('//') || (unsafeChars(value) || value.includes(' '))) return '/account';
  try {
    const decoded = decodeURIComponent(value);
    if (decoded.startsWith('//') || unsafeChars(decoded)) return '/account';
    const u = new URL(value, window.location.origin);
    if (u.origin !== window.location.origin || /^\/(login|register)(\/|$)/.test(u.pathname)) return '/account';
    return u.pathname + u.search + u.hash;
  } catch { return '/account'; }
}
export const currentReturnTo = () => safeReturnTo(window.location.pathname + window.location.search + window.location.hash);
export const authLink = (page, next = currentReturnTo()) => `${page}?next=${encodeURIComponent(safeReturnTo(next))}`;
export const prepareAuthReturn = () => window.dispatchEvent(new Event('fe:auth-leave'));
function read(key) {
  try {
    const v = JSON.parse(sessionStorage.getItem(key));
    return v && Date.now() - v.at < TTL && Date.now() >= v.at ? v : null;
  } catch { return null; }
}
function write(key, data) {
  try { sessionStorage.setItem(key, JSON.stringify({ ...data, at: Date.now() })); return true; } catch { return false; }
}
export function rememberExport(payload) {
  clearPendingExport();
  // The API already caps request size. Do not fill browser storage with oversized data.
  const path = currentReturnTo();
  if (JSON.stringify(payload).length <= 512000 && write(KEY, { path, payload })) return;
  // A small explicit fallback survives quota pressure without retaining a large dataset.
  write(KEY, { path, payload: null, filename: payload.filename });
}
export function pendingExport() { return read(KEY); }
export function clearPendingExport() { try { sessionStorage.removeItem(KEY); } catch { /* unavailable */ } }
export function rememberAuthView(key, state) { write(VIEW_KEY, { path: currentReturnTo(), key, state }); }
export function restoredAuthView(key) {
  const v = read(VIEW_KEY);
  return v?.path === currentReturnTo() && v.key === key ? v.state : null;
}
