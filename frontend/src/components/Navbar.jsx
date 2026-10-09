import { useState, useEffect, useRef, useCallback } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import {
  Menu, X, ChevronDown, ArrowLeftRight, BarChart3, BookOpen, Building2, CalendarDays, Clock, Coins, Flag, GitCompare, Globe2,
  Cookie, Home, Info, Landmark, Layers, Mail, Map as MapIcon, Percent, PiggyBank, TrendingUp, Code2, User,
} from 'lucide-react';
import { cn } from '../lib/format';
import { FOCUS_RING } from '../lib/uiTokens';
import { track, events } from '../lib/track';
import IndicatorSearch from './IndicatorSearch';
import LocaleSwitcher from './LocaleSwitcher';
import BottomSheet from './BottomSheet';
import Brand from './Brand';
import { useAuth } from '../context/authContext';
import {
  COUNTRIES_ANCHOR_ID, OPEN_NAV_MENU_EVENT, RATES_TO, WORLD_RATING_TO,
  isAccountPath, isToolsPath, mobileNavGroups, primaryNav, resolveActiveNavId,
} from '../lib/navItems';
import { useAnchorInView } from '../lib/useAnchorInView';
import { accountInitial } from '../lib/accountInitial';
import { useScrollDirection } from '../lib/useScrollDirection';
import { openConsentSettings } from '../lib/consent';
import { useFooterTone } from '../lib/useFooterTone';
import { megaCountries, megaIndicators } from '../lib/megaMenu';
import { isRussiaSectionPath } from '../lib/sitePaths';
import { useLocale, useT } from '../i18n';
import '../styles/ui-detail-nav-calendar.css';
import '../styles/shell.css';
import '../styles/z3-polish.css';
import '../styles/z2-shell.css';
import '../styles/k3-shell.css';

/** После раскрытия группы меню подводит её список в видимую часть шторки; без плавности при reduced-motion. */
function revealWhenRendered(id) {
  if (typeof window === 'undefined' || typeof window.requestAnimationFrame !== 'function') return;
  window.requestAnimationFrame(() => window.requestAnimationFrame(() => {
    const el = document.getElementById(id);
    if (!el || typeof el.scrollIntoView !== 'function') return;
    const reduce = typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    el.scrollIntoView({ block: 'nearest', behavior: reduce ? 'auto' : 'smooth' });
  }));
}

