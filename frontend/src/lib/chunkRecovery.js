// Устаревшая вкладка после релиза: хэшированные чанки старой сборки пропали,
// динамический import() / React.lazy падает. Лечится одной перезагрузкой за
// новым index.html. Этот модуль решает, МОЖНО ли перезагрузить, и страхует от
// петли. Без React: используется из main.jsx и ErrorBoundary.

const STORAGE_KEY = 'fe:chunk-reload:at';

/** Не чаще одной автоперезагрузки за этот интервал (защита от петли). */
export const RELOAD_GUARD_MS = 5 * 60 * 1000;
/** Ввод в поле за последние N мс считаем «пользователь печатает». */
export const RECENT_INPUT_MS = 30 * 1000;

const CHUNK_ERROR_RE = new RegExp([
  'Failed to fetch dynamically imported module', // Chromium
  'error loading dynamically imported module', // Firefox
  'Importing a module script failed', // Safari
  'ChunkLoadError',
  'Loading (?:CSS )?chunk [\\w-]+ failed', // webpack-стиль
  'Unable to preload CSS',
].join('|'), 'i');

/** Ошибка загрузки чанка (по сообщению/имени), а не любая ошибка кода. */
export function isChunkLoadError(error) {
  if (!error) return false;
  if (typeof error === 'string') return CHUNK_ERROR_RE.test(error);
  return CHUNK_ERROR_RE.test(`${error.name || ''} ${error.message || ''}`);
}

// --- Занятость пользователя -------------------------------------------------

const NON_TEXT_INPUT_TYPES = new Set([
  'button', 'checkbox', 'radio', 'range', 'submit', 'reset', 'file', 'image', 'hidden', 'color',
]);

function isTextEntry(el) {
  if (!el) return false;
  const tag = el.tagName;
  if (tag === 'TEXTAREA') return !el.readOnly;
  if (tag === 'INPUT') return !el.readOnly && !NON_TEXT_INPUT_TYPES.has(String(el.type || 'text').toLowerCase());
  return Boolean(el.isContentEditable);
}

let lastInputAt = 0;
let activeJobs = 0;

/** Слушатель ввода в поля; вешается один раз при старте приложения. */
export function watchUserInput(target = typeof window !== 'undefined' ? window : null, now = Date.now) {
  if (!target) return () => {};
  const onInput = (event) => {
    if (isTextEntry(event.target)) lastInputAt = now();
  };
  target.addEventListener('input', onInput, true);
  return () => target.removeEventListener('input', onInput, true);
}

/** Помечает идущую загрузку/выгрузку: пока она идёт, перезагружать нельзя. */
export function beginBusy() {
  activeJobs += 1;
  let done = false;
  return () => {
    if (done) return;
    done = true;
    activeJobs = Math.max(0, activeJobs - 1);
  };
}

/** Оборачивает промис долгой операции (экспорт, скачивание) в beginBusy. */
export function trackBusy(promise) {
  const end = beginBusy();
  return Promise.resolve(promise).finally(end);
}

/** Пользователь вводит текст или идёт загрузка/скачивание. */
export function isUserBusy({ doc = typeof document !== 'undefined' ? document : null, now = Date.now } = {}) {
  if (activeJobs > 0) return true;
  if (doc && isTextEntry(doc.activeElement)) return true;
  return lastInputAt > 0 && now() - lastInputAt < RECENT_INPUT_MS;
}

/** Только для тестов. */
export function resetBusyStateForTests() {
  lastInputAt = 0;
  activeJobs = 0;
}

// --- Решение о перезагрузке -------------------------------------------------

// Перезагрузка допустима, только если отметка записана в sessionStorage. В
// приватном режиме/при переполнении квоты безопаснее показать экран ошибки,
// чем уйти в цикл перезагрузок.
export function createChunkRecovery({
  release,
  getStorage,
  reload,
  now = Date.now,
  isBusy = () => isUserBusy({ now }),
  guardMs = RELOAD_GUARD_MS,
}) {
  let reloading = false;
  // true — перезагрузка запущена (или уже идёт); false — показать обычную ошибку.
  return () => {
    if (reloading) return true;
    if (isBusy()) return false;
    const t = now();
    try {
      const storage = getStorage();
      const raw = storage.getItem(STORAGE_KEY);
      if (raw) {
        const last = JSON.parse(raw);
        const age = t - Number(last?.at);
        // age < 0 — часы ушли назад: тоже считаем «недавно», петля хуже ошибки.
        if (!Number.isFinite(age) || age < guardMs) return false;
      }
      const mark = JSON.stringify({ at: t, release: String(release) });
      storage.setItem(STORAGE_KEY, mark);
      if (storage.getItem(STORAGE_KEY) !== mark) return false;
    } catch {
      return false;
    }
    reloading = true;
    reload();
    return true;
  };
}

let shared = null;

/** Общая точка для main.jsx и ErrorBoundary: одна отметка, один флаг reloading. */
export function recoverFromStaleChunk() {
  if (!shared) {
    shared = createChunkRecovery({
      // URL входного чанка содержит content-hash, в том числе в локальных сборках.
      release: import.meta.url,
      getStorage: () => window.sessionStorage,
      reload: () => window.location.reload(),
    });
  }
  return shared();
}

/** Подписки main.jsx: preload-ошибка Vite, непойманный import(), ошибка React. */
export function installChunkRecovery(target = window, recover = recoverFromStaleChunk) {
  watchUserInput(target);
  // event не гасим: Vite тогда отдаёт lazy() undefined («reading 'default'»).
  // Пусть исходная ошибка дойдёт до ErrorBoundary — он покажет пустой экран
  // на время перезагрузки, а при отказе (занят/петля) обычный экран ошибки.
  target.addEventListener('vite:preloadError', () => { recover(); });
  target.addEventListener('unhandledrejection', (event) => {
    if (isChunkLoadError(event.reason)) recover();
  });
  target.addEventListener('error', (event) => {
    if (isChunkLoadError(event.error || event.message)) recover();
  });
}
