import { useCallback, useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Link } from 'react-router-dom';
import { ArrowLeft, ArrowRight, Bell, Bot, Download, Send, Star } from 'lucide-react';
import Brand from '../Brand';
import Button from '../Button';
import WelcomeArt from './WelcomeArt';
import { useT } from '../../i18n';
import { track, events } from '../../lib/track';
import { authLink, prepareAuthReturn } from '../../lib/authReturn';
import { readSceneMode } from '../../lib/sceneBudget';
import { useCabinetConfig } from '../../lib/useCabinet';
import {
  TELEGRAM_BOT_URL, TELEGRAM_CHANNEL_URL, WELCOME_STEPS, clampStep, markWelcomeSeen, welcomeMotionLevel,
} from '../../lib/welcome';
import '../../styles/welcome.css';

/**
 * Приветственный экран для нового посетителя (16.11.2026). Четыре шага, на каждом одна мысль, одна сцена и одно главное действие:
 *   find      как пользоваться: поиск → график, история, источник;
 *   fresh     данные сверяются с источниками каждый день;
 *   telegram  бот отвечает цифрой и присылает новые данные, канал с разборами;
 *   account   зачем аккаунт: сохранять, следить, скачивать (последний шаг: единственная золотая кнопка «Создать аккаунт»).
 *
 * Поведение:
 *  - «Пропустить» всегда на месте (справа вверху), Esc делает то же; после любого выхода экран сам больше не открывается;
 *  - шаги листает только человек (кнопки, стрелки ←/→, смахивание, полоски шагов): ничего не уезжает само, читать можно сколько угодно;
 *  - окно модальное: страница под ним не прокручивается и не получает фокус (`inert` у `#root`, для старых браузеров круг Tab);
 *  - движение: только `transform` и `opacity`; при `prefers-reduced-motion`, Save-Data и reduced-transparency всё стоит в итоговом виде
 *    (`data-wl-motion="off"`), на слабом устройстве остаются короткие проходы без фонового плавания (`calm`);
 *  - рисуется порталом в `body`: предки с `backdrop-filter` не становятся контейнером для `position: fixed`.
 *
 * Когда показывать — `lib/welcome.js` и `WelcomeGate.jsx`.
 */
const EXIT_MS = 240;
const SWIPE_MIN = 56;
const FOCUSABLE = 'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])';

