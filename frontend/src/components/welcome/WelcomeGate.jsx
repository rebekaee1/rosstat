import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/authContext';
import { isAutomationClient } from '../../lib/behavior';
import { inIframe, usePwaStore } from '../../lib/pwa';
import { cn } from '../../lib/format';
import { useT } from '../../i18n';
import {
  WELCOME_OPEN_DELAY_MS, WELCOME_OPEN_EVENT, WELCOME_QUERY, canRemember, isCrawlerUa, isManualRequest, manualStartStep,
  readWelcomeSeen, shouldAutoOpenWelcome,
} from '../../lib/welcome';

// Экран лежит отдельным чанком: тот, кому он не положен (почти все), его код и стили не скачивает.
const WelcomeScreen = lazy(() => import('./WelcomeScreen'));

function useWelcomeEnabled() {
  return usePwaStore().config?.welcome_enabled === true;
}

/** Человек уже чем-то занят: открыт поиск или окно, страница прокручена, курсор в поле. Тогда экран не перебивает. */
function visitorIsBusy() {
  if (typeof document === 'undefined') return true;
  if (document.querySelector('[role="dialog"][aria-modal="true"]')) return true;
  if ((window.scrollY || 0) > 160) return true;
  const active = document.activeElement;
  return Boolean(active && /^(INPUT|TEXTAREA|SELECT)$/.test(active.tagName));
}

/**
 * Ворота приветственного экрана: решают, открывать ли его (правила — `lib/welcome.js`), и подгружают сам экран.
 * Пока флаг сервера `welcome_enabled` выключен, ничего не рисуют и ничего не скачивают.
 */
export default function WelcomeGate() {
  const enabled = useWelcomeEnabled();
  const store = usePwaStore();
  const { isAuthed, isLoading } = useAuth();
  const { pathname, search, hash } = useLocation();
  const navigate = useNavigate();
  const [opened, setOpened] = useState(null); // null | 'auto' | 'manual'
  const [openedPath, setOpenedPath] = useState(null); // страница, на которой экран открылся
  const pathRef = useRef(pathname);                    // текущая страница для обработчиков событий
  useEffect(() => { pathRef.current = pathname; }, [pathname]);
  const [closedAt, setClosedAt] = useState(0); // перечитать «видел» после закрытия

  const manualByUrl = enabled && isManualRequest(search);
  const trigger = opened || (manualByUrl ? 'manual' : null);

  // Пункт подвала «Знакомство с сайтом».
  useEffect(() => {
    if (!enabled) return undefined;
    const onOpen = () => { setOpened('manual'); setOpenedPath(pathRef.current); };
    window.addEventListener(WELCOME_OPEN_EVENT, onOpen);
    return () => window.removeEventListener(WELCOME_OPEN_EVENT, onOpen);
  }, [enabled]);

  // Экран открылся сам на одной странице, а человек ушёл на другую («назад», ссылка под показом) —
  // экран уступает: поверх страницы данных он не остаётся.
  const leftPage = Boolean(opened) && openedPath !== null && openedPath !== pathname;
  useEffect(() => {
    if (!leftPage) return undefined;
    const id = window.setTimeout(() => {
      setOpened(null);
      setOpenedPath(null);
      setClosedAt(Date.now());
    }, 0);
    return () => window.clearTimeout(id);
  }, [leftPage]);

  // Экрана нет — страница не должна оставаться в его тёмном фоне, даже если он закрылся нештатно.
  useEffect(() => {
    if (!trigger && typeof document !== 'undefined') document.documentElement.removeAttribute('data-fe-welcome');
  }, [trigger]);

  // При выключенном флаге правила показа не вычисляются вовсе (и хранилище браузера не трогается).
  const auto = enabled && !trigger && shouldAutoOpenWelcome({
    enabled,
    pathname,
    authLoading: isLoading,
    isAuthed,
    seen: Boolean(readWelcomeSeen()) || closedAt > 0,
    visits: store.state?.visits,
    canStore: canRemember(),
    automation: isAutomationClient(),
    crawler: typeof navigator !== 'undefined' && isCrawlerUa(navigator.userAgent),
    standalone: store.standalone,
    embedded: inIframe(),
  });

  useEffect(() => {
    if (!auto) return undefined;
    const id = window.setTimeout(() => {
      if (!visitorIsBusy()) { setOpened('auto'); setOpenedPath(pathRef.current); }
    }, WELCOME_OPEN_DELAY_MS);
    return () => window.clearTimeout(id);
  }, [auto]);

  const onClose = useCallback(() => {
    setOpened(null);
    setOpenedPath(null);
    setClosedAt(Date.now());
    if (!isManualRequest(search)) return;
    const params = new URLSearchParams(search);
    params.delete(WELCOME_QUERY);
    params.delete('welcome_step');
    const rest = params.toString();
    navigate({ pathname, search: rest ? `?${rest}` : '', hash }, { replace: true });
  }, [hash, navigate, pathname, search]);

  if (!trigger || leftPage) return null;
  return (
    <Suspense fallback={null}>
      <WelcomeScreen trigger={trigger} initialStep={manualByUrl ? manualStartStep(search) : 0} onClose={onClose} />
    </Suspense>
  );
}

/** Пункт подвала: вернуться к знакомству. Виден только при включённом флаге. */
export function WelcomeEntry({ className }) {
  const t = useT();
  const enabled = useWelcomeEnabled();
  if (!enabled) return null;
  return (
    <li>
      <button
        type="button"
        className={cn(className, 'text-left')}
        onClick={() => window.dispatchEvent(new Event(WELCOME_OPEN_EVENT))}
        data-testid="welcome-entry"
      >
        {t('welcome.footer.entry')}
      </button>
    </li>
  );
}
