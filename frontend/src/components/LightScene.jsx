import { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { isReservedFirstSegment } from '../lib/sitePaths';
import { applySceneMode, heroKindForPath, parallaxOffset, readSceneMode } from '../lib/sceneBudget';
import { useLightPointer } from '../lib/useLightPointer';
import '../styles/k1-scene.css';

/**
 * Сцена света (раунд 3, K1): всё, что даёт стеклу что преломлять: слои под страницей и кадр граней героя поверх неё.
 * Декор: ни текста, ни фокуса, ни событий (aria-hidden, pointer-events: none).
 *
 *  1. `.fe-scene` (fixed): бумага, три каустики (золото, лёд, роза) с дрейфом 40 с, текстура граней (≥768 px),
 *     6 силуэтов граней в боковых полях (≥1600 px) с параллаксом 0,15 / 0,3. На телефоне только каустики.
 *  2. [снят в круге 6, слой не рендерится] `.fe-scene-hero` (абсолютно в верху страницы, поверх страницы, multiply): кадр граней в пустой середине hero
 *     карточки страны и справа от цифр на 404, только от 768 px; монтируется после загрузки страницы, чтобы не мешать
 *     LCP. Размеры заданы (aspect-ratio в CSS, width/height на img и source), сдвига вёрстки нет.
 *     Главная кристаллов героя больше не имеет (круг 6, зона B): её объект сцены, стеклянная F, стоит внутри плиты
 *     планеты и рядом с заголовком на телефоне (`k7-home.css`; включается атрибутом `html[data-fe-f="on"]`,
 *     который ставит эта сцена после загрузки страницы).
 *  2б. `.fe-scene__f` (внутри fixed-слоя, под страницей): одна большая стеклянная F на каждой остальной странице
 *     (показатель, рейтинг, прогнозы, валюты...), а на телефоне ещё и у страны и 404, где кристаллов героя нет.
 *     Лежит за стеклом панелей: даёт ему что преломлять, но не лежит под заголовком (панели матовые).
 *  3. `.fe-scene-leak` (абсолютно, только ≥1024 px): «утечка света» за героем и за подвалом, режим screen.
 *
 * Бюджет, выключатели и режимы: `lib/sceneBudget.js`. Классы `.fe-glint`, `.fe-cursor-light`, `.fe-drift`
 * (стили в `styles/k1-scene.css`, слушатели в `lib/useLightPointer.js`) доступны всем зонам.
 */

// Грань-«змеевик»: 4 фасета вокруг центра, без обводки. Цвета берутся из градиентов в <defs> ниже.
const SHARD_POINTS = {
  top: '50,0',
  right: '94,58',
  bottom: '50,168',
  left: '6,58',
  center: '50,74',
};

// Позиции в боковых полях: k задаёт отступ от края окна как долю ширины поля (свободное место сбоку от
// контента, считается в CSS из --fe-container-data), w это максимальная ширина грани. y в долях высоты окна.
// depth: 0,15 дальний слой, 0,3 ближний.
const SHARDS = [
  { id: 'l1', side: 'left', k: 0.1, y: '16%', w: 64, depth: 0.15, rot: -12, dur: 13, delay: -2, tone: 'champagne' },
  { id: 'l2', side: 'left', k: 0.18, y: '50%', w: 92, depth: 0.3, rot: 9, dur: 11, delay: -6, tone: 'ice' },
  { id: 'l3', side: 'left', k: 0.04, y: '80%', w: 54, depth: 0.15, rot: 20, dur: 14, delay: -9, tone: 'champagne' },
  { id: 'r1', side: 'right', k: 0.08, y: '10%', w: 58, depth: 0.15, rot: 14, dur: 12, delay: -4, tone: 'ice' },
  { id: 'r2', side: 'right', k: 0.16, y: '38%', w: 96, depth: 0.3, rot: -10, dur: 10, delay: -1, tone: 'champagne' },
  { id: 'r3', side: 'right', k: 0.03, y: '70%', w: 70, depth: 0.15, rot: -18, dur: 13, delay: -7, tone: 'champagne' },
];

function Shard({ shard }) {
  const { id, side, k, y, w, depth, rot, dur, delay, tone } = shard;
  const p = SHARD_POINTS;
  return (
    <div
      className="fe-scene__par fe-scene__shard-slot"
      data-depth={depth}
      data-side={side}
      data-fe-shard={id}
      style={{ top: y, '--k': k, '--w': `${w}px` }}
    >
      <svg
        className="fe-scene__shard fe-drift"
        viewBox="0 0 100 168"
        width={w}
        height={Math.round(w * 1.68)}
        focusable="false"
        style={{ '--r': `${rot}deg`, '--fe-drift-dur': `${dur}s`, '--fe-drift-delay': `${delay}s`, '--fe-drift-y': depth > 0.2 ? '9px' : '6px' }}
      >
        <polygon points={`${p.top} ${p.right} ${p.center}`} fill={`url(#fe-k1-${tone}-hi)`} />
        <polygon points={`${p.top} ${p.left} ${p.center}`} fill={`url(#fe-k1-${tone}-mid)`} />
        <polygon points={`${p.right} ${p.bottom} ${p.center}`} fill={`url(#fe-k1-${tone}-lo)`} />
        <polygon points={`${p.left} ${p.bottom} ${p.center}`} fill={`url(#fe-k1-${tone}-mid)`} />
        <polygon points="50,10 68,52 50,64" fill="#FFFFFF" fillOpacity="0.55" />
      </svg>
    </div>
  );
}

// Блики-грани «под стеклом» (круг 5): три небольшие грани, закреплённые в разных местах окна (не только в боковых полях).
// Лежат под страницей и видны сквозь стекло и в зазорах между панелями; на телефоне скрыты. Координаты в долях окна.
const GLINTS = [
  { id: 'g1', left: '21vw', top: '66vh', w: 46, depth: 0.3, rot: 18, dur: 13, delay: -3, tone: 'champagne' },
  { id: 'g2', left: '57vw', top: '24vh', w: 58, depth: 0.15, rot: -14, dur: 11, delay: -8, tone: 'ice' },
  { id: 'g3', left: '81vw', top: '74vh', w: 52, depth: 0.3, rot: 9, dur: 14, delay: -5, tone: 'champagne' },
];

function Glint({ glint }) {
  const { id, left, top, w, depth, rot, dur, delay, tone } = glint;
  const p = SHARD_POINTS;
  return (
    <div className="fe-scene__par fe-scene__glint-slot" data-depth={depth} data-fe-glint-shard={id} style={{ left, top, '--w': `${w}px` }}>
      <svg
        className="fe-scene__glint fe-drift"
        viewBox="0 0 100 168"
        width={w}
        height={Math.round(w * 1.68)}
        focusable="false"
        style={{ '--r': `${rot}deg`, '--fe-drift-dur': `${dur}s`, '--fe-drift-delay': `${delay}s`, '--fe-drift-y': '10px' }}
      >
        <polygon points={`${p.top} ${p.right} ${p.center}`} fill={`url(#fe-k1-${tone}-hi)`} />
        <polygon points={`${p.top} ${p.left} ${p.center}`} fill={`url(#fe-k1-${tone}-mid)`} />
        <polygon points={`${p.right} ${p.bottom} ${p.center}`} fill={`url(#fe-k1-${tone}-lo)`} />
        <polygon points={`${p.left} ${p.bottom} ${p.center}`} fill={`url(#fe-k1-${tone}-mid)`} />
        <polygon points="50,10 68,52 50,64" fill="#FFFFFF" fillOpacity="0.6" />
      </svg>
    </div>
  );
}

// Цветные пятна на разной высоте окна (круг 5): под стеклом на любом месте страницы есть что-то золотое, ледяное,
// сапфировое или тёплое. Градиенты без blur-фильтра, дрейф через .fe-drift (только transform).
const SPOTS = [
  { id: 'gold', depth: 0.3, dur: 15, delay: -4 },
  { id: 'sapphire', depth: 0.15, dur: 18, delay: -9 },
  { id: 'ice', depth: 0.3, dur: 14, delay: -2 },
  { id: 'peach', depth: 0.15, dur: 16, delay: -11 },
];

function ShardDefs() {
  const stops = (a, b) => (
    <>
      <stop offset="0" stopColor={a} />
      <stop offset="1" stopColor={b} />
    </>
  );
  return (
    <svg width="0" height="0" style={{ position: 'absolute' }} focusable="false" aria-hidden="true">
      <defs>
        <linearGradient id="fe-k1-champagne-hi" x1="0" y1="0" x2="1" y2="1">{stops('#FFFBEA', '#F3E4B8')}</linearGradient>
        <linearGradient id="fe-k1-champagne-mid" x1="0" y1="0" x2="1" y2="1">{stops('#F3E4B8', '#E3CB8A')}</linearGradient>
        <linearGradient id="fe-k1-champagne-lo" x1="0" y1="0" x2="1" y2="1">{stops('#E9D7A6', '#C9A24D')}</linearGradient>
        <linearGradient id="fe-k1-ice-hi" x1="0" y1="0" x2="1" y2="1">{stops('#FFFFFF', '#DCEAF6')}</linearGradient>
        <linearGradient id="fe-k1-ice-mid" x1="0" y1="0" x2="1" y2="1">{stops('#DCEAF6', '#BFD3EA')}</linearGradient>
        <linearGradient id="fe-k1-ice-lo" x1="0" y1="0" x2="1" y2="1">{stops('#CFE0F0', '#9DB9D8')}</linearGradient>
      </defs>
    </svg>
  );
}

/** Вызвать fn, когда браузер освободится после загрузки страницы (но не позже, чем через ~1,6 с после load). */
function afterLoadIdle(fn) {
  if (typeof window === 'undefined') return () => {};
  let cancelled = false;
  let idleId = 0;
  let timerId = 0;
  const run = () => {
    if (cancelled) return;
    if (typeof window.requestIdleCallback === 'function') {
      idleId = window.requestIdleCallback(() => { if (!cancelled) fn(); }, { timeout: 1500 });
    } else {
      timerId = window.setTimeout(() => { if (!cancelled) fn(); }, 250);
    }
  };
  const onLoad = () => run();
  if (document.readyState === 'complete') run();
  else window.addEventListener('load', onLoad, { once: true });
  return () => {
    cancelled = true;
    window.removeEventListener('load', onLoad);
    if (idleId && typeof window.cancelIdleCallback === 'function') window.cancelIdleCallback(idleId);
    if (timerId) window.clearTimeout(timerId);
  };
}

/** true после загрузки страницы и простоя браузера (чтобы тяжёлые кадры не мешали LCP); в режиме экономии всегда false. */
function useDeferredMount(enabled) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    if (!enabled || mounted) return undefined;
    if (readSceneMode().lite) return undefined;
    return afterLoadIdle(() => setMounted(true));
  }, [enabled, mounted]);
  return enabled && mounted;
}

