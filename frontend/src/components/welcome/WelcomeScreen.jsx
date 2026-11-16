import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Link } from 'react-router-dom';
import { ArrowLeft, ArrowRight } from 'lucide-react';
import WelcomeChart from './WelcomeChart';
import { useLocale, useT } from '../../i18n';
import { track, events } from '../../lib/track';
import { authLink, prepareAuthReturn } from '../../lib/authReturn';
import { readSceneMode } from '../../lib/sceneBudget';
import { useCabinetConfig } from '../../lib/useCabinet';
import { fetchWorldCompareSeries } from '../../lib/worldApi';
import {
  TELEGRAM_BOT_URL, TELEGRAM_CHANNEL_URL, clampStep, markWelcomeSeen, searchHref, welcomeMotionLevel, welcomeScreens,
} from '../../lib/welcome';
import { readBrowserSignals, welcomeAudience } from '../../lib/welcomeAudience';
import { WELCOME_CONCEPT, cleanSeries, formatMonth, formatPercent } from '../../lib/welcomeChart';
import '../../styles/welcome.css';

/**
 * Приветственный экран для нового посетителя. Третья версия (17.11.2026).
 *
 * Слова владельца о второй версии: «всё какое-то мультяшное и слишком виден AI slop… надо разобраться во вкусе и философии
 * дизайна». Философия — `.artifacts/FE-REFERENSY/FILOSOFIYA.md`. Что из неё здесь:
 *  - экран не рассказывает о продукте картинками, а ведёт себя как продукт: вопрос → фраза-ответ → линия-доказательство;
 *  - числа настоящие (ряд сайта, `GET /world/compare/series`), нарисованных «интерфейсов» и заготовок нет;
 *  - слова стоят неподвижно, под рукой идёт только число и месяц;
 *  - «сейчас» — самая резкая кромка, прошлое мягче; золото значит одно — «ваше» (точка на шаге про аккаунт);
 *  - следующий шаг настоящий: поле «Спросите своё» открывает поиск сайта с этим запросом.
 *
 * Одна линия живёт весь показ; меняется только текст рядом и то, что на линии выделено. Шаги (lib/welcome.js):
 * русская версия — вопрос и ответ, свежие данные, Telegram, аккаунт; английская — то же, но вместо Telegram сравнение
 * страны посетителя с соседней (lib/welcomeAudience.js).
 *
 * Поведение: «Пропустить» всегда справа вверху, Esc делает то же; шаги листает только человек; окно модальное
 * (`inert` у `#root`, круг Tab); движение — проявление текста и один проход линии, при `prefers-reduced-motion` всё стоит сразу.
 * Нет данных (сеть, сбой) — экран остаётся честным: общие фразы без чисел и без линии.
 */
const EXIT_MS = 260;
const OUT_MS = 180;
const DATA_TIMEOUT_MS = 4500;
const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])';

const goTo = (href) => { window.location.assign(href); };

