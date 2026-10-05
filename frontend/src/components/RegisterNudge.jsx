import { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  Sparkles, X, Download, CalendarRange, Bell,
  MessageSquare, AlertCircle, Lightbulb,
} from 'lucide-react';
import { useAuth } from '../context/authContext';
import { track, events } from '../lib/track';
import { cn } from '../lib/format';
import { FOCUS_RING } from '../lib/uiTokens';
import { useT } from '../i18n';
import { authLink, prepareAuthReturn } from '../lib/authReturn';
import {
  hasDownloadAttempt, markDownloadAttempt, readActions, shouldOfferNudge, writeActions,
} from '../lib/registerNudge';
import Button from './Button';
import '../styles/indicator-russia.css';
import '../styles/shell.css';
import '../styles/z1-polish.css';

// Не показываем на этих маршрутах: там целевое действие и так на виду.
// Главная — отдельный кейс: плавающая кнопка наезжает на блок «Инструменты».
const HIDDEN_PATHS = ['/', '/login', '/register', '/account', '/widgets'];

// Два режима одного плавающего окна:
//   guest    — приглашение зарегистрироваться (открыть скачивание);
//   feedback — для авторизованных: позвать оставить обратную связь.
// Волна 6: приглашение не висит на каждой странице. Гостю оно показывается после второго действия
// (или первой попытки скачать) и только там, где есть что скачать (см. lib/registerNudge.js);
// свёрнутый вид — маленькая кнопка-значок, а не широкая золотая плашка.
const REGISTER_VARIANT = {
  storageKey: 'fe_nudge_dismissed',
  pillKey: 'nudge.register.pill',
  Icon: Download,
  titleKey: 'nudge.register.title',
  benefitKeys: [
    { icon: Download, textKey: 'nudge.register.benefit.download' },
    { icon: CalendarRange, textKey: 'nudge.register.benefit.history' },
    { icon: Bell, textKey: 'nudge.register.benefit.mail' },
  ],
  noteKey: 'nudge.register.note',
  // Плашка на телефоне: заголовок про выгоду и одна короткая фраза, без «рассылки» как преимущества.
  mobileTitleKey: 'shell3.nudge.register.title',
  mobileSubKey: 'shell3.nudge.register.sub',
  ctaKey: 'nudge.register.cta',
  ctaTo: '/register',
  requireDownloadable: true,
  ev: {
    view: events.REGISTER_NUDGE_VIEW,
    expand: events.REGISTER_NUDGE_EXPAND,
    cta: events.REGISTER_NUDGE_CTA,
  },
};

const FEEDBACK_VARIANT = {
  storageKey: 'fe_feedback_nudge_dismissed',
  pillKey: 'nudge.feedback.pill',
  Icon: MessageSquare,
  titleKey: 'nudge.feedback.title',
  benefitKeys: [
    { icon: MessageSquare, textKey: 'nudge.feedback.benefit.missing' },
    { icon: AlertCircle, textKey: 'nudge.feedback.benefit.bug' },
    { icon: Lightbulb, textKey: 'nudge.feedback.benefit.idea' },
  ],
  noteKey: 'nudge.feedback.note',
  mobileTitleKey: 'nudge.feedback.pill',
  mobileSubKey: 'shell3.nudge.feedback.sub',
  ctaKey: 'nudge.feedback.cta',
  ctaTo: '/account#feedback',
  requireDownloadable: false,
  ev: {
    view: events.FEEDBACK_NUDGE_VIEW,
    expand: events.FEEDBACK_NUDGE_EXPAND,
    cta: events.FEEDBACK_NUDGE_CTA,
  },
};

function readDismissed(key) {
  try { return localStorage.getItem(key) === '1'; } catch { return false; }
}

