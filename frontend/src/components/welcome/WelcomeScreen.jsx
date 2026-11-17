import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Link } from 'react-router-dom';
import { ArrowLeft, ArrowRight, Bell, Bot, Download, Pause, Play, Send, Star } from 'lucide-react';
import WelcomeArt from './WelcomeArt';
import { useLocale, useT } from '../../i18n';
import { track, events } from '../../lib/track';
import { authLink, prepareAuthReturn } from '../../lib/authReturn';
import { readSceneMode } from '../../lib/sceneBudget';
import { useCabinetConfig } from '../../lib/useCabinet';
import {
  TELEGRAM_BOT_URL, TELEGRAM_CHANNEL_URL, WELCOME_HELLO, clampStep, markWelcomeSeen, welcomeMotionLevel, welcomeScreens,
} from '../../lib/welcome';
import { readBrowserSignals, welcomeAudience } from '../../lib/welcomeAudience';
import { WELCOME_CONCEPT, cleanSeries, formatMonth, formatPercent } from '../../lib/welcomeChart';
import { fetchWorldCompareSeries } from '../../lib/worldApi';
import '../../styles/welcome.css';

/**
 * Приветственный экран для нового посетителя (16.11.2026; вид и движение переделаны 17.11.2026 по словам владельца:
 * «как будто ты открываешь новый iPhone»).
 *
 * Образ: свет в зале гаснет, на тёмном сапфире появляется хрустальная F (экран-приветствие `hello`), человек сам нажимает
 * «Начать», проходит четыре шага и в конце тёмный занавес поднимается, открывая светлый сайт.
 *
 * Шаги (lib/welcome.js): русская версия — поиск, свежие данные, Telegram, аккаунт; английская (иностранная аудитория) —
 * поиск, свежие данные с ведомствами страны посетителя (lib/welcomeAudience.js), сравнение стран, аккаунт.
 *
 * Поведение:
 *  - «Пропустить» всегда справа вверху, Esc делает то же; после любого выхода экран сам больше не открывается;
 *  - экраны листает только человек (кнопки, стрелки ←/→, палец, полоски шагов): ничего не уезжает само;
 *  - палец ведёт сцену за собой 1:1 (сцена быстрее, текст медленнее), у краёв движение туго тянется; отпустил — шаг решает
 *    направление и скорость жеста, а не только пройденный путь;
 *  - уходящий шаг не исчезает кадром: он уезжает, пока новый въезжает (оба слоя на экране ~260 мс);
 *  - окно модальное: страница под ним не прокручивается и не получает фокус (`inert` у `#root`, для старых браузеров круг Tab);
 *  - движение: только `transform` и прозрачность; при `prefers-reduced-motion`, Save-Data и reduced-transparency всё стоит
 *    в итоговом виде (`data-wl-motion="off"`), на слабом устройстве нет фонового плавания света (`calm`);
 *  - рисуется порталом в `body`: предки с `backdrop-filter` не становятся контейнером для `position: fixed`.
 *
 * Когда показывать — `lib/welcome.js` и `WelcomeGate.jsx`.
 */
const EXIT_MS = { done: 1330, skip: 640 };
const OUT_MS = 300;
const SWIPE_MIN = 56;
const SWIPE_VELOCITY = 0.45; // px/мс: быстрый короткий жест тоже листает
const DRAG_SLOP = 10;
/**
 * Показ идёт сам (слова владельца 17.11.2026: «чтобы всё в анимации перетекало… не обязательно от пользователя нужно действие»).
 * Сколько стоит каждый экран, мс: сцена доигрывает за 3,5–3,9 с, остальное — время прочитать две строки. Последний шаг
 * (аккаунт) не уходит сам: там действие, которого мы ждём от человека.
 */
const AUTOPLAY_MS = { hello: 5200, find: 7800, fresh: 7600, telegram: 8000, compare: 7600 };
const DATA_TIMEOUT_MS = 4500;
const STAGE_COLOR = '#0A1227';
const FOCUSABLE = 'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** Заголовок из словаря: `|` делит его на две строки (вторая — тише: акцент остаётся на первой). */
function TitleLines({ text }) {
  const lines = String(text).split('|');
  return lines.map((line, i) => (
    // Ключ по месту строки: строки одного заголовка не переставляются.
    <span key={i} className="fe-wl__line" data-accent={i === 0 ? 'true' : undefined}>
      <span className="fe-wl__line-in" style={{ '--i': i }}>{line}{i < lines.length - 1 ? ' ' : ''}</span>
    </span>
  ));
}

