import { useState, useEffect, useRef } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import {
  Menu, X, ChevronDown, BarChart3, Building2, CalendarDays, Clock, Coins, Flag, GitCompare, Globe2, Home, Info, Landmark,
  Map as MapIcon, Percent, PiggyBank,
} from 'lucide-react';
import { cn } from '../lib/format';
import { FOCUS_RING } from '../lib/uiTokens';
import { track, events } from '../lib/track';
import IndicatorSearch from './IndicatorSearch';
import LocaleSwitcher from './LocaleSwitcher';
import Brand from './Brand';
import { useAuth } from '../context/authContext';
import { PRIMARY_NAV, mobileNavGroups, primaryNav, resolveActiveNavId } from '../lib/navItems';
import { useLocale, useT } from '../i18n';
import '../styles/ui-detail-nav-calendar.css';
import '../styles/shell.css';
import '../styles/z3-polish.css';

function AuthCluster({ mobile = false, onNavigate }) {
  const { isAuthed, isLoading } = useAuth();
  const t = useT();
  // Анти-фликер: пока первый /me грузится — нейтральный плейсхолдер фикс. ширины,
  // чтобы кнопки не прыгали и не было layout shift (ADR-0007).
  if (isLoading) {
    return (
      <span
        aria-hidden
        className={cn('inline-block h-8 rounded-full bg-obsidian-lighter/40', mobile ? 'w-full' : 'w-[96px]')}
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
          'fe-button-primary rounded-full px-4 py-1.5 text-sm font-semibold transition-colors',
          mobile && 'w-full justify-center text-center',
        )}
      >
        {t('common.account')}
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
          mobile && 'flex-1 justify-center text-center border border-border-subtle',
        )}
      >
        {t('common.login')}
      </Link>
      <Link
        to="/register"
        onClick={() => { track(events.HEADER_REGISTER_CLICK); onNavigate?.(); }}
        className={cn(
          FOCUS_RING,
          'fe-button-primary rounded-full px-4 py-1.5 text-sm font-semibold transition-colors',
          mobile ? 'flex-1 justify-center text-center' : 'whitespace-nowrap',
        )}
      >
        {t('common.register')}
      </Link>
    </div>
  );
}

const MOBILE_ICONS = {
  home: Home,
  globe: Globe2,
  chart: BarChart3,
  compare: GitCompare,
  flag: Flag,
  landmark: Landmark,
  clock: Clock,
  map: MapIcon,
  calendar: CalendarDays,
  coins: Coins,
};

// Три калькулятора — три разных значка: в меню телефона их различают с первого взгляда.
const CALCULATOR_ITEMS = [
  { to: '/calculator', labelKey: 'nav.calc.inflation', icon: Percent },
  { to: '/calculator/mortgage', labelKey: 'nav.calc.mortgage', icon: Building2 },
  { to: '/calculator/compound', labelKey: 'nav.calc.compound', icon: PiggyBank },
];

