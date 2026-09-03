/**
 * Yandex.RTB (РСЯ) floor-ad: загрузка/рендер/детекция fill (логика без React).
 *
 * Контракт:
 * - Loader (`window.yaContextCb` + `https://yandex.ru/ads/system/context.js`)
 *   подключается в `index.html` и в SSR (см. backend/app/services/seo_renderer.py)
 *   — один раз на документ, независимо от количества блоков.
 * - Рендерим ТОЛЬКО блок текущей платформы через
 *   `Ya.Context.AdvManager.getPlatform()` (официальный рецепт РСЯ). Рендер
 *   обоих подряд оставлял на touch пустой chrome-шелл без креатива.
 * - SPA-навигация (2026-09-03): маршрут сменился — блок обновляем
 *   (`destroy` + `render` с инкрементом `pageNumber`, официальный рецепт РСЯ
 *   для динамического контента), но не чаще `REFRESH_COOLDOWN_MS`. До этой
 *   правки реклама рендерилась один раз на документ: читатель, смотрящий
 *   десять карточек, видел одно объявление за визит.
 * - Запрос объявления делает только человек: гейт по доверенному вводу живёт
 *   в `frontend/public/consent.js` (`armAdsGate`). Инцидент 2026-08-27:
 *   роботы просили рекламу на SSR-страницах, fill rate упал 97% → 11%.
 * - Empty-state (2026-07-14, rev.2): watchdog ~6 с с destroy УБРАН.
 *   Он снимал живой Floor Ad после видимого fill (late iframe / video /
 *   Shadow DOM — детектор «пусто» давал false positive). Снос живой рекламы
 *   хуже серого chrome. Destroy только в `onError` (явный no-bid / SDK error).
 *   Fill-детектор остаётся для цели Метрики `rsy_floor_render`.
 *
 * Активные блоки:
 *   R-A-19489903-2 floorAd touch    — мобильные
 *   R-A-19489903-1 floorAd desktop  — десктоп
 *
 * Trap: без media-src / frame-src для РСЯ в Caddyfile видео и iframe
 * креативов молча не грузятся → пустой серый floorAd на iPhone.
 */

export const RSY_BLOCKS = [
  { blockId: 'R-A-19489903-2', type: 'floorAd', platform: 'touch' },
  { blockId: 'R-A-19489903-1', type: 'floorAd', platform: 'desktop' },
];

/** Цель Метрики: ждём fill, не уничтожаем шелл. */
const FILL_GOAL_CHECK_MS = 8_000;

/**
 * Бывший EMPTY_CHECK_MS (~6 с) уничтожал рекламу. Оставляем константу
 * заведомо «выключенной» (>1 час), чтобы тесты ловили регрессию к ~6 с.
 * Auto-destroy по таймеру не вызывается.
 */
export const EMPTY_CHECK_MS = 3_600_000;

/** SDK ставит `data-r-a-19489903-2-floorad` (= `data-` + blockId.lower + `-floorad`). */
function floorAdMarkerAttr(blockId) {
  return `data-${String(blockId).toLowerCase()}-floorad`;
}

export const MARKER_ATTRS = RSY_BLOCKS.map((b) => floorAdMarkerAttr(b.blockId));

const MEDIA_SEL = 'iframe, img, video, canvas, object, embed, source, yanetag, [data-videoname]';

export function destroyBlock(blockId) {
  try {
    window.Ya?.Context?.AdvManager?.destroy?.({ blockId });
  } catch {
    /* SDK может быть недоступен (AdBlock) */
  }
}

/** Снимает оставшийся fixed-шелл по data-маркеру блока РСЯ. */
export function forceRemoveShell(blockId) {
  if (typeof document === 'undefined') return;
  const attr = floorAdMarkerAttr(blockId);
  document.querySelectorAll(`[${attr}]`).forEach((marker) => {
    let el = marker;
    while (el && el !== document.body) {
      const pos = window.getComputedStyle(el).position;
      if (pos === 'fixed' || pos === 'sticky') {
        el.remove();
        return;
      }
      el = el.parentElement;
    }
    marker.remove();
  });
}

function shellForBlock(blockId) {
  const attr = floorAdMarkerAttr(blockId);
  const marker = document.querySelector(`[${attr}]`);
  if (!marker) return null;
  let el = marker;
  while (el && el !== document.body) {
    const pos = window.getComputedStyle(el).position;
    if (pos === 'fixed' || pos === 'sticky') return el;
    el = el.parentElement;
  }
  return marker.parentElement;
}

export function hasLiveMedia(root) {
  if (!root || typeof root.querySelectorAll !== 'function') return false;
  const nodes = root.querySelectorAll(MEDIA_SEL);
  for (const media of nodes) {
    if (media.tagName === 'IMG') {
      if (media.complete && media.naturalWidth === 0) continue;
      return true;
    }
    if (media.tagName === 'SOURCE') {
      if (media.getAttribute?.('src') || media.src) return true;
      continue;
    }
    return true;
  }
  return false;
}

