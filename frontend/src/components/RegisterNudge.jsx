import { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  Sparkles, X, ChevronUp, Download, CalendarRange, Bell,
  MessageSquare, AlertCircle, Lightbulb,
} from 'lucide-react';
import { useAuth } from '../context/authContext';
import { track, events } from '../lib/track';
import { cn } from '../lib/format';
import { FOCUS_RING } from '../lib/uiTokens';
import { useT } from '../i18n';
import '../styles/shell.css';
import { authLink, prepareAuthReturn } from '../lib/authReturn';
import Button from './Button';

// Не показываем на этих маршрутах: там целевое действие и так на виду.
// Главная — отдельный кейс: плавающая кнопка наезжает на блок «Инструменты».
const HIDDEN_PATHS = ['/', '/login', '/register', '/account'];

// Два режима одного плавающего окна:
//   guest    — приглашение зарегистрироваться (открыть скачивание);
//   feedback — для авторизованных: позвать оставить обратную связь.
const REGISTER_VARIANT = {
  storageKey: 'fe_nudge_dismissed',
  pillKey: 'nudge.register.pill',
  lineKey: 'shell.nudge.register.line',
  titleKey: 'nudge.register.title',
  benefitKeys: [
    { icon: Download, textKey: 'nudge.register.benefit.download' },
    { icon: CalendarRange, textKey: 'nudge.register.benefit.history' },
    { icon: Bell, textKey: 'nudge.register.benefit.mail' },
  ],
  noteKey: 'nudge.register.note',
  ctaKey: 'nudge.register.cta',
  ctaTo: '/register',
  ev: {
    view: events.REGISTER_NUDGE_VIEW,
    expand: events.REGISTER_NUDGE_EXPAND,
    cta: events.REGISTER_NUDGE_CTA,
  },
};

const FEEDBACK_VARIANT = {
  storageKey: 'fe_feedback_nudge_dismissed',
  pillKey: 'nudge.feedback.pill',
  lineKey: 'shell.nudge.feedback.line',
  titleKey: 'nudge.feedback.title',
  benefitKeys: [
    { icon: MessageSquare, textKey: 'nudge.feedback.benefit.missing' },
    { icon: AlertCircle, textKey: 'nudge.feedback.benefit.bug' },
    { icon: Lightbulb, textKey: 'nudge.feedback.benefit.idea' },
  ],
  noteKey: 'nudge.feedback.note',
  ctaKey: 'nudge.feedback.cta',
  ctaTo: '/account#feedback',
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
  const lastTrackedRef = useRef(null);

  // Смена режима (вход/выход) — у каждого свой ключ скрытия. Корректируем
  // состояние во время рендера (паттерн React «adjust state on prop change»),
  // не в эффекте, иначе setState-in-effect.
  if (variantKey !== variant.storageKey) {
    setVariantKey(variant.storageKey);
    setDismissed(readDismissed(variant.storageKey));
    setExpanded(false);
  }

  const onHiddenPath = HIDDEN_PATHS.includes(location.pathname);
  const visible = !isLoading && !dismissed && !onHiddenPath;

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

  return (
    <>
    <aside
      className="fe-reveal [--fe-duration:0.2s] [--fe-rise:8px] fe-nudge-card sm:hidden print:hidden"
      aria-label={t(variant.titleKey)}
    >
      <div className="flex items-start gap-3">
        <span className="fe-nudge-card__icon" aria-hidden="true">
          <Sparkles size={18} />
        </span>
        <p className="min-w-0 flex-1 self-center text-[15px] font-medium leading-snug text-text-primary">
          {t(variant.lineKey)}
        </p>
        <button
          type="button"
          onClick={dismiss}
          aria-label={t('common.close')}
          className={cn(FOCUS_RING, 'fe-press -mr-2 -mt-2 flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-text-tertiary hover:text-text-primary')}
        >
          <X className="w-4 h-4" aria-hidden="true" />
        </button>
      </div>
      <Button
        as={Link}
        to={isAuthed ? variant.ctaTo : authLink('/register')}
        onClick={() => { prepareAuthReturn(); track(variant.ev.cta); }}
        className="mt-1 w-full"
      >
        {t(variant.ctaKey)}
      </Button>
    </aside>
    <div className="hidden sm:block fixed bottom-4 right-4 z-40 max-w-[calc(100vw-2rem)] print:hidden">
      {!expanded ? (
        <div className="fe-reveal [--fe-duration:0.2s] [--fe-rise:8px]">
          <Button
            onClick={expand}
            aria-label={pill}
            className="gap-2.5 rounded-full! py-3 pl-4 pr-5 shadow-xl"
          >
            <Sparkles className="w-4 h-4 shrink-0" aria-hidden="true" />
            <span className="hidden sm:inline">{pill}</span>
            <ChevronUp className="w-4 h-4 shrink-0 opacity-80" aria-hidden="true" />
          </Button>
        </div>
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
              className={cn(FOCUS_RING, 'fe-press flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-text-tertiary hover:text-text-primary pointer-coarse:h-11 pointer-coarse:w-11')}
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
              className={cn(FOCUS_RING, 'fe-press rounded-md px-2 text-xs text-text-tertiary hover:text-text-secondary whitespace-nowrap min-h-8 pointer-coarse:min-h-11')}
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