export default function Navbar() {
  const t = useT();
  const { locale } = useLocale();
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [calcOpen, setCalcOpen] = useState(false);
  const navRef = useRef(null);
  const calcWrapRef = useRef(null);
  const calcBtnRef = useRef(null);
  const mobileBtnRef = useRef(null);
  const mobileMenuRef = useRef(null);
  const { pathname } = useLocation();
  // Служебный раздел /admin/*: fixed-пилюля наезжала на карточки BI при
  // скролле (обход BI 2.1, этап 4а) — показываем шапку только вверху страницы.
  const isAdmin = pathname.startsWith('/admin');
  const activeNavId = resolveActiveNavId(pathname);
  const primaryItems = primaryNav(locale);
  const mobileGroups = mobileNavGroups(locale);
  const mobileActiveId = resolveActiveNavId(pathname, mobileGroups.flatMap((group) => group.items));

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
    // Тап/клик вне открытой панели закрывает её (pointerdown + mousedown: второй — для окружений без Pointer Events).
    const onDoc = (e) => {
      const inCalc = calcWrapRef.current?.contains(e.target);
      const inMobile = mobileMenuRef.current?.contains(e.target) || mobileBtnRef.current?.contains(e.target);
      if (calcOpen && !inCalc) setCalcOpen(false);
      if (mobileOpen && !inMobile) setMobileOpen(false);
    };
    const onKey = (e) => {
      if (e.key !== 'Escape') return;
      // Фокус — на кнопку, которая открыла панель: клавиатурный пользователь не теряет место.
      const target = calcOpen ? calcBtnRef.current : mobileBtnRef.current;
      closeAll();
      target?.focus();
    };
    document.addEventListener('pointerdown', onDoc);
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('pointerdown', onDoc);
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, [mobileOpen, calcOpen]);

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
    const full = t(item.labelKey);
    const short = item.shortLabelKey ? t(item.shortLabelKey) : null;
    return (
      <Link
        key={`${desktop ? 'd' : 'm'}-${item.id}`}
        to={item.to}
        className={navItemClass(isActive)}
        onClick={closeAll}
        aria-current={isActive ? 'page' : undefined}
      >
        {desktop && short ? (
          <>
            <span className="xl:hidden">{short}</span>
            <span className="hidden xl:inline">{full}</span>
          </>
        ) : full}
      </Link>
    );
  };

  return (
    <>
      {menuOpen && (
        <div
          className="fe-reveal fixed inset-0 z-[80] bg-text-primary/25 backdrop-blur-[2px] [--fe-duration:0.2s] [--fe-rise:0px] md:bg-text-primary/20"
          aria-hidden
          onClick={closeAll}
        />
      )}
      <nav
        ref={navRef}
        style={{ '--fe-duration': '0.3s', '--fe-rise': '-8px' }}
        className={cn(
          // .fe-reveal: шапка видна сразу (в SSR и без JS), лишь мягко опускается на 8px.
          'fe-reveal fe-reveal--free fe-navbar fixed top-9 inset-x-0 mx-auto z-[100]',
          // Не transition-all: иначе transition тянет backdrop-filter и в
          // части движков blur на время/после смены soft↔surface пропадает.
          'transition-[transform,opacity,background-color,box-shadow,border-color] duration-500 ease-out',
          'rounded-[1.5rem] px-3 sm:px-5 lg:px-6 py-3 flex items-center gap-2 sm:gap-3',
          'max-w-[1440px] w-[calc(100%-2rem-env(safe-area-inset-left,0px)-env(safe-area-inset-right,0px))]',
          scrolled
            ? 'glass-surface border border-border-subtle shadow-lg shadow-black/5'
            : 'glass-surface-soft border border-black/[0.04]',
          isAdmin && scrolled && !menuOpen && '-translate-y-24 opacity-0 pointer-events-none'
        )}
      >
      <Link
        to="/"
        className={cn(FOCUS_RING, 'flex items-center gap-2 shrink-0 rounded-xl')}
        onClick={closeAll}
        aria-label={t('nav.homeAria')}
        title={t('nav.homeTitle')}
      >
        <Brand compact />
      </Link>

      {/* justify-end: при переполнении лишнее выезжает ВЛЕВО, поверх логотипа
          (задвоенный логотип на скринах руководителя 2026-07-05 и 2026-07-27).
          scrollWidth такое переполнение не показывает — ловится только
          сравнением боксов, см. scripts/e2e/navbar-overlap.mjs. Поэтому до xl
          длинные подписи заменяются короткими (`shortLabelKey`), а «О проекте»
          на десктопе живёт в футере и мобильном меню. */}
      <div className="fe-navbar-links hidden lg:flex items-center gap-3 xl:gap-5 flex-1 justify-end min-w-0">
        {primaryItems.map((item) => renderPrimaryLink(item, { desktop: true }))}
        <div className="relative" ref={calcWrapRef}>
          <button
            ref={calcBtnRef}
            type="button"
            onClick={() => { setCalcOpen((o) => !o); }}
            className={cn(
              FOCUS_RING,
              'flex items-center gap-1 text-sm font-medium transition-colors px-2 py-1 rounded-xl',
              calcOpen ? 'text-champagne' : 'text-text-secondary hover:text-text-primary'
            )}
            aria-expanded={calcOpen}
            aria-haspopup="menu"
            aria-controls={calcOpen ? 'fe-nav-calc-menu' : undefined}
          >
            {t('nav.calculators')}
            <ChevronDown className={cn('w-4 h-4 transition-transform', calcOpen && 'rotate-180')} />
          </button>
          {calcOpen && (
            <div
              id="fe-nav-calc-menu"
              className="fe-reveal fe-reveal--free fe-reveal--panel absolute right-0 top-full z-[110] mt-2 min-w-[240px] rounded-2xl border border-border-subtle bg-surface py-2 shadow-2xl ring-1 ring-black/[0.08]"
              role="menu"
            >
              {CALCULATOR_ITEMS.map((c) => (
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
                  {t(c.labelKey)}
                </NavLink>
              ))}
            </div>
          )}
        </div>
        {/* В пилюлю не влезает: доступна из футера и мобильного меню. */}
      </div>

      <div className="hidden lg:flex items-center shrink-0 gap-2 xl:gap-3">
        <IndicatorSearch variant="pill" />
        <LocaleSwitcher />
        <div className="h-5 w-px bg-border-subtle" aria-hidden />
        <AuthCluster />
      </div>

      <div className="lg:hidden ml-auto flex items-center gap-1">
        <IndicatorSearch className="!px-2 !py-1.5" />
        <LocaleSwitcher />
        <button
          ref={mobileBtnRef}
          type="button"
          onClick={() => { setMobileOpen(!mobileOpen); track(events.NAV_MOBILE_TOGGLE); }}
          className={cn(
            FOCUS_RING,
            'flex min-h-11 min-w-11 items-center justify-center rounded-xl p-2.5 text-text-secondary transition-colors hover:text-text-primary'
          )}
          aria-expanded={mobileOpen}
          aria-controls={mobileOpen ? 'fe-nav-mobile-menu' : undefined}
          aria-label={mobileOpen ? t('nav.closeMenu') : t('nav.openMenu')}
        >
          {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {mobileOpen && (
        <div ref={mobileMenuRef} id="fe-nav-mobile-menu" className="fe-reveal fe-reveal--free fe-reveal--panel fe-navbar-mobile-menu absolute left-0 right-0 top-full z-[110] mt-2 max-h-[min(80dvh,600px)] rounded-2xl border border-border-subtle bg-surface shadow-2xl ring-1 ring-black/[0.08] lg:hidden">
          <div className="fe-mnav-scroll">
            <div className="flex flex-col gap-1">
              {mobileGroups.map((group) => (
                <div key={group.id} className="fe-mnav-group">
                  {group.titleKey ? <p className="fe-mnav-title">{t(group.titleKey)}</p> : null}
                  {group.items.map((item) => {
                    const Icon = MOBILE_ICONS[item.icon];
                    const isActive = mobileActiveId === item.id;
                    return (
                      <Link
                        key={`m-${item.id}`}
                        to={item.to}
                        className={cn(navItemClass(isActive), 'fe-mnav-link')}
                        onClick={closeAll}
                        aria-current={isActive ? 'page' : undefined}
                      >
                        {Icon ? <Icon size={18} aria-hidden="true" className="fe-mnav-icon" /> : null}
                        {t(item.labelKey)}
                      </Link>
                    );
                  })}
                </div>
              ))}
              <div className="fe-mnav-group">
                <p className="fe-mnav-title">{t('nav.calculators')}</p>
                {CALCULATOR_ITEMS.map((c) => {
                  const CalcIcon = c.icon;
                  return (
                    <NavLink key={c.to} to={c.to} end className={({ isActive }) => cn(navItemClass(isActive), 'fe-mnav-link')} onClick={closeAll}>
                      <CalcIcon size={18} aria-hidden="true" className="fe-mnav-icon" />
                      {t(c.labelKey)}
                    </NavLink>
                  );
                })}
              </div>
              <div className="fe-mnav-group">
                <NavLink to="/about" className={({ isActive }) => cn(navItemClass(isActive), 'fe-mnav-link')} onClick={closeAll}>
                  <Info size={18} aria-hidden="true" className="fe-mnav-icon" />
                  {t('nav.about')}
                </NavLink>
              </div>
            </div>
          </div>
          {/* Вход и регистрация закреплены внизу: видны сразу, не после прокрутки списка. */}
          <div className="fe-mnav-foot">
            <AuthCluster mobile onNavigate={closeAll} />
          </div>
        </div>
      )}
    </nav>
    </>
  );
}