export default function RegisterNudge() {
  const t = useT();
  const { isAuthed, isLoading } = useAuth();
  const location = useLocation();
  const variant = isAuthed ? FEEDBACK_VARIANT : REGISTER_VARIANT;
  const pill = t(variant.pillKey);

  const [dismissed, setDismissed] = useState(() => readDismissed(variant.storageKey));
  const [expanded, setExpanded] = useState(false);
  const [variantKey, setVariantKey] = useState(variant.storageKey);
  const [actions, setActions] = useState(() => readActions());
  const [downloadAttempted, setDownloadAttempted] = useState(() => hasDownloadAttempt());
  const [nearFooter, setNearFooter] = useState(false);
  const [prevPath, setPrevPath] = useState(location.pathname);
  const lastTrackedRef = useRef(null);

  // Смена режима (вход/выход) — у каждого свой ключ скрытия. Корректируем
  // состояние во время рендера (паттерн React «adjust state on prop change»),
  // не в эффекте, иначе setState-in-effect.
  if (variantKey !== variant.storageKey) {
    setVariantKey(variant.storageKey);
    setDismissed(readDismissed(variant.storageKey));
    setExpanded(false);
  }

  // Действие = переход на другую страницу внутри сайта за сессию (первый вход не считается).
  // Счёт ведём в состоянии (тот же паттерн «подправить состояние при смене пропса»), в хранилище только пишем.
  if (prevPath !== location.pathname) {
    setPrevPath(location.pathname);
    setActions((n) => n + 1);
  }
  useEffect(() => { writeActions(actions); }, [actions]);

  // Первая попытка скачать (сервер ответил «после регистрации») показывает приглашение сразу.
  useEffect(() => {
    const onLimit = () => { markDownloadAttempt(); setDownloadAttempted(true); };
    window.addEventListener('fe:download-limit', onLimit);
    return () => window.removeEventListener('fe:download-limit', onLimit);
  }, []);

  const onHiddenPath = HIDDEN_PATHS.includes(location.pathname);
  const offered = shouldOfferNudge({
    actions,
    downloadAttempted,
    pathname: location.pathname,
    requireDownloadable: variant.requireDownloadable,
  });
  const visible = !isLoading && !dismissed && !onHiddenPath && offered;

  // Значок прячется, когда на экране подвал: не закрывает ссылки и реквизиты.
  useEffect(() => {
    if (!visible || typeof IntersectionObserver === 'undefined') return undefined;
    const footer = document.querySelector('footer');
    if (!footer) return undefined;
    const observer = new IntersectionObserver(
      ([entry]) => setNearFooter(Boolean(entry?.isIntersecting)),
      { rootMargin: '0px 0px 64px 0px' },
    );
    observer.observe(footer);
    return () => observer.disconnect();
  }, [visible, location.pathname]);

  // Цель «показан» — один раз на каждый режим (ключ режима — в ref внутри эффекта).
  useEffect(() => {
    if (visible && lastTrackedRef.current !== variant.ev.view) {
      lastTrackedRef.current = variant.ev.view;
      track(variant.ev.view);
    }
  }, [visible, variant]);

  if (!visible) return null;

  const expand = () => {
    setExpanded(true);
    track(variant.ev.expand);
  };

  const dismiss = () => {
    try { localStorage.setItem(variant.storageKey, '1'); } catch { /* noop */ }
    setDismissed(true);
  };

  const FabIcon = variant.Icon;

  return (
    <>
    <aside className="fe-reveal [--fe-duration:0.2s] [--fe-rise:8px] fe-nudge-m fe-nudge-root sm:hidden print:hidden" aria-label={pill}>
      <span className="fe-nudge-m__icon" aria-hidden="true"><Sparkles className="h-5 w-5" /></span>
      <div className="fe-nudge-m__text">
        <p className="fe-nudge-m__title">{t(variant.mobileTitleKey)}</p>
        <p className="fe-nudge-m__sub">{t(variant.mobileSubKey)}</p>
      </div>
      <button type="button" onClick={dismiss} aria-label={t('common.close')} className={cn(FOCUS_RING, 'fe-press fe-nudge-m__close')}><X className="w-4 h-4" aria-hidden="true" /></button>
      <Button
        as={Link}
        to={isAuthed ? variant.ctaTo : authLink('/register')}
        onClick={() => { prepareAuthReturn(); track(variant.ev.cta); }}
        className="fe-nudge-m__cta"
      >
        {t(variant.ctaKey)}
      </Button>
    </aside>
    <div
      className="fe-nudge-root fe-nudge-desk hidden sm:block print:hidden"
      data-near-footer={nearFooter && !expanded ? 'true' : undefined}
    >
      {!expanded ? (
        <button
          type="button"
          onClick={expand}
          aria-label={pill}
          title={pill}
          className={cn(FOCUS_RING, 'fe-press fe-nudge-fab')}
          data-testid="nudge-fab"
        >
          <FabIcon className="h-5 w-5" aria-hidden="true" />
        </button>
      ) : (
        <div className="fe-reveal [--fe-duration:0.2s] [--fe-rise:8px] w-[340px] max-w-[calc(100vw-2rem)] rounded-2xl border border-border-subtle bg-surface shadow-2xl ring-1 ring-black/10 overflow-hidden">
          <div className="flex items-start justify-between gap-3 px-5 pt-4 pb-2">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-champagne" />
              <h3 className="text-sm font-semibold text-text-primary">{t(variant.titleKey)}</h3>
            </div>
            <button
              type="button"
              onClick={() => setExpanded(false)}
              className={cn(FOCUS_RING, 'fe-press flex h-11 w-11 shrink-0 items-center justify-center rounded-md text-text-tertiary hover:text-text-primary')}
              aria-label={t('nudge.register.collapse')}
            >
              <X className="w-4 h-4" aria-hidden="true" />
            </button>
          </div>
          <ul className="px-5 py-2 space-y-2.5">
            {variant.benefitKeys.map((b, i) => {
              const Icon = b.icon;
              return (
                <li key={i} className="flex items-start gap-2.5 text-sm text-text-secondary">
                  <Icon className="w-4 h-4 text-champagne shrink-0 mt-0.5" />
                  <span>{t(b.textKey)}</span>
                </li>
              );
            })}
          </ul>
          <p className="px-5 pb-3 text-xs text-text-tertiary">{t(variant.noteKey)}</p>
          <div className="flex items-center gap-3 px-5 py-3 border-t border-border-subtle bg-obsidian-lighter/30">
            <Button
              as={Link}
              to={isAuthed ? variant.ctaTo : authLink('/register')}
              onClick={() => { prepareAuthReturn(); track(variant.ev.cta); }}
              className="flex-1"
            >
              {t(variant.ctaKey)}
            </Button>
            <button
              type="button"
              onClick={dismiss}
              className={cn(FOCUS_RING, 'fe-press rounded-md px-2 text-xs text-text-tertiary hover:text-text-secondary whitespace-nowrap min-h-11')}
            >
              {t('nudge.register.dismiss')}
            </button>
          </div>
        </div>
      )}
    </div>
    </>
  );
}
