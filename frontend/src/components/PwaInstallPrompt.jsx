// Ненавязчивое приглашение установить сайт как приложение (PWA).
// Когда показывать — lib/pwaPolicy.js (после полезного действия или второго захода,
// «Не сейчас» откладывает на 3/7/14/30 дней и дальше раз в 30). Уже установившим —
// никогда. Только телефоны и планшеты, не в iframe, не в виджетах и админке, не
// поверх баннера согласия, модальных окон и других плавающих подсказок.
import { useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { track, events } from '../lib/track';
import {
  acknowledgeIos, currentPlatform, dismissInstall, inIframe, promptNativeInstall,
  setCardVisible, usePwaStore,
} from '../lib/pwa';
import { shouldShowInstallCard, triggerFor } from '../lib/pwaPolicy';
import PwaInstallCard from './PwaInstallCard';

// Всё, что нельзя накрывать: баннер согласия, модальные окна, нудж регистрации/обратной связи.
const BLOCKERS = '[data-analytics-overlay="cookie-consent"], [role="dialog"][aria-modal="true"], .fe-nudge-root';
const POLL_MS = 1500;

function overlayPresent() {
  if (typeof document === 'undefined') return false;
  return document.querySelector(BLOCKERS) !== null;
}

export default function PwaInstallPrompt() {
  const store = usePwaStore();
  const { pathname } = useLocation();
  const [tick, setTick] = useState(0);
  const [busy, setBusy] = useState(false);
  const platform = currentPlatform(); // дёшево; не замораживаем: UA в тестах подменяется на лету
  const [loadedAt] = useState(() => Date.now());
  const shownRef = useRef(false);
  const stateKey = `${store.state.installed}|${store.state.nextAt}|${store.state.usefulAt}|${store.state.visits}`;

  // Время и внешние оверлеи меняются без событий React: перепроверяем по таймеру,
  // пока окно возможно показать (иначе цикл ничего не стоит).
  const { state } = store;
  const trigger = triggerFor({ state, now: Date.now(), sessionUsefulAt: store.sessionUsefulAt });
  const candidate = Boolean(
    store.config?.install_prompt_enabled && !state.installed && !store.standalone && trigger
    && (platform === 'android' || platform === 'ios-safari'),
  );
  useEffect(() => {
    if (!candidate) return undefined;
    const id = setInterval(() => setTick((n) => n + 1), POLL_MS);
    return () => clearInterval(id);
  }, [candidate, stateKey]);

  const now = Date.now();
  const show = candidate && shouldShowInstallCard({
    state,
    now,
    platform,
    hasNativePrompt: Boolean(store.deferredPrompt),
    flagEnabled: Boolean(store.config?.install_prompt_enabled),
    standalone: store.standalone,
    inIframe: inIframe(),
    pathname,
    blocked: overlayPresent(),
    trigger,
    pageLoadedAt: loadedAt,
  });
  // tick намеренно читается: перерисовка по таймеру пересчитывает show.
  void tick;

  useEffect(() => {
    setCardVisible(show);
    return () => setCardVisible(false);
  }, [show]);

  const viewPlatform = platform === 'android' ? 'android' : 'ios';
  useEffect(() => {
    if (!show || shownRef.current) return;
    shownRef.current = true; // один показ — одно событие, пока карточка не закрыта
    track(events.PWA_INSTALL_PROMPT_VIEW, { platform: viewPlatform });
    if (viewPlatform === 'ios') track(events.PWA_IOS_HINT_VIEW, { platform: 'ios' });
  }, [show, viewPlatform]);
  useEffect(() => { if (!show) shownRef.current = false; }, [show]);

  if (!show) return null;

  const onInstall = async () => {
    track(events.PWA_INSTALL_PROMPT_ACCEPT, { platform: 'android' });
    setBusy(true);
    try { await promptNativeInstall({ fromCard: true }); } finally { setBusy(false); }
  };

  return (
    <PwaInstallCard
      platform={viewPlatform}
      busy={busy}
      onInstall={onInstall}
      onLater={() => dismissInstall(viewPlatform)}
      onAck={() => acknowledgeIos()}
    />
  );
}