export default function WelcomeScreen({ trigger = 'auto', initialStep = 0, onClose }) {
  const t = useT();
  const { locale } = useLocale();
  const titleId = useId();
  const cabinet = useCabinetConfig();
  const screens = useMemo(() => welcomeScreens(locale), [locale]);
  const total = screens.length;
  const stepCount = total - 1;
  const [index, setIndex] = useState(() => clampStep(initialStep, total));
  const [dir, setDir] = useState(1);
  const [out, setOut] = useState(null); // уходящий экран: { name, tick }
  const [leaving, setLeaving] = useState(null); // 'done' | 'skip'
  const [motion] = useState(() => welcomeMotionLevel(readSceneMode()));
  // Иностранная аудитория: чьи источники и какие страны показать. На русском сайте подписи берутся из словаря.
  const [audience] = useState(() => (locale === 'en' ? welcomeAudience(readBrowserSignals()) : null));
  const rootRef = useRef(null);
  const stageRef = useRef(null);
  const primaryRef = useRef(null);
  const drag = useRef(null);
  const closedRef = useRef(false);
  const indexRef = useRef(index);
  const tickRef = useRef(0);
  const dragFromRef = useRef(0);
  const liveCopyRef = useRef(null);
  // Показ идёт сам, пока человек его не остановил: кнопкой паузы, клавиатурой, шагом назад. При «меньше движения» не идёт вовсе.
  // Открытие сразу на заданном шаге (`welcome_step`, проверка на устройствах) — показ стоит, чтобы шаг можно было рассмотреть.
  const [auto, setAuto] = useState(() => welcomeMotionLevel(readSceneMode()) !== 'off' && !initialStep);
  // Временная остановка: палец или кнопка мыши на сцене, курсор над ссылками, вкладка не на экране.
  const [held, setHeld] = useState(false);
  const remainRef = useRef(0);
  // Настоящее для сцен: ряд страны посетителя и страны рядом (один-два запроса). Сбой не роняет экран: сцены останутся без чисел.
  const [data, setData] = useState({ status: 'loading', series: [], peer: [], source: '' });
  useEffect(() => { indexRef.current = index; }, [index]);

  const name = screens[index];
  const hello = name === WELCOME_HELLO;
  const last = index === total - 1;
  const homeSlug = audience ? audience.homeSlug : 'russia';
  const peerSlug = audience ? audience.peerSlug : 'united-states';

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => setData((cur) => (cur.status === 'loading' ? { ...cur, status: 'empty' } : cur)), DATA_TIMEOUT_MS);
    const load = (slug) => fetchWorldCompareSeries(slug, WELCOME_CONCEPT, { signal: controller.signal }).catch(() => null);
    Promise.all([load(homeSlug), load(peerSlug)]).then(([home, peer]) => {
      if (controller.signal.aborted) return;
      const series = cleanSeries(home);
      setData({
        status: series.length ? 'ready' : 'empty',
        series,
        peer: series.length ? cleanSeries(peer) : [],
        source: typeof home?.meta?.source === 'string' ? home.meta.source : '',
      });
    });
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [homeSlug, peerSlug]);

  const facts = useMemo(() => {
    const home = audience ? audience.home : t('welcome.scene.home');
    const peer = audience ? audience.peer : t('welcome.scene.peer');
    if (data.status !== 'ready') return { series: [], peerSeries: [], home, peer, value: '', peerValue: '', month: '', caption: '', answer: '' };
    const lastPoint = data.series[data.series.length - 1];
    const peerPoint = data.peer.length ? data.peer[data.peer.length - 1] : null;
    const value = formatPercent(lastPoint.value, locale);
    const month = formatMonth(lastPoint.t, locale);
    return {
      series: data.series,
      peerSeries: data.peer,
      home,
      peer,
      value,
      peerValue: peerPoint ? formatPercent(peerPoint.value, locale) : '',
      month,
      caption: data.source ? t('welcome.scene.caption', { month, source: data.source }) : month,
      answer: t('welcome.scene.answer', { value, country: home }),
    };
  }, [audience, data, locale, t]);

  const close = useCallback((outcome, { instant = false } = {}) => {
    if (closedRef.current) return;
    closedRef.current = true;
    markWelcomeSeen(outcome, indexRef.current);
    if (instant || motion === 'off') {
      onClose?.(outcome);
      return;
    }
    const kind = outcome === 'done' ? 'done' : 'skip';
    setLeaving(kind);
    window.setTimeout(() => onClose?.(outcome), EXIT_MS[kind]);
  }, [motion, onClose]);

  const go = useCallback((next, via) => {
    const target = clampStep(next, total);
    const from = indexRef.current;
    if (target === from || closedRef.current) return;
    // С шагов на приветствие не возвращаемся: «Назад» ведёт только между шагами.
    if (target === 0 && from > 0) return;
    tickRef.current += 1;
    const tick = tickRef.current;
    // Уходящий слой стартует оттуда, где его оставил палец (после жеста), а не с нуля: шва между жестом и анимацией нет.
    rootRef.current?.style.setProperty('--wl-from', via === 'swipe' ? `${dragFromRef.current.toFixed(1)}px` : '0px');
    setDir(target > from ? 1 : -1);
    // Приветствие стоит по центру под F, а шаг раскладывается иначе: уходящему приветствию запоминаем его место на экране,
    // чтобы оно растаяло там, где стояло, а не прыгнуло в колонку текста.
    let box = null;
    if (from === 0 && liveCopyRef.current) {
      const r = liveCopyRef.current.getBoundingClientRect();
      box = { position: 'fixed', left: `${r.left}px`, top: `${r.top}px`, width: `${r.width}px`, margin: 0 };
    }
    setOut(motion === 'off' ? null : { name: screens[from], tick, box });
    setIndex(target);
    indexRef.current = target;
    window.setTimeout(() => setOut((cur) => (cur && cur.tick === tick ? null : cur)), OUT_MS);
    track(events.WELCOME_STEP, { step: screens[target], via });
  }, [motion, screens, total]);

  // Показ идёт сам: когда время экрана вышло, открывается следующий. Остановка запоминает, сколько осталось.
  const duration = AUTOPLAY_MS[name] || 0;
  const playing = auto && !held && !leaving && duration > 0;
  useEffect(() => { remainRef.current = AUTOPLAY_MS[screens[index]] || 0; }, [index, screens]);
  useEffect(() => {
    if (!playing) return undefined;
    const startedAt = Date.now();
    const left = remainRef.current > 0 ? remainRef.current : duration;
    const id = window.setTimeout(() => go(indexRef.current + 1, 'auto'), left);
    return () => {
      window.clearTimeout(id);
      remainRef.current = Math.max(400, left - (Date.now() - startedAt));
    };
  }, [playing, duration, go, index]);
  // Вкладка ушла с экрана — показ ждёт: человек не должен вернуться к концу, которого не видел.
  useEffect(() => {
    const onVisibility = () => setHeld(document.visibilityState === 'hidden');
    document.addEventListener('visibilitychange', onVisibility);
    return () => document.removeEventListener('visibilitychange', onVisibility);
  }, []);
  const toggleAuto = () => {
    setAuto((on) => {
      track(events.WELCOME_STEP, { step: screens[indexRef.current], via: on ? 'pause' : 'play' });
      return !on;
    });
    setHeld(false);
  };

  const skip = useCallback((via) => {
    track(events.WELCOME_SKIP, { step: screens[indexRef.current], via });
    close('skip');
  }, [close, screens]);

  const finish = useCallback(() => {
    track(events.WELCOME_DONE);
    close('done');
  }, [close]);

  // Показ считаем один раз; уже на показе запоминаем «видел»: закрытая вкладка или переход по ссылке не вернут экран.
  useEffect(() => {
    track(events.WELCOME_VIEW, { trigger, audience: audience?.key || 'ru' });
    markWelcomeSeen('seen', 0);
  }, [trigger, audience]);

  // Страница под экраном: без прокрутки и без фокуса. Фокус при выходе возвращается туда, где был.
  // Цвет панели браузера (iPhone, Android) на время показа совпадает со сценой: экран не обрезан светлой полосой.
  useEffect(() => {
    const before = document.activeElement;
    const app = document.getElementById('root');
    const html = document.documentElement;
    const prevOverflow = html.style.overflow;
    const meta = document.querySelector('meta[name="theme-color"]');
    const prevTheme = meta?.getAttribute('content');
    html.style.overflow = 'hidden';
    html.setAttribute('data-fe-welcome', 'open');
    app?.setAttribute('inert', '');
    meta?.setAttribute('content', STAGE_COLOR);
    // Фокус на самом окне, а не на кнопке: у человека с мышью не вспыхивает обводка, Tab идёт с «Пропустить».
    rootRef.current?.focus({ preventScroll: true });
    return () => {
      html.style.overflow = prevOverflow;
      html.removeAttribute('data-fe-welcome');
      app?.removeAttribute('inert');
      if (meta && prevTheme != null) meta.setAttribute('content', prevTheme);
      if (before instanceof HTMLElement && document.contains(before)) before.focus({ preventScroll: true });
    };
  }, []);

  // Занавес поднимается: панель браузера светлеет вместе с ним, а не после.
  useEffect(() => {
    if (!leaving) return;
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta?.getAttribute('content') === STAGE_COLOR) meta.setAttribute('content', '#F4F5F7');
    document.documentElement.removeAttribute('data-fe-welcome');
  }, [leaving]);

  // Главная кнопка на разных экранах разная: фокус не должен пропасть со страницы, когда прежняя кнопка исчезла.
  useEffect(() => {
    if (rootRef.current && !rootRef.current.contains(document.activeElement)) primaryRef.current?.focus({ preventScroll: true });
  }, [index]);

  useEffect(() => {
    const onKey = (event) => {
      if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) return;
      if (event.key === 'Escape') {
        event.preventDefault();
        skip('key');
        return;
      }
      // С клавиатуры человек ведёт сам: показ перестаёт листать под ним (и не перебивает экранное чтение по Tab).
      if (event.key === 'Tab' || event.key === 'ArrowRight' || event.key === 'ArrowLeft' || event.key === ' ') setAuto(false);
      if (event.key === 'ArrowRight') { go(indexRef.current + 1, 'key'); return; }
      if (event.key === 'ArrowLeft') { go(indexRef.current - 1, 'key'); return; }
      if (event.key !== 'Tab' || !rootRef.current) return;
      const items = [...rootRef.current.querySelectorAll(FOCUSABLE)].filter((el) => el.getClientRects().length > 0 && !el.closest('[inert]'));
      if (items.length === 0) return;
      const first = items[0];
      const lastItem = items[items.length - 1];
      const active = document.activeElement;
      if (!rootRef.current.contains(active) || active === rootRef.current) {
        event.preventDefault();
        (event.shiftKey ? lastItem : first).focus();
      } else if (event.shiftKey && active === first) {
        event.preventDefault();
        lastItem.focus();
      } else if (!event.shiftKey && active === lastItem) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [go, skip]);

  // Палец ведёт сцену. Пока движение не стало явно горизонтальным (10 pt), ничего не трогаем: вертикальная прокрутка шага жива.
  const setDrag = (px) => {
    const el = stageRef.current;
    if (!el) return;
    if (px === null) {
      el.removeAttribute('data-wl-drag');
      el.style.removeProperty('--wl-drag');
    } else {
      el.setAttribute('data-wl-drag', 'true');
      el.style.setProperty('--wl-drag', `${px.toFixed(1)}px`);
    }
  };
  const onPointerDown = (event) => {
    setHeld(true); // пока палец или кнопка мыши на сцене, показ стоит: можно рассмотреть
    if (event.pointerType !== 'touch' || motion === 'off') return;
    drag.current = { x: event.clientX, y: event.clientY, lastX: event.clientX, lastT: event.timeStamp, v: 0, active: false, dx: 0 };
  };
  const onPointerMove = (event) => {
    const d = drag.current;
    if (!d || event.pointerType !== 'touch') return;
    const dx = event.clientX - d.x;
    const dy = event.clientY - d.y;
    if (!d.active) {
      if (Math.abs(dx) < DRAG_SLOP) return;
      if (Math.abs(dx) < Math.abs(dy) * 1.4) { drag.current = null; return; }
      d.active = true;
    }
    const dt = Math.max(1, event.timeStamp - d.lastT);
    d.v = (event.clientX - d.lastX) / dt;
    d.lastX = event.clientX;
    d.lastT = event.timeStamp;
    // У краёв (первый шаг вправо, последний влево, приветствие вправо) сцена тянется туго: там листать некуда.
    const i = indexRef.current;
    const blocked = (dx > 0 && i <= 1) || (dx < 0 && i >= total - 1);
    d.dx = blocked ? (dx * 0.55 * 120) / (120 + 0.55 * Math.abs(dx)) : dx;
    d.blocked = blocked;
    setDrag(d.dx);
  };
  const onPointerEnd = (event) => {
    setHeld(false);
    const d = drag.current;
    drag.current = null;
    if (!d || !d.active) return;
    setDrag(null);
    if (d.blocked || event.type === 'pointercancel') return;
    const fast = Math.abs(d.v) > SWIPE_VELOCITY && Math.sign(d.v) === Math.sign(d.dx);
    if (Math.abs(d.dx) < SWIPE_MIN && !fast) return;
    dragFromRef.current = d.dx;
    go(indexRef.current + (d.dx < 0 ? 1 : -1), 'swipe');
  };

  const onRegister = () => {
    track(events.WELCOME_CTA, { target: 'register' });
    prepareAuthReturn();
    close('register', { instant: true });
  };
  const onTelegram = (target) => () => {
    track(events.WELCOME_CTA, { target });
    markWelcomeSeen(target, indexRef.current);
  };

  // Обещания шага «Аккаунт» зависят от того, включён ли кабинет на сервере: без него звезды и колокольчика на сайте нет.
  const accountPoints = [
    cabinet.enabled && { key: 'save', Icon: Star },
    cabinet.enabled && { key: 'watch', Icon: Bell },
    { key: 'download', Icon: Download },
  ].filter(Boolean);

  /** Текст экрана. `live` — действующий слой (со ссылками и кнопками); уходящий слой только рисуется. */
  const renderCopy = (screen, live) => (
    <>
      <p className="fe-wl__eyebrow">
        <span className="fe-wl__rule" aria-hidden="true" />
        {t(`welcome.${screen}.eyebrow`)}
        {screen !== WELCOME_HELLO ? (
          <span className="fe-wl__count" aria-hidden="true">{String(screens.indexOf(screen)).padStart(2, '0')}<i> / {String(stepCount).padStart(2, '0')}</i></span>
        ) : null}
        {live && screen !== WELCOME_HELLO ? <span className="sr-only">. {t('welcome.stepOf', { n: index, total: stepCount })}</span> : null}
      </p>
      <h2 id={live ? titleId : undefined} className="fe-wl__title font-display"><TitleLines text={t(`welcome.${screen}.title`)} /></h2>

      {screen === 'account' ? (
        <>
          <ul className="fe-wl__points">
            {accountPoints.map(({ key, Icon }) => (
              <li key={key}>
                <span className="fe-wl__point-icon" aria-hidden="true"><Icon className="h-4 w-4" /></span>
                {t(`welcome.account.${key}`)}
              </li>
            ))}
          </ul>
          <p className="fe-wl__note">{t('welcome.account.note')}</p>
        </>
      ) : (
        <p className="fe-wl__body">{t(`welcome.${screen}.body`)}</p>
      )}

      {screen === 'telegram' && (
        <div
          className="fe-wl__links"
          onMouseEnter={live ? () => setHeld(true) : undefined}
          onMouseLeave={live ? () => setHeld(false) : undefined}
        >
          <a className="fe-wl__link" href={TELEGRAM_BOT_URL} target="_blank" rel="noopener noreferrer" onClick={live ? onTelegram('bot') : undefined}>
            <Bot className="h-[18px] w-[18px]" aria-hidden="true" />
            <span>{t('welcome.telegram.bot')}</span>
            <span className="sr-only">, {t('welcome.telegram.newTab')}</span>
          </a>
          <a className="fe-wl__link" href={TELEGRAM_CHANNEL_URL} target="_blank" rel="noopener noreferrer" onClick={live ? onTelegram('channel') : undefined}>
            <Send className="h-[18px] w-[18px]" aria-hidden="true" />
            <span>{t('welcome.telegram.channel')}</span>
            <span className="sr-only">, {t('welcome.telegram.newTab')}</span>
          </a>
        </div>
      )}

      {screen === WELCOME_HELLO && (
        <div className="fe-wl__start">
          <button
            ref={live ? primaryRef : undefined}
            type="button"
            className="fe-wl__btn fe-wl__btn--light"
            onClick={live ? () => go(1, 'start') : undefined}
            data-testid={live ? 'welcome-start' : undefined}
          >
            <span>{t('welcome.hello.start')}</span>
            <span className="fe-wl__btn-chip" aria-hidden="true"><ArrowRight className="fe-wl__btn-arrow h-4 w-4" /></span>
          </button>
        </div>
      )}
    </>
  );

  if (typeof document === 'undefined') return null;

  return createPortal(
    <div
      ref={rootRef}
      className="fe-wl"
      tabIndex={-1}
      role="dialog"
      aria-modal="true"
      aria-label={t('welcome.aria')}
      aria-describedby={titleId}
      data-wl-motion={motion}
      data-wl-step={name}
      data-wl-kind={hello ? 'hello' : 'step'}
      data-wl-leaving={leaving || undefined}
      data-wl-auto={auto && duration > 0 ? 'on' : 'off'}
      data-wl-paused={playing ? undefined : 'true'}
      data-wl-data={data.status}
      data-testid="welcome-screen"
      style={{ '--wl-dir': dir, '--wl-i': Math.max(0, index - 1), '--wl-dur': `${duration || 1}ms` }}
    >
      <div className="fe-wl__scene" aria-hidden="true">
        <span className="fe-wl__glow fe-wl__glow--a" />
        <span className="fe-wl__glow fe-wl__glow--b" />
        <span className="fe-wl__glow fe-wl__glow--warm" />
        {/* Мазки света и тонкие трещины льда: сцена не пустая и не плоская; резкие искры рядом с F — там, где хрусталь ловит свет. */}
        <span className="fe-wl__beam fe-wl__beam--a" />
        <span className="fe-wl__beam fe-wl__beam--b" />
        <svg className="fe-wl__ice" viewBox="0 0 1200 800" preserveAspectRatio="xMidYMid slice" focusable="false">
          <g fill="none" stroke="#DCE6FF" strokeLinecap="round">
            <path d="M-40 212 L60 190 L148 214 L236 176 L330 188 L402 150" strokeOpacity="0.09" strokeWidth="1" />
            <path d="M402 150 L470 96 L512 20 L498 -40" strokeOpacity="0.06" strokeWidth="0.8" />
            <path d="M402 150 L486 196 L590 204 L664 258 L770 262" strokeOpacity="0.07" strokeWidth="0.9" />
            <path d="M770 262 L842 210 L946 196 L1010 132 L1108 110 L1240 122" strokeOpacity="0.09" strokeWidth="1" />
            <path d="M770 262 L808 350 L790 448 L846 540 L836 640" strokeOpacity="0.06" strokeWidth="0.8" />
            <path d="M836 640 L930 676 L1036 660 L1120 716 L1240 708" strokeOpacity="0.07" strokeWidth="0.9" />
            <path d="M-40 560 L70 548 L150 596 L262 590 L330 648 L318 742 L360 840" strokeOpacity="0.07" strokeWidth="0.9" />
            <path d="M262 590 L310 500 L296 410 L352 330" strokeOpacity="0.05" strokeWidth="0.7" />
          </g>
        </svg>
        <span className="fe-wl__f">
          <span className="fe-wl__f-ground" />
          <span className="fe-wl__f-orbit"><i /></span>
          <span className="fe-wl__f-img" />
          <span className="fe-wl__f-sweep"><i /></span>
          <span className="fe-wl__spark fe-wl__spark--a" />
          <span className="fe-wl__spark fe-wl__spark--b" />
          <span className="fe-wl__spark fe-wl__spark--c" />
        </span>
      </div>

      <header className="fe-wl__top">
        {/* Маленький знак — значок сайта (стеклянная F на тёмно-синем), слово владельца 17.11.2026. */}
        <span className="fe-wl__brand fe-wl__mark">
          <img src="/favicon-512.png" width="30" height="30" alt="" decoding="async" />
          <span className="fe-wl__mark-word">forecast<span>economy</span></span>
        </span>
        <span className="fe-wl__top-actions">
          {/* Показ идёт сам, поэтому остановить его можно всегда (и снова пустить). На последнем шаге и при «меньше движения» кнопки нет. */}
          {motion !== 'off' && duration > 0 ? (
            <button
              type="button"
              className="fe-wl__pause"
              onClick={toggleAuto}
              aria-label={auto ? t('welcome.pause') : t('welcome.play')}
              aria-pressed={!auto}
              data-testid="welcome-pause"
            >
              {auto ? <Pause className="h-4 w-4" aria-hidden="true" /> : <Play className="h-4 w-4" aria-hidden="true" />}
            </button>
          ) : null}
          <button type="button" className="fe-wl__skip" onClick={() => skip('button')} aria-label={t('welcome.skipAria')}>
            {t('welcome.skip')}
          </button>
        </span>
      </header>

      <div
        ref={stageRef}
        className="fe-wl__stage"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerEnd}
        onPointerCancel={onPointerEnd}
        onPointerLeave={(event) => { if (event.pointerType === 'mouse') setHeld(false); }}
      >
        <div className="fe-wl__art">
          {out && out.name !== WELCOME_HELLO ? (
            <div className="fe-wl__art-in" data-out="true" key={`out-${out.tick}`}>
              <WelcomeArt step={out.name} t={t} audience={audience} facts={facts} />
            </div>
          ) : null}
          {!hello && (
            <div className="fe-wl__art-in" key={name}>
              <WelcomeArt step={name} t={t} audience={audience} facts={facts} />
            </div>
          )}
        </div>

        {/* Обёртка постоянная (экранное чтение объявляет новый шаг), содержимое пересоздаётся: появление играет заново. */}
        <div className="fe-wl__copy-wrap">
          {out ? (
            <div className="fe-wl__copy" data-out="true" data-screen={out.name} key={`out-${out.tick}`} aria-hidden="true" inert style={out.box || undefined}>
              {renderCopy(out.name, false)}
            </div>
          ) : null}
          <div ref={liveCopyRef} className="fe-wl__copy" data-screen={name} key={name} aria-live="polite">
            {renderCopy(name, true)}
          </div>
        </div>
      </div>

      {/* На приветствии низа нет: одна кнопка «Начать» под текстом. С первым шагом низ въезжает снизу. */}
      {!hello && (
      <footer className="fe-wl__nav">
        <ol className="fe-wl__steps" aria-label={t('welcome.progressAria')}>
          {screens.slice(1).map((step, i) => (
            <li key={step}>
              <button
                type="button"
                className="fe-wl__dot"
                data-state={i + 1 === index ? 'current' : i + 1 < index ? 'done' : 'ahead'}
                aria-label={t('welcome.stepOf', { n: i + 1, total: stepCount })}
                aria-current={i + 1 === index ? 'step' : undefined}
                onClick={() => go(i + 1, 'dot')}
              >
                <span aria-hidden="true" />
              </button>
            </li>
          ))}
        </ol>

        <div className="fe-wl__actions">
          <button
            type="button"
            className="fe-wl__back"
            onClick={() => { setAuto(false); go(index - 1, 'back'); }}
            aria-label={t('welcome.back')}
            disabled={index <= 1}
            data-hidden={index <= 1 ? 'true' : undefined}
          >
            <ArrowLeft className="h-5 w-5" aria-hidden="true" />
          </button>

          {last ? (
            <>
              <button type="button" className="fe-wl__btn fe-wl__btn--quiet" onClick={finish} data-testid="welcome-done">
                {t('welcome.done')}
              </button>
              <div className="fe-wl__cta">
                <Link
                  ref={primaryRef}
                  to={authLink('/register', '/')}
                  className="fe-wl__btn fe-wl__btn--gold"
                  onClick={onRegister}
                  data-testid="welcome-register"
                >
                  <span>{t('welcome.account.cta')}</span>
                  <span className="fe-wl__btn-chip" aria-hidden="true"><ArrowRight className="fe-wl__btn-arrow h-4 w-4" /></span>
                </Link>
                <span className="fe-wl__cta-hint">{t('welcome.account.ctaHint')}</span>
              </div>
            </>
          ) : (
            <button
              ref={primaryRef}
              type="button"
              className="fe-wl__btn fe-wl__btn--light"
              onClick={() => go(index + 1, 'next')}
              data-testid="welcome-next"
            >
              <span>{t('welcome.next')}</span>
              <span className="fe-wl__btn-chip" aria-hidden="true"><ArrowRight className="fe-wl__btn-arrow h-4 w-4" /></span>
              {/* Когда сцена доиграла, по кнопке один раз проходит блик: взгляд возвращается к следующему действию. */}
              <i className="fe-wl__btn-glint" key={name} aria-hidden="true" />
            </button>
          )}
        </div>
      </footer>
      )}
    </div>,
    document.body,
  );
}
