/* Forecast Economy — service worker (PWA, 2026-10-05).
 *
 * Принципы (владелец: пользователь не должен увидеть устаревшие числа):
 *   - НЕ кэшируем HTML, API, графики и данные. Единственный кэш — офлайн-страница
 *     и её иконка; кладутся при установке, отдаются ТОЛЬКО когда сеть недоступна
 *     у навигации. Все остальные запросы service worker не перехватывает.
 *   - Обновление: байты файла меняются на каждой сборке (__SW_VERSION__ подставляет
 *     Vite), skipWaiting + clients.claim, старые кэши `fe-` удаляются при активации.
 *   - Аварийный выход (kill-switch) БЕЗ пересборки: GET /api/v1/pwa/config; если
 *     `sw_enabled === false`, service worker снимает регистрацию и чистит кэши.
 *     Проверка — при активации и не чаще раза в 30 минут при навигации; ошибка
 *     сети выключением не считается. Клиент (lib/pwa.js) делает то же самое.
 *   - push / notificationclick — заготовка: сервер ничего не отправляет, пока не включены
 *     оба флага отправки (backend app/services/web_push.py), а подписка создаётся только по
 *     явному действию пользователя (lib/pushSubscription.js, на него нигде нет вызовов).
 */
const VERSION = '__SW_VERSION__';
const CACHE = `fe-offline-${VERSION}`;
const OFFLINE_URL = '/offline.html';
const PRECACHE = [OFFLINE_URL, '/icons/icon-192.png'];
const CONFIG_URL = '/api/v1/pwa/config';
const KILL_CHECK_EVERY_MS = 30 * 60 * 1000;

let lastKillCheck = 0;

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE)
      // cache: 'reload' — офлайн-страница всегда свежая, не из HTTP-кэша браузера.
      .then((cache) => Promise.all(PRECACHE.map((url) => cache.add(new Request(url, { cache: 'reload' })))))
      .then(() => self.skipWaiting())
      // Не удалось положить офлайн-страницу — всё равно ставимся: без неё нет только запасного экрана.
      .catch(() => self.skipWaiting()),
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(names.filter((n) => n.startsWith('fe-') && n !== CACHE).map((n) => caches.delete(n)));
    await self.clients.claim();
    await killIfDisabled(true);
  })());
});

async function killIfDisabled(force) {
  const now = Date.now();
  if (!force && now - lastKillCheck < KILL_CHECK_EVERY_MS) return;
  lastKillCheck = now;
  try {
    const response = await fetch(CONFIG_URL, { cache: 'no-store', credentials: 'omit' });
    if (!response.ok) return;
    const config = await response.json();
    if (config && config.sw_enabled === false) {
      const names = await caches.keys();
      await Promise.all(names.map((n) => caches.delete(n)));
      await self.registration.unregister();
    }
  } catch (_) { /* сеть недоступна: не выключаем */ }
}

self.addEventListener('fetch', (event) => {
  const request = event.request;
  // Только навигации по страницам. Данные, API, ассеты, картинки — напрямую в сеть, без нашего кэша.
  if (request.mode !== 'navigate') return;
  event.waitUntil(killIfDisabled(false));
  event.respondWith(
    fetch(request).catch(async () => {
      const cached = await caches.match(OFFLINE_URL, { cacheName: CACHE });
      return cached || new Response('Offline', { status: 503, headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
    }),
  );
});

// ── Push (заготовка, ничего не запрашивает и не показывает без серверной отправки) ──
self.addEventListener('push', (event) => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch (_) { data = {}; }
  const title = typeof data.title === 'string' && data.title ? data.title.slice(0, 120) : 'Forecast Economy';
  const options = {
    body: typeof data.body === 'string' ? data.body.slice(0, 300) : '',
    icon: '/icons/icon-192.png',
    badge: '/icons/icon-192.png',
    tag: typeof data.tag === 'string' ? data.tag.slice(0, 64) : undefined,
    data: { url: typeof data.url === 'string' ? data.url : '/' },
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  // Открываем только страницы нашего origin: произвольный URL из payload не доверяем.
  let target = '/';
  try {
    const url = new URL((event.notification.data && event.notification.data.url) || '/', self.location.origin);
    if (url.origin === self.location.origin) target = url.pathname + url.search + url.hash;
  } catch (_) { /* остаётся / */ }
  event.waitUntil((async () => {
    const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    for (const client of windows) {
      if ('focus' in client) {
        await client.focus();
        if ('navigate' in client) { try { await client.navigate(target); } catch (_) { /* iOS */ } }
        return;
      }
    }
    await self.clients.openWindow(target);
  })());
});