/**
 * Стеклянная F: один крупный объект сцены. `mode="all"` виден на любой ширине, `mode="phone"` только до 768 px
 * (там, где на компьютере стоят кристаллы героя). Кадр: 1300x1519 с альфой для компьютера, 856x1000 для телефона.
 */
function SceneF({ mode }) {
  const [loaded, setLoaded] = useState(false);
  const mounted = useDeferredMount(!!mode);
  const imgRef = useCallback((img) => {
    if (img && img.complete && img.naturalWidth > 0) setLoaded(true);
  }, []);
  if (!mounted) return null;
  return (
    <div className={`fe-scene__f${loaded ? ' is-ready' : ''}`} data-fe-f-mode={mode} aria-hidden="true">
      <picture>
        <source media="(min-width: 768px)" srcSet="/brand/emblem-f-2x.webp" width="1300" height="1519" />
        <img
          ref={imgRef}
          src="/brand/emblem-f-phone.webp"
          width="856"
          height="1000"
          alt=""
          loading="lazy"
          decoding="async"
          fetchPriority="low"
          onLoad={() => setLoaded(true)}
        />
      </picture>
    </div>
  );
}

/** Какой режим стеклянной F нужен странице (null: своя F или водяной знак уже есть). */
function sceneFMode(kind, pathname) {
  if (kind === 'home') return null;
  const path = String(pathname || '/').replace(/\/+$/, '');
  if (path === '/about') return null;
  if (kind === 'country' || kind === 'notfound') return 'phone';
  return 'all';
}

