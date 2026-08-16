import { useState, useEffect, useRef } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import { TrendingUp, Menu, X, ChevronDown } from 'lucide-react';
import gsap from 'gsap';
import { cn } from '../lib/format';
import { FOCUS_RING } from '../lib/uiTokens';
import { track, events } from '../lib/track';
import IndicatorSearch from './IndicatorSearch';
import { useAuth } from '../context/authContext';
import { PRIMARY_NAV, resolveActiveNavId } from '../lib/navItems';

function AuthCluster({ mobile = false, onNavigate }) {
  const { isAuthed, isLoading } = useAuth();
  // Анти-фликер: пока первый /me грузится — нейтральный плейсхолдер фикс. ширины,
  // чтобы кнопки не прыгали и не было layout shift (ADR-0007).
  if (isLoading) {
    return (
      <span
        aria-hidden
        className={cn('inline-block h-8 rounded-full bg-obsidian-lighter/40', mobile ? 'w-full' : 'w-[150px]')}
      />
    );
  }
  if (isAuthed) {
    return (
      <Link
        to="/account"
        onClick={onNavigate}
        className={cn(
          FOCUS_RING,
          'rounded-full px-4 py-1.5 text-sm font-semibold bg-champagne text-white hover:bg-champagne-muted transition-colors',
          mobile && 'w-full text-center',
        )}
      >
        Кабинет
      </Link>
    );
  }
  return (
    <div className={cn('flex items-center gap-2', mobile && 'w-full')}>
      <Link
        to="/login"
        onClick={() => { track(events.HEADER_LOGIN_CLICK); onNavigate?.(); }}
        className={cn(
          FOCUS_RING,
          'rounded-full px-3.5 py-1.5 text-sm font-medium text-text-secondary hover:text-text-primary transition-colors',
          mobile && 'flex-1 text-center border border-border-subtle',
        )}
      >
        Войти
      </Link>
      <Link
        to="/register"
        onClick={() => { track(events.HEADER_REGISTER_CLICK); onNavigate?.(); }}
        className={cn(
          FOCUS_RING,
          'rounded-full px-4 py-1.5 text-sm font-semibold bg-champagne text-white hover:bg-champagne-muted transition-colors',
          mobile ? 'flex-1 text-center' : 'whitespace-nowrap',
        )}
      >
        Регистрация
      </Link>
    </div>
  );
}