export default function WelcomeScreen({ trigger = 'auto', initialStep = 0, onClose, navigateTo = goTo }) {
  const t = useT();
  const { locale } = useLocale();
  const titleId = useId();
  const cabinet = useCabinetConfig();
  const screens = useMemo(() => welcomeScreens(locale), [locale]);
  const total = screens.length;
  const [index, setIndex] = useState(() => clampStep(initialStep, total));
  const [out, setOut] = useState(null); // уходящий текст: { name, tick }
  const [leaving, setLeaving] = useState(false);
  const [motion] = useState(() => welcomeMotionLevel(readSceneMode()));
  // Иностранная аудитория: страна посетителя и её ведомства. На русском сайте ряд — Россия.
  const [audience] = useState(() => (locale === 'en' ? welcomeAudience(readBrowserSignals()) : null));
  const [data, setData] = useState({ status: 'loading', series: [], peer: [], source: '' });
  const [query, setQuery] = useState('');
  const rootRef = useRef(null);
  const primaryRef = useRef(null);
  const closedRef = useRef(false);
  const indexRef = useRef(index);
  const tickRef = useRef(0);
  useEffect(() => { indexRef.current = index; }, [index]);

  const name = screens[index];
  const last = index === total - 1;
  const homeSlug = audience ? audience.homeSlug : 'russia';
  const peerSlug = audience ? audience.peerSlug : null;

  // Настоящий ряд: один запрос (для английской версии ещё один — страна для сравнения). Сбой не роняет экран.
  useEffect(() => {
    const controller = new AbortController();
    let done = false;
    const timer = window.setTimeout(() => {
      if (!done) setData((cur) => (cur.status === 'loading' ? { ...cur, status: 'empty' } : cur));
    }, DATA_TIMEOUT_MS);
    const load = (slug) => fetchWorldCompareSeries(slug, WELCOME_CONCEPT, { signal: controller.signal }).catch(() => null);
    Promise.all([load(homeSlug), peerSlug ? load(peerSlug) : Promise.resolve(null)]).then(([home, peer]) => {
      if (controller.signal.aborted) return;
      done = true;
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

  const close = useCallback((outcome, { instant = false } = {}) => {
    if (closedRef.current) return;
    closedRef.current = true;
    markWelcomeSeen(outcome, indexRef.current);
    if (instant || motion === 'off') {
      onClose?.(outcome);
      return;
    }
    setLeaving(true);
    window.setTimeout(() => onClose?.(outcome), EXIT_MS);
  }, [motion, onClose]);

  const go = useCallback((next, via) => {
    const target = clampStep(next, total);
    const from = indexRef.current;
    if (target === from || closedRef.current) return;
    tickRef.current += 1;
    const tick = tickRef.current;
    setOut(motion === 'off' ? null : { name: screens[from], tick });
    setIndex(target);
    indexRef.current = target;
    window.setTimeout(() => setOut((cur) => (cur && cur.tick === tick ? null : cur)), OUT_MS);
    track(events.WELCOME_STEP, { step: screens[target], via });
  }, [motion, screens, total]);

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
  useEffect(() => {
    const before = document.activeElement;
    const app = document.getElementById('root');
    const html = document.documentElement;
    const prevOverflow = html.style.overflow;
    html.style.overflow = 'hidden';
    html.setAttribute('data-fe-welcome', 'open');
    app?.setAttribute('inert', '');
    // Фокус на самом окне, а не на кнопке: у человека с мышью не вспыхивает обводка, Tab идёт с «Пропустить».
    rootRef.current?.focus({ preventScroll: true });
    return () => {
      html.style.overflow = prevOverflow;
      html.removeAttribute('data-fe-welcome');
      app?.removeAttribute('inert');
      if (before instanceof HTMLElement && document.contains(before)) before.focus({ preventScroll: true });
    };
  }, []);

  // Главная кнопка на последнем шаге другая: фокус не должен пропасть со страницы, когда прежняя исчезла.
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
      // В поле ввода стрелки двигают курсор по тексту, а не листают шаги.
      const typing = document.activeElement instanceof HTMLInputElement;
      if (event.key === 'ArrowRight' && !typing) { go(indexRef.current + 1, 'key'); return; }
      if (event.key === 'ArrowLeft' && !typing) { go(indexRef.current - 1, 'key'); return; }
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

  const onRegister = () => {
    track(events.WELCOME_CTA, { target: 'register' });
    prepareAuthReturn();
    close('register', { instant: true });
  };
  const onTelegram = (target) => () => {
    track(events.WELCOME_CTA, { target });
    markWelcomeSeen(target, indexRef.current);
  };
  // Следующий шаг настоящий: вопрос уходит в поиск сайта (`/?q=…` открывает поиск с этим запросом).
  const ask = (text) => {
    const q = String(text || '').trim();
    if (q.length < 2 || closedRef.current) return;
    closedRef.current = true;
    track(events.WELCOME_CTA, { target: 'search' });
    markWelcomeSeen('search', indexRef.current);
    navigateTo(searchHref(q, typeof window !== 'undefined' ? window.location.search : ''));
  };

  const ready = data.status === 'ready';
  const lastPoint = ready ? data.series[data.series.length - 1] : null;
  const peerPoint = ready && data.peer.length ? data.peer[data.peer.length - 1] : null;
  const month = lastPoint ? formatMonth(lastPoint.t, locale) : '';
  const names = audience ? { home: audience.home, peer: audience.peer } : null;

  /** Фраза шага. С данными — ответ с настоящим числом; без данных — общая фраза без чисел. */
  const phraseFor = (screen) => {
    if (screen === 'find') {
      return ready ? t('welcome.find.phrase', { value: formatPercent(lastPoint.value, locale), country: audience?.home || '' }) : t('welcome.find.phraseEmpty');
    }
    if (screen === 'fresh') return ready ? t('welcome.fresh.phrase', { month }) : t('welcome.fresh.phraseEmpty');
    if (screen === 'compare') {
      return ready && peerPoint ? t('welcome.compare.phrase', {
        home: audience.home, homeValue: formatPercent(lastPoint.value, locale), peer: audience.peer, peerValue: formatPercent(peerPoint.value, locale),
      }) : t('welcome.compare.phraseEmpty');
    }
    return t(`welcome.${screen}.phrase`);
  };

  // Обещания шага «Аккаунт» зависят от того, включён ли кабинет на сервере: без него звезды и колокольчика на сайте нет.
  const accountPoints = [cabinet.enabled && 'save', cabinet.enabled && 'watch', 'download'].filter(Boolean);
  const sources = audience ? audience.sources.join(', ') : t('welcome.fresh.sourceList');

  /** Текст шага. `live` — действующий слой (с полем и ссылками); уходящий слой только рисуется. */
  const renderCopy = (screen, live) => (
    <>
      <p className="fe-wl3__label">
        {screen === 'find' && !ready ? t('welcome.find.labelEmpty') : t(`welcome.${screen}.label`)}
        {live ? <span className="sr-only">. {t('welcome.stepOf', { n: index + 1, total })}</span> : null}
      </p>
      {screen === 'find' && ready ? <p className="fe-wl3__question">{t('welcome.find.question')}</p> : null}
      <h2 id={live ? titleId : undefined} className="fe-wl3__phrase">{phraseFor(screen)}</h2>

      {screen === 'find' && (
        <>
          {ready ? <p className="fe-wl3__caption">{data.source ? t('welcome.find.caption', { month, source: data.source }) : month}</p> : null}
          <p className="fe-wl3__body">{ready ? t('welcome.find.body') : t('welcome.find.bodyEmpty')}</p>
          {live ? (
            <form className="fe-wl3__ask" onSubmit={(event) => { event.preventDefault(); ask(query); }}>
              <div className="fe-wl3__field">
                <input
                  type="text"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder={t('welcome.find.field')}
                  aria-label={t('welcome.find.fieldAria')}
                  enterKeyHint="search"
                  autoComplete="off"
                  autoCorrect="off"
                  autoCapitalize="off"
                  spellCheck={false}
                  maxLength={80}
                  data-testid="welcome-field"
                />
                <button type="submit" aria-label={t('welcome.find.go')} disabled={query.trim().length < 2}>
                  <ArrowRight className="h-[18px] w-[18px]" aria-hidden="true" />
                </button>
              </div>
              <p className="fe-wl3__tries">
                {['try1', 'try2', 'try3'].map((key) => (
                  <button key={key} type="button" onClick={() => ask(t(`welcome.find.${key}`))}>{t(`welcome.find.${key}`)}</button>
                ))}
              </p>
            </form>
          ) : null}
        </>
      )}
      {screen === 'fresh' && (
        <>
          <p className="fe-wl3__body">{ready ? t('welcome.fresh.body') : t('welcome.fresh.bodyEmpty')}</p>
          <p className="fe-wl3__caption">{t('welcome.fresh.sources', { list: sources })}</p>
        </>
      )}
      {screen === 'compare' && <p className="fe-wl3__body">{t('welcome.compare.body')}</p>}
      {screen === 'telegram' && (
        <>
          <p className="fe-wl3__body">{t('welcome.telegram.body')}</p>
          <p className="fe-wl3__links">
            <a className="fe-wl3__link" href={TELEGRAM_BOT_URL} target="_blank" rel="noopener noreferrer" onClick={live ? onTelegram('bot') : undefined}>
              {t('welcome.telegram.bot')}
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
              <span className="sr-only">, {t('welcome.telegram.newTab')}</span>
            </a>
            <a className="fe-wl3__link" href={TELEGRAM_CHANNEL_URL} target="_blank" rel="noopener noreferrer" onClick={live ? onTelegram('channel') : undefined}>
              {t('welcome.telegram.channel')}
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
              <span className="sr-only">, {t('welcome.telegram.newTab')}</span>
            </a>
          </p>
        </>
      )}
      {screen === 'account' && (
        <>
          <ul className="fe-wl3__points">
            {accountPoints.map((key) => <li key={key}>{t(`welcome.account.${key}`)}</li>)}
          </ul>
          <p className="fe-wl3__caption">{t('welcome.account.note')}</p>
        </>
      )}
    </>
  );

  if (typeof document === 'undefined') return null;
  const settled = data.status !== 'loading';

  return createPortal(
    <div
      ref={rootRef}
      className="fe-wl3"
      tabIndex={-1}
      role="dialog"
      aria-modal="true"
      aria-label={t('welcome.aria')}
      aria-describedby={titleId}
      data-wl-motion={motion}
      data-wl-step={name}
      data-wl-data={data.status}
      data-wl-leaving={leaving ? 'true' : undefined}
      data-testid="welcome-screen"
    >
      <div className="fe-wl3__ice" aria-hidden="true">
        <svg viewBox="0 0 1200 800" preserveAspectRatio="xMidYMid slice" focusable="false">
          <g fill="none" stroke="#28406E" strokeLinecap="round">
            <path d="M-40 212 L60 190 L148 214 L236 176 L330 188 L402 150" strokeOpacity="0.04" strokeWidth="1" />
            <path d="M402 150 L470 96 L512 20 L498 -40" strokeOpacity="0.02" strokeWidth="0.8" />
            <path d="M402 150 L486 196 L590 204 L664 258 L770 262" strokeOpacity="0.03" strokeWidth="0.9" />
            <path d="M770 262 L842 210 L946 196 L1010 132 L1108 110 L1240 122" strokeOpacity="0.04" strokeWidth="1" />
            <path d="M770 262 L808 350 L790 448 L846 540 L836 640" strokeOpacity="0.02" strokeWidth="0.8" />
            <path d="M836 640 L930 676 L1036 660 L1120 716 L1240 708" strokeOpacity="0.03" strokeWidth="0.9" />
            <path d="M836 640 L772 716 L760 840" strokeOpacity="0.02" strokeWidth="0.7" />
            <path d="M-40 560 L70 548 L150 596 L262 590 L330 648 L318 742 L360 840" strokeOpacity="0.03" strokeWidth="0.9" />
            <path d="M262 590 L310 500 L296 410 L352 330" strokeOpacity="0.02" strokeWidth="0.7" />
            <path d="M1010 132 L1040 40 L1016 -40" strokeOpacity="0.02" strokeWidth="0.7" />
          </g>
        </svg>
      </div>

      <header className="fe-wl3__top">
        {/* Маленький знак сайта — значок сайта (favicon): стеклянная F на тёмно-синем квадрате; его выбрал владелец 17.11.2026. */}
        <span className="fe-wl3__brand">
          <img src="/favicon-512.png" alt="" width="28" height="28" decoding="async" />
          Forecast Economy
        </span>
        <button type="button" className="fe-wl3__skip" onClick={() => skip('button')} aria-label={t('welcome.skipAria')}>
          {t('welcome.skip')}
        </button>
      </header>

      <div className="fe-wl3__stage">
        {/* Обёртка постоянная (экранное чтение объявляет новый шаг), содержимое пересоздаётся: текст проявляется заново. */}
        <div className="fe-wl3__copywrap">
          {out ? (
            <div className="fe-wl3__copy" data-out="true" key={`out-${out.tick}`} aria-hidden="true" inert>
              {renderCopy(out.name, false)}
            </div>
          ) : null}
          {settled ? (
            <div className="fe-wl3__copy" key={name} aria-live="polite">
              {renderCopy(name, true)}
            </div>
          ) : null}
        </div>

        {ready ? (
          <WelcomeChart series={data.series} peer={data.peer} mode={name} locale={locale} t={t} names={names} />
        ) : <div className="fe-wl3-chart" data-empty="true" aria-hidden="true" />}
      </div>

      <footer className="fe-wl3__nav">
        <div className="fe-wl3__actions">
          <ol className="fe-wl3__steps" aria-label={t('welcome.progressAria')}>
            {screens.map((step, i) => (
              <li key={step}>
                <button
                  type="button"
                  className="fe-wl3__tick"
                  data-state={i === index ? 'current' : i < index ? 'done' : 'ahead'}
                  aria-label={t('welcome.stepOf', { n: i + 1, total })}
                  aria-current={i === index ? 'step' : undefined}
                  onClick={() => go(i, 'dot')}
                >
                  <span aria-hidden="true" />
                </button>
              </li>
            ))}
          </ol>

          <button
            type="button"
            className="fe-wl3__back"
            onClick={() => go(index - 1, 'back')}
            aria-label={t('welcome.back')}
            disabled={index === 0}
            data-hidden={index === 0 ? 'true' : undefined}
          >
            <ArrowLeft className="h-[18px] w-[18px]" aria-hidden="true" />
            <span>{t('welcome.back')}</span>
          </button>

          {last ? (
            <>
              <button type="button" className="fe-wl3__quiet" onClick={finish} data-testid="welcome-done">
                {t('welcome.done')}
              </button>
              <span className="fe-wl3__cta">
                <Link ref={primaryRef} to={authLink('/register', '/')} className="fe-wl3__go" onClick={onRegister} data-testid="welcome-register">
                  {t('welcome.account.cta')}
                </Link>
                <small>{t('welcome.account.ctaHint')}</small>
              </span>
            </>
          ) : (
            <button ref={primaryRef} type="button" className="fe-wl3__go" onClick={() => go(index + 1, 'next')} data-testid="welcome-next">
              {t('welcome.next')}
              <ArrowRight className="h-[18px] w-[18px]" aria-hidden="true" />
            </button>
          )}
        </div>
      </footer>
    </div>,
    document.body,
  );
}