/** Параллакс слоёв `[data-depth]`: смещение с затуханием, только transform, один rAF на кадр прокрутки. */
function useSceneParallax(rootRef) {
  useEffect(() => {
    const root = rootRef.current;
    if (!root || typeof window === 'undefined') return undefined;
    const nodes = Array.from(root.querySelectorAll('[data-depth]')).map((el) => ({
      el,
      depth: Number(el.getAttribute('data-depth')) || 0,
    }));
    let frame = 0;
    let applied = false;

    const reset = () => {
      if (!applied) return;
      nodes.forEach(({ el }) => { el.style.transform = ''; });
      applied = false;
    };
    const update = () => {
      frame = 0;
      const html = document.documentElement;
      if (html.getAttribute('data-fe-motion') !== 'on' || window.innerWidth < 768) {
        reset();
        return;
      }
      const y = window.scrollY || 0;
      nodes.forEach(({ el, depth }) => {
        const off = parallaxOffset(y, depth, depth * 1066);
        el.style.transform = `translate3d(0, ${off.toFixed(1)}px, 0)`;
      });
      applied = true;
    };
    const schedule = () => { if (!frame) frame = window.requestAnimationFrame(update); };

    window.addEventListener('scroll', schedule, { passive: true });
    window.addEventListener('resize', schedule, { passive: true });
    schedule();
    return () => {
      window.removeEventListener('scroll', schedule);
      window.removeEventListener('resize', schedule);
      if (frame) window.cancelAnimationFrame(frame);
      reset();
    };
  }, [rootRef]);
}