function AuthCluster({ mobile = false, onNavigate }) {
  const { isAuthed, isLoading, user } = useAuth();
  const { pathname } = useLocation();
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
    // Круг 11, G (U2): вошедшего видно по кружку с первой буквой имени (графит, не золото); на /account кнопка подсвечена.
    const current = isAccountPath(pathname);
    const initial = accountInitial(user);
    return (
      <Link
        to="/account"
        onClick={onNavigate}
        title={user?.display_name || user?.email || undefined}
        aria-current={current ? 'page' : undefined}
        className={cn(
          FOCUS_RING,
          'fe-nav-account text-sm font-semibold transition-colors',
          current && 'is-current',
          mobile && 'w-full justify-center text-center',
        )}
      >
        <span className="fe-avatar fe-avatar--sm" aria-hidden="true">{initial || <User size={14} strokeWidth={1.75} />}</span>
        <span className="fe-nav-account__text">{t('common.account')}</span>
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
          'fe-nav-login rounded-full px-4 py-1.5 text-sm font-semibold transition-colors',
          mobile && 'flex-1 justify-center text-center',
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

/** Иконка пункта меню в стеклянной «грани» 40 px: светлая плитка с бликом и мягкой тенью (рамок нет). */
function MnavTile({ icon: Icon }) {
  return (
    <span className="fe-mnav-tile" aria-hidden="true">
      <Icon size={18} className="fe-mnav-icon" />
    </span>
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
  trend: TrendingUp,
  layers: Layers,
  book: BookOpen,
};

// Инструменты: конвертер валют и калькуляторы (разные золотые значки, у каждого пометка «для каких стран») и конструктор виджетов.
const CALCULATOR_ITEMS = [
  { to: RATES_TO, labelKey: 'z2.tools.converter', noteKey: 'z2.tools.converter.note', icon: ArrowLeftRight },
  { to: '/calculator', labelKey: 'nav.calc.inflation', noteKey: 'w6g.nav.note.inflation', icon: Percent },
  { to: '/calculator/mortgage', labelKey: 'nav.calc.mortgage', noteKey: 'w6g.nav.note.mortgage', icon: Building2 },
  { to: '/calculator/compound', labelKey: 'nav.calc.compound', noteKey: 'w6g.nav.note.compound', icon: PiggyBank },
  { to: '/widgets', labelKey: 'w6g.nav.widgets', noteKey: 'w6g.nav.note.widgets', icon: Code2 },
];

/** Мега-панель «Страны мира»: флаги крупнейших экономик, популярные рейтинги, ссылки на каталог и рейтинг. */
function CountriesMega({ locale, t, onNavigate }) {
  const countries = megaCountries(locale);
  const indicators = megaIndicators();
  return (
    <div id="fe-nav-mega" className="fe-mega fe-reveal fe-reveal--free fe-reveal--panel">
      <div className="fe-mega__card fe-nav-panel" role="group" aria-label={t('z2.mega.aria')}>
        <div>
          <p className="fe-mega__title">{t('z2.mega.countriesTitle')}</p>
          <ul className="fe-mega__list fe-mega__list--flags">
            {countries.map((c) => (
              <li key={c.slug}>
                <Link to={c.to} className={cn(FOCUS_RING, 'fe-mega__link')} onClick={onNavigate}>
                  <span className="fe-mega__flag fe-mega__tile" aria-hidden="true">{c.flag}</span>
                  <span>{c.label}</span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <p className="fe-mega__title">{t('z2.mega.indicatorsTitle')}</p>
          <ul className="fe-mega__list">
            {indicators.map((item) => (
              <li key={item.slug}>
                <Link to={item.to} className={cn(FOCUS_RING, 'fe-mega__link')} onClick={onNavigate}>
                  <span className="fe-mega__tile fe-mega__tile--gem" aria-hidden="true"><BarChart3 size={16} className="text-champagne-ink" /></span>
                  <span>{t(item.labelKey)}</span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
        <div className="fe-mega__foot">
          <Link to="/#countries" className={cn(FOCUS_RING, 'fe-mega__all rounded-md')} onClick={onNavigate}>
            {t('z2.mega.all')}
          </Link>
          <Link to={WORLD_RATING_TO} className={cn(FOCUS_RING, 'fe-mega__all rounded-md')} onClick={onNavigate}>
            {t('z2.mega.rating')}
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function Navbar() {
  const t = useT();
  const { locale } = useLocale();
  // Прокрутка: шапка плотнее (scrolled), а на телефоне при движении вниз сжимается и уезжает вверх вместе с лентой курсов.
  const { scrolled, deep, dir } = useScrollDirection();
  const compact = deep && dir === 'down';
  // Над тёмным подвалом шапка получает тёмный тон (сапфировое стекло): светлое стекло там становилось грязно-серым.
  const overFooter = useFooterTone().nav;
  // Открытые панели помнят адрес, на котором их открыли: при любом переходе (ссылка, «назад», программный переход)
  // адрес меняется, и панель закрывается сама, без отдельных обработчиков на каждой ссылке.
  const { pathname, hash, key: locationKey } = useLocation();
  const [mobileOpenAt, setMobileOpenAt] = useState(null);
  const [calcOpenAt, setCalcOpenAt] = useState(null);
  const [megaOpenAt, setMegaOpenAt] = useState(null);
  const mobileOpen = mobileOpenAt === locationKey;
  const calcOpen = calcOpenAt === locationKey;
  const megaOpen = megaOpenAt === locationKey;
  // Раскрытые группы меню: «Россия» раскрыта сама только на страницах российского раздела.
  const [openGroups, setOpenGroups] = useState({});
  const navRef = useRef(null);
  const calcWrapRef = useRef(null);
  const calcBtnRef = useRef(null);
  const megaWrapRef = useRef(null);
  const megaTimer = useRef(0);
  const mobileBtnRef = useRef(null);
  // Служебный раздел /admin/*: fixed-пилюля наезжала на карточки BI при
  // скролле (обход BI 2.1, этап 4а) — показываем шапку только вверху страницы.
  const isAdmin = pathname.startsWith('/admin');
  // Круг 11, G (U33): «Страны» подсвечен, когда в адресе #countries или человек долистал до каталога стран на главной.
  const countriesInView = useAnchorInView(COUNTRIES_ANCHOR_ID, pathname === '/');
  const activeNavId = resolveActiveNavId(pathname, undefined, hash, countriesInView);
  const toolsActive = isToolsPath(pathname);
  const primaryItems = primaryNav(locale);
  const mobileGroups = mobileNavGroups(locale);
  const mobileActiveId = resolveActiveNavId(pathname, mobileGroups.flatMap((group) => group.items), hash, countriesInView);
  // Круг 9, S10: «Инструменты» стоят сразу после мировых разделов, до «Россия»: раскрытая «Россия» (4 подпункта) больше не уводит
  // конвертер и калькуляторы на два экрана вниз и не прижимает «Виджеты» к кнопкам «Войти».
  const menuGroups = [mobileGroups[0], { id: 'tools' }, ...mobileGroups.slice(1)];

  const setMobileOpen = (next) => setMobileOpenAt(next ? locationKey : null);
  const setCalcOpen = (next) => {
    setCalcOpenAt(next ? locationKey : null);
    if (next) setMegaOpenAt(null);
  };
  const closeAll = useCallback(() => {
    setMobileOpenAt(null);
    setCalcOpenAt(null);
    setMegaOpenAt(null);
  }, []);

  // «Ещё» в нижней док-панели телефона открывает то же меню, что и гамбургер.
  useEffect(() => {
    const open = () => { setMobileOpenAt(locationKey); setCalcOpenAt(null); setMegaOpenAt(null); };
    window.addEventListener(OPEN_NAV_MENU_EVENT, open);
    return () => window.removeEventListener(OPEN_NAV_MENU_EVENT, open);
  }, [locationKey]);

  useEffect(() => () => window.clearTimeout(megaTimer.current), []);

  // --fe-header-h: высота шапки в покое (+ 6 px опускания при прокрутке). Вместе с --fe-ticker-h (её ставит LiveTicker) читается
  // `html { scroll-padding-top }` в k3-shell.css: якоря и scrollIntoView останавливают заголовок секции ниже шапки.
  // Сжатую шапку телефона (data-compact) не меряем: запас считается по полному размеру, иначе заголовок мог бы оказаться под ней.
  useEffect(() => {
    const node = navRef.current;
    if (!node || typeof document === 'undefined') return undefined;
    const root = document.documentElement;
    const apply = () => {
      if (node.dataset.compact === 'true') return;
      const h = Math.ceil(node.offsetHeight);
      if (h > 0) root.style.setProperty('--fe-header-h', `${h + 6}px`);
    };
    apply();
    let observer = null;
    if (typeof ResizeObserver !== 'undefined') {
      observer = new ResizeObserver(apply);
      observer.observe(node);
    }
    window.addEventListener('resize', apply);
    return () => {
      observer?.disconnect();
      window.removeEventListener('resize', apply);
      root.style.removeProperty('--fe-header-h');
    };
  }, []);

  const panelOpen = mobileOpen || calcOpen || megaOpen;
  useEffect(() => {
    if (!panelOpen) return undefined;
    // Тап/клик вне открытой панели закрывает её (pointerdown + mousedown: второй — для окружений без Pointer Events).
    const onDoc = (e) => {
      const inCalc = calcWrapRef.current?.contains(e.target);
      const inMega = megaWrapRef.current?.contains(e.target);
      // Шторка меню рисуется порталом в body, поэтому ищем её по id, а не через ref внутри шапки.
      const inMobile = document.getElementById('fe-nav-mobile-menu')?.contains(e.target) || mobileBtnRef.current?.contains(e.target);
      if (calcOpen && !inCalc) setCalcOpenAt(null);
      if (megaOpen && !inMega) setMegaOpenAt(null);
      if (mobileOpen && !inMobile) setMobileOpenAt(null);
    };
    const onKey = (e) => {
      if (e.key !== 'Escape') return;
      // Фокус — на кнопку, которая открыла панель: клавиатурный пользователь не теряет место.
      const target = calcOpen ? calcBtnRef.current : (megaOpen ? megaWrapRef.current?.querySelector('a') : mobileBtnRef.current);
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
  }, [panelOpen, mobileOpen, calcOpen, megaOpen, closeAll]);

  // Поиск открылся (Ctrl/Cmd+K, «/» или нажатие на лупу): панели меню закрываются, иначе за окном поиска оставались
  // размытая страница и открытое меню. Окно поиска рисуется порталом в body — следим за его появлением.
  useEffect(() => {
    if (!panelOpen || typeof MutationObserver === 'undefined') return undefined;
    const observer = new MutationObserver(() => {
      if (document.querySelector('[data-fe-search-dialog]')) closeAll();
    });
    observer.observe(document.body, { childList: true });
    return () => observer.disconnect();
  }, [panelOpen, closeAll]);

  const navItemClass = (isActive) => cn(
    FOCUS_RING,
    'rounded-lg text-sm font-medium transition-colors duration-200 px-0.5 py-0.5 -mx-0.5 whitespace-nowrap',
    isActive
      ? 'text-champagne'
      : 'text-text-secondary hover:text-text-primary'
  );

  const itemClass = cn(
    FOCUS_RING,
    'fe-nav-tool'
  );

  const menuOpen = mobileOpen || calcOpen;

  // Мега-панель «Страны мира» открывается наведением мыши с небольшой паузой (чтобы не мигать при пролёте курсора),
  // фокусом с клавиатуры и закрывается при уходе курсора или фокуса. Нажатие на саму ссылку ведёт в каталог стран.
  const openMega = () => {
    window.clearTimeout(megaTimer.current);
    megaTimer.current = window.setTimeout(() => { setMegaOpenAt(locationKey); setCalcOpenAt(null); }, 110);
  };
  const closeMega = () => {
    window.clearTimeout(megaTimer.current);
    megaTimer.current = window.setTimeout(() => setMegaOpenAt(null), 200);
  };

  const renderPrimaryLink = (item, { desktop = false } = {}) => {
    const isActive = activeNavId === item.id;
    const full = t(item.labelKey);
    const short = item.shortLabelKey ? t(item.shortLabelKey) : null;
    const link = (
      <Link
        key={`${desktop ? 'd' : 'm'}-${item.id}`}
        to={item.to}
        className={cn(navItemClass(isActive), desktop && 'fe-nav-link')}
        onClick={closeAll}
        aria-current={isActive ? 'page' : undefined}
        aria-expanded={desktop && item.id === 'countries' ? megaOpen : undefined}
        aria-controls={desktop && item.id === 'countries' && megaOpen ? 'fe-nav-mega' : undefined}
      >
        {desktop && short ? (
          <>
            <span className="2xl:hidden">{short}</span>
            <span className="hidden 2xl:inline">{full}</span>
          </>
        ) : full}
      </Link>
    );
    if (!(desktop && item.id === 'countries')) return link;
    return (
      <div
        key="d-countries-wrap"
        ref={megaWrapRef}
        className="relative"
        onPointerEnter={(e) => { if (e.pointerType === 'mouse') openMega(); }}
        onPointerLeave={(e) => { if (e.pointerType === 'mouse') closeMega(); }}
        onFocus={openMega}
        onBlur={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) closeMega(); }}
      >
        {link}
        {megaOpen ? <CountriesMega locale={locale} t={t} onNavigate={closeAll} /> : null}
      </div>
    );
  };

  return (
    <>
      {calcOpen && (
        <div
          className="fe-nav-scrim fe-reveal fixed inset-0 z-[80] [--fe-duration:0.2s] [--fe-rise:0px]"
          aria-hidden
          onClick={closeAll}
        />
      )}
      <nav
        ref={navRef}
        style={{ '--fe-duration': '0.3s', '--fe-rise': '-8px' }}
        data-scrolled={scrolled ? 'true' : 'false'}
        // Сжатое состояние не снимается, пока открыта шторка: иначе шапка под затемнением съезжала вниз и торчала «второй шапкой».
        data-compact={compact ? 'true' : 'false'}
        data-tone={overFooter ? 'dark' : undefined}
        className={cn(
          // .fe-reveal: шапка видна сразу (в SSR и без JS), лишь мягко опускается на 8px.
          // Стекло капсулы (L1, плотнее при прокрутке) и тень задаёт styles/k3-shell.css; движутся только transform и opacity.
          'fe-reveal fe-reveal--free fe-navbar fe-navbar--glass fixed top-9 inset-x-0 mx-auto z-[100]',
          'transition-[transform,opacity] duration-300 ease-out',
          'rounded-[1.5rem] px-3 sm:px-5 lg:px-6 py-3 flex items-center gap-2 sm:gap-3',
          'max-w-[1440px] w-[calc(100%-2rem-env(safe-area-inset-left,0px)-env(safe-area-inset-right,0px))]',
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
          сравнением боксов, см. scripts/e2e/navbar-overlap.mjs. Поэтому до 2xl
          длинные подписи заменяются короткими (`shortLabelKey`), поиск сжимается до лупы,
          а «О проекте» на десктопе живёт в футере и мобильном меню. */}
      <div className="fe-navbar-links hidden xl:flex items-center flex-1 justify-end min-w-0">
        {primaryItems.map((item) => renderPrimaryLink(item, { desktop: true }))}
        <div className="relative" ref={calcWrapRef}>
          <button
            ref={calcBtnRef}
            type="button"
            onClick={() => { setCalcOpen(!calcOpen); }}
            className={cn(
              FOCUS_RING,
              'fe-nav-tools-btn flex items-center gap-1 text-sm font-medium transition-colors px-2 py-1 rounded-xl',
              calcOpen ? 'text-champagne' : (toolsActive ? 'text-text-primary' : 'text-text-secondary hover:text-text-primary')
            )}
            data-active={toolsActive ? 'true' : undefined}
            aria-expanded={calcOpen}
            aria-haspopup="menu"
            aria-controls={calcOpen ? 'fe-nav-calc-menu' : undefined}
          >
            {t('w6g.nav.tools')}
            <ChevronDown className={cn('w-4 h-4 transition-transform', calcOpen && 'rotate-180')} />
          </button>
          {calcOpen && (
            <div
              id="fe-nav-calc-menu"
              className="fe-nav-panel fe-nav-tools fe-reveal fe-reveal--free fe-reveal--panel absolute right-0 top-full z-[110] mt-2 rounded-2xl shadow-2xl"
              role="menu"
            >
              {CALCULATOR_ITEMS.map((c) => {
                const ToolIcon = c.icon;
                return (
                  <NavLink
                    key={c.to}
                    to={c.to}
                    end
                    className={({ isActive }) => cn(itemClass, isActive && 'bg-champagne/5')}
                    onClick={closeAll}
                    role="menuitem"
                  >
                    <span className="fe-tool-ico"><ToolIcon aria-hidden="true" /></span>
                    <span className="fe-nav-tool__text">
                      <span className="fe-nav-tool__name">{t(c.labelKey)}</span>
                      <span className="fe-nav-tool__note">{t(c.noteKey)}</span>
                    </span>
                  </NavLink>
                );
              })}
            </div>
          )}
        </div>
        {/* В пилюлю не влезает: доступна из футера и мобильного меню. */}
      </div>

      <div className="hidden xl:flex items-center shrink-0 gap-2 xl:gap-3">
        <div className="fe-nav-search"><IndicatorSearch variant="pill" /></div>
        <LocaleSwitcher />
        <AuthCluster />
      </div>

      <div className="fe-nav-cluster xl:hidden ml-auto flex items-center">
        <IndicatorSearch className="fe-nav-round" />
        <LocaleSwitcher className="fe-nav-round" />
        <button
          ref={mobileBtnRef}
          type="button"
          onClick={() => { setMobileOpen(!mobileOpen); track(events.NAV_MOBILE_TOGGLE); }}
          className={cn(
            FOCUS_RING,
            'fe-nav-round'
          )}
          aria-expanded={mobileOpen}
          aria-controls={mobileOpen ? 'fe-nav-mobile-menu' : undefined}
          aria-label={mobileOpen ? t('nav.closeMenu') : t('nav.openMenu')}
        >
          {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>


    </nav>

      {/* Меню телефона и планшета: шторка снизу порталом в body (шапка с blur не должна быть её контейнером). */}
      <BottomSheet
        open={mobileOpen}
        onClose={closeAll}
        id="fe-nav-mobile-menu"
        ariaLabel={t('k3.sheet.menuAria')}
        className="fe-navbar-mobile-menu"
        bodyClassName="fe-mnav-scroll"
        footerClassName="fe-mnav-foot"
        footer={<AuthCluster mobile onNavigate={closeAll} />}
      >
        <div className="fe-mnav-columns">
          {menuGroups.map((group) => {
            if (group.id === 'tools') {
              return (
                <div key="tools" className="fe-mnav-group">
                  <p className="fe-mnav-title">{t('w6g.nav.tools')}</p>
                  {CALCULATOR_ITEMS.map((c) => (
                    <NavLink key={c.to} to={c.to} end className={({ isActive }) => cn(navItemClass(isActive), 'fe-mnav-link')} onClick={closeAll}>
                      <MnavTile icon={c.icon} />
                      <span className="fe-mnav-text"><span className="fe-mnav-label">{t(c.labelKey)}</span></span>
                    </NavLink>
                  ))}
                </div>
              );
            }
            const renderLink = (item, nested = false) => {
              const Icon = MOBILE_ICONS[item.icon];
              const isActive = mobileActiveId === item.id;
              return (
                <Link
                  key={`m-${item.id}`}
                  to={item.to}
                  className={cn(navItemClass(isActive), 'fe-mnav-link', nested && 'fe-mnav-link--nested')}
                  onClick={closeAll}
                  aria-current={isActive ? 'page' : undefined}
                >
                  {Icon ? <MnavTile icon={Icon} /> : null}
                  <span className="fe-mnav-text">
                    <span className="fe-mnav-label">{t(item.labelKey)}</span>
                    {item.hintKey ? <span className="fe-mnav-hint">{t(item.hintKey)}</span> : null}
                  </span>
                </Link>
              );
            };
            if (group.collapsible) {
              const GroupIcon = MOBILE_ICONS[group.icon];
              const open = openGroups[group.id] ?? isRussiaSectionPath(pathname);
              const panelId = `fe-nav-group-${group.id}`;
              return (
                <div key={group.id} className="fe-mnav-group fe-mnav-group--collapsible">
                  <button
                    type="button"
                    className={cn(navItemClass(false), 'fe-mnav-link fe-mnav-toggle w-full text-left')}
                    aria-expanded={open}
                    aria-controls={panelId}
                    onClick={() => {
                      setOpenGroups((prev) => ({ ...prev, [group.id]: !open }));
                      // Круг 8, S5: раскрытые подпункты прокручиваются в видимую часть списка (раньше менялась только стрелка).
                      if (!open) revealWhenRendered(panelId);
                    }}
                  >
                    {GroupIcon ? <MnavTile icon={GroupIcon} /> : null}
                    <span className="fe-mnav-text">
                      <span className="fe-mnav-label">{t(group.titleKey)}</span>
                      {group.hintKey ? <span className="fe-mnav-hint">{t(group.hintKey)}</span> : null}
                    </span>
                    <ChevronDown size={16} aria-hidden="true" className={cn('fe-mnav-chevron', open && 'is-open')} />
                  </button>
                  {open ? (
                    <div id={panelId} className="fe-mnav-sub">
                      {group.items.map((item) => renderLink(item, true))}
                    </div>
                  ) : null}
                </div>
              );
            }
            return (
              <div key={group.id} className="fe-mnav-group">
                {group.titleKey ? <p className="fe-mnav-title">{t(group.titleKey)}</p> : null}
                {group.items.map((item) => renderLink(item))}
              </div>
            );
          })}
          <div className="fe-mnav-group">
            <NavLink to="/about" className={({ isActive }) => cn(navItemClass(isActive), 'fe-mnav-link')} onClick={closeAll}>
              <MnavTile icon={Info} />
              <span className="fe-mnav-text"><span className="fe-mnav-label">{t('nav.about')}</span></span>
            </NavLink>
            <a
              href="mailto:rebeka.ee@yandex.ru"
              className={cn(navItemClass(false), 'fe-mnav-link')}
              onClick={() => { track(events.CONTACT_EMAIL); closeAll(); }}
            >
              <MnavTile icon={Mail} />
              <span className="fe-mnav-text"><span className="fe-mnav-label">{t('shell.footer.contact')}</span></span>
            </a>
            {/* Настройки cookie живут здесь и в подвале: плавающего значка на странице нет. */}
            <button
              type="button"
              className={cn(navItemClass(false), 'fe-mnav-link w-full text-left')}
              data-testid="menu-cookie-settings"
              onClick={() => { closeAll(); openConsentSettings(); }}
            >
              <MnavTile icon={Cookie} />
              <span className="fe-mnav-text"><span className="fe-mnav-label">{t('cookie.aria')}</span></span>
            </button>
          </div>
        </div>
      </BottomSheet>
    </>
  );
}