/**
 * Пустой креатив: есть chrome (шелл), но нет media/текста объявления.
 *
 * Консервативно: при сомнении — не пустой. Пустой `.needsclick` сам по себе
 * НЕ доказательство пустоты (РСЯ часто держит слот, пока video/iframe
 * догружается в соседний узел / Shadow DOM).
 *
 * Используется только для цели Метрики, не для auto-destroy.
 */
export function isFloorAdShellEmpty(shell) {
  if (!shell || typeof shell.querySelector !== 'function') return true;
  if (hasLiveMedia(shell)) return false;

  const slots =
    typeof shell.querySelectorAll === 'function'
      ? shell.querySelectorAll('.needsclick')
      : [];
  if (slots.length > 0) {
    const anyFilled = [...slots].some(
      (s) => s.children.length > 0 || (s.innerText || '').trim().length > 0
    );
    if (anyFilled) return false;
  }

  const raw = (shell.innerText || '')
    .replace(/РЕКЛАМА/gi, '')
    .replace(/advertisement/gi, '')
    .replace(/закрыть/gi, '')
    .replace(/\s+/g, ' ')
    .trim();
  if (raw.length >= 12) return false;

  return true;
}

function trackFloorFillGoal(blockId) {
  window.setTimeout(() => {
    const shell = shellForBlock(blockId);
    if (!shell || isFloorAdShellEmpty(shell)) return;
    if (typeof window.ym === 'function') {
      window.ym(107136069, 'reachGoal', 'rsy_floor_render');
    }
  }, FILL_GOAL_CHECK_MS);
}

/** Блок под текущую платформу (официальный рецепт РСЯ: getPlatform). */
export function blockForPlatform(adv) {
  const platform =
    adv && typeof adv.getPlatform === 'function' ? adv.getPlatform() : null;
  return (
    RSY_BLOCKS.find((b) => b.platform === platform) ||
    RSY_BLOCKS.find((b) => b.platform === 'desktop') ||
    RSY_BLOCKS[0]
  );
}

/**
 * Минимальный интервал между обновлениями блока на SPA-навигации.
 *
 * Зачем: floorAd — прилипающая плашка. Обновлять её на каждый клик по меню
 * значит мигать рекламой у читателя и множить запросы без показов. 60 с —
 * компромисс: читатель, изучающий 3–4 карточки подряд, получает новое
 * объявление, «пролистывание» каталога — нет.
 */
export const REFRESH_COOLDOWN_MS = 60_000;

let lastRenderAt = 0;
let pageNumber = 0;

/** Сброс счётчиков (тесты; в браузере состояние живёт до перезагрузки). */
export function __resetFloorAdState() {
  lastRenderAt = 0;
  pageNumber = 0;
}

/**
 * Рендер блока. `refresh=true` — повторный вызов при смене маршрута SPA:
 * прежний блок сносим (`destroy`) и просим новое объявление с инкрементом
 * `pageNumber`, как требует документация РСЯ для динамического контента.
 *
 * Возвращает true, если запрос объявления ушёл.
 */
export function renderFloorAd({ refresh = false, now = Date.now() } = {}) {
  const adv = window.Ya?.Context?.AdvManager;
  if (!adv || typeof adv.render !== 'function') return false;

  const cfg = blockForPlatform(adv);

  if (refresh) {
    if (now - lastRenderAt < REFRESH_COOLDOWN_MS) return false;
    // Контейнер занят предыдущим объявлением: без destroy SDK молча
    // проигнорирует повторный render.
    destroyBlock(cfg.blockId);
    forceRemoveShell(cfg.blockId);
  }

  lastRenderAt = now;
  pageNumber += 1;

  adv.render({
    blockId: cfg.blockId,
    type: cfg.type,
    platform: cfg.platform,
    pageNumber,
    onError: () => {
      // Единственный путь auto-destroy: явный no-bid / ошибка SDK.
      destroyBlock(cfg.blockId);
      forceRemoveShell(cfg.blockId);
    },
    onRender: () => {
      trackFloorFillGoal(cfg.blockId);
    },
  });
  return true;
}

// Экспорт маркеров для тестов / CSS-аудита.
export const __RSY_TEST = {
  RSY_BLOCKS,
  MARKER_ATTRS,
  isFloorAdShellEmpty,
  EMPTY_CHECK_MS,
  hasLiveMedia,
  REFRESH_COOLDOWN_MS,
  /** true = timer auto-destroy отключён; снос только через onError. */
  AUTO_DESTROY_DISABLED: true,
};