/**
 * Страница 404: корень `.z2-nf`. Пока он в документе, герой получает вариант `notfound` (кристаллы справа от цифр,
 * без прямых краёв); без этой проверки адрес из одного сегмента (`/abc`) выглядел бы как карточка страны.
 * Проверка идёт по короткому таймеру после мутаций DOM. Для адресов, похожих на страну, следим всё время (профиль может не
 * загрузиться и смениться на 404), для остальных только первые 6 секунд после перехода.
 */
function useIsNotFoundPage(countryLike, pathname) {
  const [notFound, setNotFound] = useState(false);
  useEffect(() => {
    if (typeof document === 'undefined') return undefined;
    let frame = 0;
    let stopTimer = 0;
    const check = () => {
      frame = 0;
      setNotFound(!!document.querySelector('.z2-nf'));
    };
    // Короткий таймер, а не rAF: в фоновой вкладке rAF стоит, а проверка должна отработать.
    const schedule = () => { if (!frame) frame = window.setTimeout(check, 40); };
    schedule();
    const mo = typeof MutationObserver === 'function' ? new MutationObserver(schedule) : null;
    if (mo) mo.observe(document.body, { childList: true, subtree: true });
    if (!countryLike && mo) stopTimer = window.setTimeout(() => mo.disconnect(), 6000);
    return () => {
      if (mo) mo.disconnect();
      if (frame) window.clearTimeout(frame);
      if (stopTimer) window.clearTimeout(stopTimer);
    };
  }, [countryLike, pathname]);
  return notFound;
}

export default function LightScene() {
  const { pathname } = useLocation();
  const rootRef = useRef(null);
  const pathKind = heroKindForPath(pathname, isReservedFirstSegment);
  const isNotFound = useIsNotFoundPage(pathKind === 'country', pathname);
  const kind = isNotFound ? 'notfound' : pathKind;

  const fMode = sceneFMode(kind, pathname);
  const fReady = useDeferredMount(kind === 'home');

  useEffect(() => applySceneMode(), []);
  // Главная: F внутри плиты планеты и рядом с заголовком рисуется из CSS и включается этим атрибутом (после load и простоя).
  useEffect(() => {
    const html = document.documentElement;
    if (fReady) html.setAttribute('data-fe-f', 'on');
    return () => html.removeAttribute('data-fe-f');
  }, [fReady]);
  useLightPointer();
  useSceneParallax(rootRef);

  return (
    <>
      <div className="fe-scene" data-fe-scene ref={rootRef} aria-hidden="true">
        <ShardDefs />
        <div className="fe-scene__par fe-scene__sky" data-depth="0.15">
          <div className="fe-scene__lamp fe-scene__lamp--gold" />
          <div className="fe-scene__lamp fe-scene__lamp--ice" />
          <div className="fe-scene__lamp fe-scene__lamp--rose" />
        </div>
        <div className="fe-scene__spots">
          {SPOTS.map((sp) => (
            <div key={sp.id} className="fe-scene__par" data-depth={sp.depth}>
              <div
                className={`fe-scene__spot fe-scene__spot--${sp.id} fe-drift`}
                style={{ '--fe-drift-dur': `${sp.dur}s`, '--fe-drift-delay': `${sp.delay}s`, '--fe-drift-y': '3vh', '--fe-drift-r': '0deg' }}
              />
            </div>
          ))}
        </div>
        <div className="fe-scene__texture" />
        <div className="fe-scene__glints">
          {GLINTS.map((g) => <Glint key={g.id} glint={g} />)}
        </div>
        <div className="fe-scene__shards">
          {SHARDS.map((s) => <Shard key={s.id} shard={s} />)}
        </div>
        <SceneF mode={fMode} />
      </div>
      {kind && kind !== 'notfound' ? <div className="fe-scene-leak fe-scene-leak--top" aria-hidden="true" /> : null}
      <div className="fe-scene-leak fe-scene-leak--bottom" aria-hidden="true" />
    </>
  );
}
