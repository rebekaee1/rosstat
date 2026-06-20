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

// Не показываем на этих маршрутах: там целевое действие и так на виду.
const HIDDEN_PATHS = ['/login', '/register', '/account'];

// Два режима одного плавающего окна (ADR-0007 Phase 2):
//   guest    — приглашение зарегистрироваться (снять лимит выгрузок);
//   feedback — для авторизованных: позвать оставить обратную связь.
const REGISTER_VARIANT = {
  storageKey: 'fe_nudge_dismissed',
  pill: 'Скачивайте данные без ограничений',
  title: 'Зачем регистрироваться',
  benefits: [
    { icon: Download, text: 'Безлимитное скачивание данных в Excel и CSV' },
    { icon: CalendarRange, text: 'Выгрузка рядов за любой период истории' },
    { icon: Bell, text: 'Рассылка об обновлениях данных и аналитике' },
  ],
  note: 'Платформа остаётся бесплатной — аккаунт снимает лимит на выгрузку и открывает рассылку.',
  ctaText: 'Зарегистрироваться',
  ctaTo: '/register',
  ev: {
    view: events.REGISTER_NUDGE_VIEW,
    expand: events.REGISTER_NUDGE_EXPAND,
    cta: events.REGISTER_NUDGE_CTA,
  },
};

const FEEDBACK_VARIANT = {
  storageKey: 'fe_feedback_nudge_dismissed',
  pill: 'Помогите сделать сервис лучше',
  title: 'Ваше мнение важно',
  benefits: [
    { icon: MessageSquare, text: 'Подскажите, каких данных или функций не хватает' },
    { icon: AlertCircle, text: 'Сообщите об ошибке или неточности в данных' },
    { icon: Lightbulb, text: 'Предложите улучшение — мы читаем каждое сообщение' },
  ],
  note: 'Форма обратной связи — в личном кабинете. Это займёт минуту.',
  ctaText: 'Оставить отзыв',
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
  const { isAuthed, isLoading } = useAuth();
  const location = useLocation();
  const variant = isAuthed ? FEEDBACK_VARIANT : REGISTER_VARIANT;

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
    <div className="fixed bottom-4 right-4 z-40 max-w-[calc(100vw-2rem)] print:hidden">
      {!expanded ? (
        <button
          type="button"
          onClick={expand}
          className={cn(
            FOCUS_RING,
            'flex items-center gap-2.5 rounded-full pl-4 pr-5 py-3 shadow-xl',
            'bg-champagne text-white font-medium text-sm hover:bg-champagne-muted transition-colors',
          )}
        >
          <Sparkles className="w-4 h-4 shrink-0" />
          {variant.pill}
          <ChevronUp className="w-4 h-4 shrink-0 opacity-80" />
        </button>
      ) : (
        <div className="w-[340px] max-w-[calc(100vw-2rem)] rounded-2xl border border-border-subtle bg-surface shadow-2xl ring-1 ring-black/10 overflow-hidden">
          <div className="flex items-start justify-between gap-3 px-5 pt-4 pb-2">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-champagne" />
              <h3 className="text-sm font-semibold text-text-primary">{variant.title}</h3>
            </div>
            <button
              type="button"
              onClick={() => setExpanded(false)}
              className={cn(FOCUS_RING, 'rounded-md p-1 text-text-tertiary hover:text-text-primary')}
              aria-label="Свернуть"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          <ul className="px-5 py-2 space-y-2.5">
            {variant.benefits.map((b, i) => {
              const Icon = b.icon;
              return (
                <li key={i} className="flex items-start gap-2.5 text-sm text-text-secondary">
                  <Icon className="w-4 h-4 text-champagne shrink-0 mt-0.5" />
                  <span>{b.text}</span>
                </li>
              );
            })}
          </ul>
          <p className="px-5 pb-3 text-xs text-text-tertiary">{variant.note}</p>
          <div className="flex items-center gap-3 px-5 py-3 border-t border-border-subtle bg-obsidian-lighter/30">
            <Link
              to={variant.ctaTo}
              onClick={() => track(variant.ev.cta)}
              className={cn(FOCUS_RING, 'flex-1 text-center rounded-xl bg-champagne text-white text-sm font-semibold py-2 hover:bg-champagne-muted transition-colors')}
            >
              {variant.ctaText}
            </Link>
            <button
              type="button"
              onClick={dismiss}
              className={cn(FOCUS_RING, 'text-xs text-text-tertiary hover:text-text-secondary whitespace-nowrap')}
            >
              Не показывать больше
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