export default function WelcomeScreen({ trigger = 'auto', initialStep = 0, onClose }) {
  const t = useT();
  const titleId = useId();
  const cabinet = useCabinetConfig();
  const [index, setIndex] = useState(() => clampStep(initialStep));
  const [dir, setDir] = useState(1);
  const [leaving, setLeaving] = useState(false);
  const [motion] = useState(() => welcomeMotionLevel(readSceneMode()));
  const rootRef = useRef(null);
  const primaryRef = useRef(null);
  const touch = useRef(null);
  const closedRef = useRef(false);
  const indexRef = useRef(index);
  useEffect(() => { indexRef.current = index; }, [index]);

  const total = WELCOME_STEPS.length;
  const step = WELCOME_STEPS[index];
  const last = index === total - 1;

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
    if (target === from) return;
    setDir(target > from ? 1 : -1);
    setIndex(target);
    track(events.WELCOME_STEP, { step: WELCOME_STEPS[target], via });
  }, [total]);

  const skip = useCallback((via) => {
    track(events.WELCOME_SKIP, { step: WELCOME_STEPS[indexRef.current], via });
    close('skip');
  }, [close]);

  const finish = useCallback(() => {
    track(events.WELCOME_DONE);
    close('done');
  }, [close]);

  // Показ считаем один раз; уже на показе запоминаем «видел»: закрытая вкладка или переход по ссылке не вернут экран.
  useEffect(() => {
    track(events.WELCOME_VIEW, { trigger });
    markWelcomeSeen('seen', 0);
  }, [trigger]);

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

  // Кнопка «Дальше» на последнем шаге сменяется другой: фокус не должен пропасть со страницы.
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
      if (event.key === 'ArrowRight') { go(indexRef.current + 1, 'key'); return; }
      if (event.key === 'ArrowLeft') { go(indexRef.current - 1, 'key'); return; }
      if (event.key !== 'Tab' || !rootRef.current) return;
      const items = [...rootRef.current.querySelectorAll(FOCUSABLE)].filter((el) => el.getClientRects().length > 0);
      if (items.length === 0) return;
      const first = items[0];
      const lastItem = items[items.length - 1];
      const active = document.activeElement;
      if (!rootRef.current.contains(active)) {
        event.preventDefault();
        first.focus();
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

  // Смахивание пальцем: только касание, только явно горизонтальное движение (вертикальная прокрутка шага не мешает).
  const onPointerDown = (event) => {
    if (event.pointerType !== 'touch') return;
    touch.current = { x: event.clientX, y: event.clientY };
  };
  const onPointerUp = (event) => {
    const start = touch.current;
    touch.current = null;
    if (!start || event.pointerType !== 'touch') return;
    const dx = event.clientX - start.x;
    const dy = event.clientY - start.y;
    if (Math.abs(dx) < SWIPE_MIN || Math.abs(dx) < Math.abs(dy) * 1.6) return;
    go(indexRef.current + (dx < 0 ? 1 : -1), 'swipe');
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
      data-wl-step={step}
      data-wl-leaving={leaving ? 'true' : undefined}
      data-testid="welcome-screen"
      style={{ '--wl-dir': dir }}
    >
      <div className="fe-wl__scene" aria-hidden="true">
        <span className="fe-wl__glow fe-wl__glow--ice" />
        <span className="fe-wl__glow fe-wl__glow--cool" />
        <span className="fe-wl__glow fe-wl__glow--warm" />
        <span className="fe-wl__f" />
      </div>

      <header className="fe-wl__top">
        <Brand compact className="fe-wl__brand" />
        <button type="button" className="fe-wl__skip fe-press" onClick={() => skip('button')} aria-label={t('welcome.skipAria')}>
          {t('welcome.skip')}
        </button>
      </header>

      <div className="fe-wl__stage" onPointerDown={onPointerDown} onPointerUp={onPointerUp} onPointerCancel={() => { touch.current = null; }}>
        <div className="fe-wl__art">
          <div className="fe-wl__art-in" key={step}>
            <WelcomeArt step={step} t={t} />
          </div>
        </div>

        {/* Обёртка постоянная (экранное чтение объявляет новый шаг), содержимое пересоздаётся: появление играет заново. */}
        <div className="fe-wl__copy-wrap" aria-live="polite">
        <div className="fe-wl__copy" key={step}>
          <p className="fe-wl__eyebrow">
            <span className="fe-wl__rule" aria-hidden="true" />
            {t(`welcome.${step}.eyebrow`)}
            <span className="sr-only">. {t('welcome.stepOf', { n: index + 1, total })}</span>
          </p>
          <h2 id={titleId} className="fe-wl__title font-display">{t(`welcome.${step}.title`)}</h2>

          {step === 'account' ? (
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
            <p className="fe-wl__body">{t(`welcome.${step}.body`)}</p>
          )}

          {step === 'telegram' && (
            <div className="fe-wl__links">
              <a
                className="fe-wl__link fe-press"
                href={TELEGRAM_BOT_URL}
                target="_blank"
                rel="noopener noreferrer"
                onClick={onTelegram('bot')}
              >
                <Bot className="h-[18px] w-[18px]" aria-hidden="true" />
                <span>{t('welcome.telegram.bot')}</span>
                <span className="sr-only">, {t('welcome.telegram.newTab')}</span>
              </a>
              <a
                className="fe-wl__link fe-press"
                href={TELEGRAM_CHANNEL_URL}
                target="_blank"
                rel="noopener noreferrer"
                onClick={onTelegram('channel')}
              >
                <Send className="h-[18px] w-[18px]" aria-hidden="true" />
                <span>{t('welcome.telegram.channel')}</span>
                <span className="sr-only">, {t('welcome.telegram.newTab')}</span>
              </a>
            </div>
          )}
        </div>
        </div>
      </div>

      <footer className="fe-wl__nav">
        <ol className="fe-wl__steps" aria-label={t('welcome.progressAria')}>
          {WELCOME_STEPS.map((name, i) => (
            <li key={name}>
              <button
                type="button"
                className="fe-wl__dot"
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

        <div className="fe-wl__actions">
          <button
            type="button"
            className="fe-wl__back fe-press"
            onClick={() => go(index - 1, 'back')}
            aria-label={t('welcome.back')}
            disabled={index === 0}
            data-hidden={index === 0 ? 'true' : undefined}
          >
            <ArrowLeft className="h-5 w-5" aria-hidden="true" />
            <span className="fe-wl__back-text">{t('welcome.back')}</span>
          </button>

          {last ? (
            <>
              <Button variant="ghost" className="fe-wl__later" onClick={finish} data-testid="welcome-done">
                {t('welcome.done')}
              </Button>
              <div className="fe-wl__cta">
                <Button
                  ref={primaryRef}
                  as={Link}
                  to={authLink('/register', '/')}
                  className="fe-cta-gold fe-wl__primary"
                  onClick={onRegister}
                  data-testid="welcome-register"
                >
                  {t('welcome.account.cta')}
                </Button>
                <span className="fe-wl__cta-hint">{t('welcome.account.ctaHint')}</span>
              </div>
            </>
          ) : (
            <Button ref={primaryRef} className="fe-wl__primary" onClick={() => go(index + 1, 'next')} data-testid="welcome-next">
              {t('welcome.next')}
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Button>
          )}
        </div>
      </footer>
    </div>,
    document.body,
  );
}
