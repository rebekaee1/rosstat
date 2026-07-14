import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

/**
 * Yandex.RTB (РСЯ) floor-ad: touch + desktop.
 *
 * Контракт:
 * - Loader (`window.yaContextCb` + `https://yandex.ru/ads/system/context.js`)
 *   подключается в `index.html` и в SSR (см. backend/app/services/seo_renderer.py)
 *   — один раз на документ, независимо от количества блоков.
 * - Рендерим ТОЛЬКО блок текущей платформы через
 *   `Ya.Context.AdvManager.getPlatform()` (официальный рецепт РСЯ). Рендер
 *   обоих подряд оставлял на touch пустой chrome-шелл без креатива.
 * - SPA-навигация не вызывает повторный рендер (`window.__rsyFloorAdRendered`).
 * - Embed-routes (`/embed/*`) монтируют свой ErrorBoundary без YandexRSY.
 * - `/admin/*`: не инициализируем; уже отрисованный floorAd прячется
 *   классом `rsy-hidden` на <html> (CSS в index.css).
 *
 * Empty-state (2026-07-14): если SDK оставил серый шелл «РЕКЛАМА»+X без
 * креатива (no-fill / VIDEO_ERROR / CSP media) — destroy + force-remove,
 * чтобы не перекрывать контент. Goal `rsy_floor_render` — только при
 * непустом креативе.
 *
 * Активные блоки:
 *   R-A-19489903-2 floorAd touch    — мобильные
 *   R-A-19489903-1 floorAd desktop  — десктоп
 *
 * Trap: без media-src / frame-src для РСЯ в Caddyfile видео и iframe
 * креативов молча не грузятся → пустой серый floorAd на iPhone.
 */

const RSY_BLOCKS = [
  { blockId: 'R-A-19489903-2', type: 'floorAd', platform: 'touch' },
  { blockId: 'R-A-19489903-1', type: 'floorAd', platform: 'desktop' },
];

const EMPTY_CHECK_MS = 2200;
const EMPTY_RETRY_MS = 1500;
/** SDK ставит `data-r-a-19489903-2-floorad` (= `data-` + blockId.lower + `-floorad`). */
function floorAdMarkerAttr(blockId) {
  return `data-${String(blockId).toLowerCase()}-floorad`;
}

const MARKER_ATTRS = RSY_BLOCKS.map((b) => floorAdMarkerAttr(b.blockId));

function destroyBlock(blockId) {
  try {
    window.Ya?.Context?.AdvManager?.destroy?.({ blockId });
  } catch {
    /* SDK может быть недоступен (AdBlock) */
  }
}

/** Снимает оставшийся fixed-шелл по data-маркеру блока РСЯ. */
function forceRemoveShell(blockId) {
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

/**
 * Пустой креатив: есть chrome (шелл), но нет media/текста объявления.
 * Закрытие/«РЕКЛАМА» в chrome не считаем наполнением.
 */
export function isFloorAdShellEmpty(shell) {
  if (!shell || typeof shell.querySelector !== 'function') return true;
  const media = shell.querySelector('iframe, img, video, canvas, object, embed');
  if (media) {
    if (media.tagName === 'IMG' && media.naturalWidth === 0 && media.complete) {
      /* битая картинка — не считаем fill */
    } else {
      return false;
    }
  }
  const slots = shell.querySelectorAll('.needsclick');
  if (slots.length > 0) {
    const anyFilled = [...slots].some(
      (s) => s.children.length > 0 || (s.innerText || '').trim().length > 0
    );
    if (anyFilled) return false;
    return true;
  }
  const raw = (shell.innerText || '')
    .replace(/РЕКЛАМА/gi, '')
    .replace(/advertisement/gi, '')
    .replace(/\s+/g, ' ')
    .trim();
  return raw.length < 12;
}

function findOrphanFloorShells() {
  if (typeof document === 'undefined') return [];
  return [...document.querySelectorAll('div')].filter((el) => {
    const s = window.getComputedStyle(el);
    if (s.position !== 'fixed' && s.position !== 'sticky') return false;
    const z = parseInt(s.zIndex, 10);
    if (!(z > 1_000_000)) return false;
    if (el.offsetHeight < 60) return false;
    if (el.offsetWidth < window.innerWidth * 0.8) return false;
    return isFloorAdShellEmpty(el);
  });
}

function collapseEmptyFloorAd(blockId) {
  const shell = shellForBlock(blockId);
  if (shell && isFloorAdShellEmpty(shell)) {
    destroyBlock(blockId);
    forceRemoveShell(blockId);
    return true;
  }
  // Фоллбэк: шелл без/с битым маркером (obfuscated class csr-uniq*).
  const orphans = findOrphanFloorShells();
  if (!orphans.length) return false;
  destroyBlock(blockId);
  orphans.forEach((el) => el.remove());
  forceRemoveShell(blockId);
  return true;
}

function watchEmptyFloorAd(blockId) {
  let tries = 0;
  const tick = () => {
    tries += 1;
    if (collapseEmptyFloorAd(blockId)) return;
    const shell = shellForBlock(blockId);
    if (!shell && tries >= 2) return;
    if (tries < 3) {
      window.setTimeout(tick, EMPTY_RETRY_MS);
    }
  };
  window.setTimeout(tick, EMPTY_CHECK_MS);
}

function renderFloorAd() {
  const adv = window.Ya?.Context?.AdvManager;
  if (!adv || typeof adv.render !== 'function') return;

  const platform =
    typeof adv.getPlatform === 'function' ? adv.getPlatform() : null;
  const cfg =
    RSY_BLOCKS.find((b) => b.platform === platform) ||
    RSY_BLOCKS.find((b) => b.platform === 'desktop') ||
    RSY_BLOCKS[0];

  adv.render({
    blockId: cfg.blockId,
    type: cfg.type,
    platform: cfg.platform,
    onError: () => {
      destroyBlock(cfg.blockId);
      forceRemoveShell(cfg.blockId);
    },
    onRender: () => {
      watchEmptyFloorAd(cfg.blockId);
      window.setTimeout(() => {
        if (collapseEmptyFloorAd(cfg.blockId)) return;
        if (typeof window.ym === 'function') {
          window.ym(107136069, 'reachGoal', 'rsy_floor_render');
        }
      }, EMPTY_CHECK_MS + 50);
    },
  });

  // onRender может не прийти при partial chrome — всё равно сторожим шелл.
  watchEmptyFloorAd(cfg.blockId);
}

export default function YandexRSY() {
  const { pathname } = useLocation();
  const isAdmin = pathname.startsWith('/admin');

  useEffect(() => {
    if (typeof document === 'undefined') return;
    document.documentElement.classList.toggle('rsy-hidden', isAdmin);
    if (isAdmin) {
      for (const b of RSY_BLOCKS) {
        destroyBlock(b.blockId);
        forceRemoveShell(b.blockId);
      }
    }
  }, [isAdmin]);

  useEffect(() => {
    if (typeof window === 'undefined' || isAdmin) return;
    if (window.__rsyFloorAdRendered) return;
    window.__rsyFloorAdRendered = true;

    window.yaContextCb = window.yaContextCb || [];
    window.yaContextCb.push(() => {
      try {
        renderFloorAd();
      } catch {
        // Не падаем, если РСЯ не загрузилась (CSP/AdBlock/сетевой блок).
      }
    });
  }, [isAdmin]);

  return null;
}

// Экспорт маркеров для тестов / CSS-аудита.
export const __RSY_TEST = { RSY_BLOCKS, MARKER_ATTRS, isFloorAdShellEmpty };