// Пункт «Калькуляторы» раскрывается как категория (просьба руководителя
// 2026-07-05: освободить место в верхнем меню).
const CALCULATORS = [
  { to: '/calculator', label: 'Калькулятор инфляции' },
  { to: '/calculator/mortgage', label: 'Ипотечный калькулятор' },
  { to: '/calculator/compound', label: 'Сложные проценты' },
];

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [calcOpen, setCalcOpen] = useState(false);
  const navRef = useRef(null);
  const calcWrapRef = useRef(null);
  const { pathname } = useLocation();
  // Служебный раздел /admin/*: fixed-пилюля наезжала на карточки BI при
  // скролле (обход BI 2.1, этап 4а) — показываем шапку только вверху страницы.
  const isAdmin = pathname.startsWith('/admin');
  const activeNavId = resolveActiveNavId(pathname);

  const closeAll = () => {
    setMobileOpen(false);
    setCalcOpen(false);
  };

  useEffect(() => {
    // Порог маленький: контент подходит под фиксированный навбар уже при
    // ~30px скролла — при 200 текст страницы просвечивал сквозь слабое
    // стекло (наложение, скрин руководителя 2026-07-05).
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  useEffect(() => {
    if (!mobileOpen && !calcOpen) return;
    const onDoc = (e) => {
      if (calcOpen && calcWrapRef.current && !calcWrapRef.current.contains(e.target)) {
        setCalcOpen(false);
      }
    };
    const onKey = (e) => {
      if (e.key === 'Escape') closeAll();
    };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, [mobileOpen, calcOpen]);

  useEffect(() => {
    if (!navRef.current) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const tween = gsap.fromTo(navRef.current,
      { y: -20, opacity: 0 },
      { y: 0, opacity: 1, duration: 0.8, ease: 'power3.out', delay: 0.2 }
    );
    return () => tween.kill();
  }, []);

  const navItemClass = (isActive) => cn(
    FOCUS_RING,
    'rounded-lg text-sm font-medium transition-colors duration-200 px-0.5 py-0.5 -mx-0.5 whitespace-nowrap',
    isActive
      ? 'text-champagne'
      : 'text-text-secondary hover:text-text-primary'
  );

  const itemClass = cn(
    FOCUS_RING,
    'rounded-xl block px-4 py-2.5 text-sm text-left transition-colors hover:bg-obsidian-lighter/80'
  );

  const menuOpen = mobileOpen || calcOpen;

  const renderPrimaryLink = (item, { desktop = false } = {}) => {
    const isActive = activeNavId === item.id;
    return (
      <Link
        key={`${desktop ? 'd' : 'm'}-${item.id}`}
        to={item.to}
        className={cn(
          navItemClass(isActive),
          desktop && item.desktopOnlyXl && 'hidden xl:block',
        )}
        onClick={closeAll}
        aria-current={isActive ? 'page' : undefined}
      >
        {item.label}
      </Link>
    );
  };

  return (
    <>
      {menuOpen && (
        <div
          className="fixed inset-0 z-[80] bg-text-primary/25 backdrop-blur-[2px] md:bg-text-primary/20"
          aria-hidden
          onClick={closeAll}
        />
      )}
      <nav
        ref={navRef}
        className={cn(
          'fixed top-11 md:top-12 inset-x-0 mx-auto z-[100]',
          // Не transition-all: иначе transition тянет backdrop-filter и в
          // части движков blur на время/после смены soft↔surface пропадает.
          'transition-[transform,opacity,background-color,box-shadow,border-color] duration-500 ease-out',
          'rounded-[2rem] px-5 lg:px-6 py-3 flex items-center gap-3',
          'max-w-7xl w-[calc(100%-2rem)]',
          scrolled
            ? 'glass-surface border border-border-subtle shadow-lg shadow-black/5'
            : 'glass-surface-soft border border-black/[0.04]',
          // !opacity: GSAP-tween появления оставляет inline opacity:1 — без
          // important класс не победит его.
          isAdmin && scrolled && !menuOpen && '-translate-y-24 !opacity-0 pointer-events-none'
        )}
      >
      <Link
        to="/"
        className={cn(FOCUS_RING, 'flex items-center gap-2 shrink-0 rounded-xl')}
        onClick={closeAll}
        aria-label="Forecast Economy — на главную"
        title="На главную"
      >
        <TrendingUp className="w-5 h-5 text-champagne" aria-hidden="true" />
        <span className="text-base font-bold tracking-tight text-text-primary">
          Forecast Economy
        </span>
      </Link>

      {/* justify-end: при переполнении лишнее выезжает ВЛЕВО, поверх логотипа
          (задвоенный логотип на скринах руководителя 2026-07-05 и 2026-07-27).
          scrollWidth такое переполнение не показывает — ловится только
          сравнением боксов, см. scripts/e2e/navbar-overlap.mjs. Поэтому набор
          пунктов режется по брейкпоинтам, а «Главная» и «О проекте» на
          десктопе живут в футере и мобильном меню. */}
      <div className="hidden lg:flex items-center gap-1 xl:gap-2 flex-1 justify-end min-w-0">
        {PRIMARY_NAV.map((item) => renderPrimaryLink(item, { desktop: true }))}
        <div className="relative hidden xl:block" ref={calcWrapRef}>
          <button
            type="button"
            onClick={() => { setCalcOpen((o) => !o); }}
            className={cn(
              FOCUS_RING,
              'flex items-center gap-1 text-sm font-medium transition-colors px-2 py-1 rounded-xl',
              calcOpen ? 'text-champagne' : 'text-text-secondary hover:text-text-primary'
            )}
            aria-expanded={calcOpen}
            aria-haspopup="menu"
          >
            Калькуляторы
            <ChevronDown className={cn('w-4 h-4 transition-transform', calcOpen && 'rotate-180')} />
          </button>
          {calcOpen && (
            <div
              className="absolute right-0 top-full z-[110] mt-2 min-w-[240px] rounded-2xl border border-border-subtle bg-surface py-2 shadow-2xl ring-1 ring-black/[0.08]"
              role="menu"
            >
              {CALCULATORS.map((c) => (
                <NavLink
                  key={c.to}
                  to={c.to}
                  end
                  className={({ isActive }) =>
                    cn(itemClass, isActive ? 'text-champagne bg-champagne/5' : 'text-text-primary')
                  }
                  onClick={closeAll}
                  role="menuitem"
                >
                  {c.label}
                </NavLink>
              ))}
            </div>
          )}
        </div>
        {/* В пилюлю не влезает: доступна из футера и мобильного меню. */}
      </div>

      <div className="hidden lg:flex items-center shrink-0 gap-2 xl:gap-3">
        <IndicatorSearch variant="pill" />
        <div className="h-5 w-px bg-border-subtle" aria-hidden />
        <AuthCluster />
      </div>

      <div className="lg:hidden ml-auto flex items-center gap-1">
        <IndicatorSearch className="!px-2 !py-1.5" />
        <button
          type="button"
          onClick={() => { setMobileOpen(!mobileOpen); track(events.NAV_MOBILE_TOGGLE); }}
          className={cn(
            FOCUS_RING,
            'flex min-h-11 min-w-11 items-center justify-center rounded-xl p-2.5 text-text-secondary transition-colors hover:text-text-primary'
          )}
          aria-expanded={mobileOpen}
          aria-label={mobileOpen ? 'Закрыть меню' : 'Открыть меню'}
        >
          {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {mobileOpen && (
        <div className="absolute left-0 right-0 top-full z-[110] mt-2 max-h-[min(80vh,520px)] overflow-y-auto rounded-2xl border border-border-subtle bg-surface p-4 shadow-2xl ring-1 ring-black/[0.08] lg:hidden">
          <div className="flex flex-col gap-1">
            <Link to="/" className={navItemClass(pathname === '/')} onClick={closeAll} aria-current={pathname === '/' ? 'page' : undefined}>
              Главная
            </Link>
            {PRIMARY_NAV.map((item) => renderPrimaryLink(item))}
            <p className="text-[10px] uppercase tracking-wider text-text-tertiary px-2 pt-3 pb-1">
              Калькуляторы
            </p>
            {CALCULATORS.map((c) => (
              <NavLink key={c.to} to={c.to} end className={({ isActive }) => navItemClass(isActive)} onClick={closeAll}>
                {c.label}
              </NavLink>
            ))}
            <NavLink to="/about" className={({ isActive }) => navItemClass(isActive)} onClick={closeAll}>
              О проекте
            </NavLink>
            <div className="mx-2 my-1 h-px bg-border-subtle" />
            <div className="px-2 pt-2">
              <AuthCluster mobile onNavigate={closeAll} />
            </div>
          </div>
        </div>
      )}
    </nav>
    </>
  );
}
