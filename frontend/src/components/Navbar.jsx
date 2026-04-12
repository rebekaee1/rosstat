import { useState, useEffect, useRef } from 'react';
import { Link, NavLink } from 'react-router-dom';
import { TrendingUp, Activity, Menu, X, ChevronDown } from 'lucide-react';
import gsap from 'gsap';
import { cn } from '../lib/format';
import { CATEGORIES } from '../lib/categories';
import { FOCUS_RING } from '../lib/uiTokens';
import { track, events } from '../lib/track';

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [catOpen, setCatOpen] = useState(false);
  const navRef = useRef(null);
  const catWrapRef = useRef(null);

  const closeAll = () => {
    setMobileOpen(false);
    setCatOpen(false);
  };

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 200);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  useEffect(() => {
    if (!catOpen && !mobileOpen) return;
    const onDoc = (e) => {
      if (catOpen && catWrapRef.current && !catWrapRef.current.contains(e.target)) {
        setCatOpen(false);
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
  }, [catOpen, mobileOpen]);

  useEffect(() => {
    if (!navRef.current) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const tween = gsap.fromTo(navRef.current,
      { y: -20, opacity: 0 },
      { y: 0, opacity: 1, duration: 0.8, ease: 'power3.out', delay: 0.2 }
    );
    return () => tween.kill();
  }, []);

  const linkClass = ({ isActive }) => cn(
    FOCUS_RING,
    'rounded-lg text-sm font-medium transition-colors duration-200 px-0.5 py-0.5 -mx-0.5',
    isActive
      ? 'text-champagne'
      : 'text-text-secondary hover:text-text-primary'
  );

  const itemClass = cn(
    FOCUS_RING,
    'rounded-xl block px-4 py-2.5 text-sm text-left transition-colors hover:bg-obsidian-lighter/80'
  );

  const menuOpen = catOpen || mobileOpen;

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
          'fixed top-4 inset-x-0 mx-auto z-[100] transition-all duration-500 ease-out',
          'rounded-[2rem] px-6 py-3 flex items-center gap-4 md:gap-6',
          'max-w-5xl w-[calc(100%-2rem)]',
          scrolled
            ? 'glass-surface border border-border-subtle shadow-lg shadow-black/5'
            : 'bg-white/60 backdrop-blur-sm border border-black/[0.04]'
        )}
      >
      <Link
        to="/"
        className={cn(FOCUS_RING, 'flex items-center gap-2 shrink-0 rounded-xl')}
        onClick={closeAll}
      >
        <TrendingUp className="w-5 h-5 text-champagne" />
        <span className="text-base font-bold tracking-tight text-text-primary">
          Forecast Economy
        </span>
      </Link>

      <div className="hidden md:flex items-center gap-2 flex-1 justify-end flex-wrap">
        <NavLink to="/" end className={linkClass} onClick={closeAll}>
          Главная
        </NavLink>

        <div className="relative" ref={catWrapRef}>
          <button
            type="button"
            onClick={() => { setCatOpen((o) => !o); track(events.NAV_CATEGORY_OPEN); }}
            className={cn(
              FOCUS_RING,
              'flex items-center gap-1 text-sm font-medium transition-colors px-2 py-1 rounded-xl',
              catOpen ? 'text-champagne' : 'text-text-secondary hover:text-text-primary'
            )}
            aria-expanded={catOpen}
            aria-haspopup="menu"
          >
            Категории
            <ChevronDown className={cn('w-4 h-4 transition-transform', catOpen && 'rotate-180')} />
          </button>
          {catOpen && (
            <div
              className="absolute right-0 top-full z-[110] mt-2 max-h-[min(70vh,420px)] min-w-[min(100vw-2rem,280px)] overflow-y-auto rounded-2xl border border-border-subtle bg-surface py-2 shadow-2xl ring-1 ring-black/[0.08]"
              role="menu"
            >
              {CATEGORIES.map((c) =>
                c.apiCategory ? (
                  <NavLink
                    key={c.slug}
                    to={`/category/${c.slug}`}
                    className={({ isActive }) =>
                      cn(itemClass, isActive ? 'text-champagne bg-champagne/5' : 'text-text-primary')
                    }
                    onClick={closeAll}
                    role="menuitem"
                  >
                    {c.name}
                  </NavLink>
                ) : (
                  <div
                    key={c.slug}
                    className={cn(itemClass, 'cursor-default text-text-secondary')}
                  >
                    {c.name}
                    <span className="ml-2 text-[10px] uppercase font-mono">скоро</span>
                  </div>
                )
              )}
              <div className="mx-4 my-1 h-px bg-border-subtle" />
              <NavLink
                to="/demographics"
                className={({ isActive }) =>
                  cn(itemClass, isActive ? 'text-champagne bg-champagne/5' : 'text-text-primary')
                }
                onClick={closeAll}
                role="menuitem"
              >
                Возрастная структура
              </NavLink>
            </div>
          )}
        </div>

        <NavLink to="/calculator" className={linkClass} onClick={closeAll}>
          Калькулятор
        </NavLink>
        <NavLink to="/about" className={linkClass} onClick={closeAll}>
          О проекте
        </NavLink>
      </div>

      <div className="hidden md:flex items-center shrink-0">
        <div className="relative group flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-obsidian-lighter/50 border border-border-subtle cursor-default">
          <Activity className="w-3 h-3 text-positive pulse-dot" />
          <span className="text-xs font-mono text-text-secondary">Онлайн</span>
          <div className="absolute top-full right-0 mt-2 px-3 py-2 rounded-xl bg-obsidian border border-border-subtle text-xs text-text-secondary whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none shadow-xl z-50">
            Все данные актуальны. Обновление ежедневно в 06:00 МСК
          </div>
        </div>
      </div>

      <button
        type="button"
        onClick={() => { setMobileOpen(!mobileOpen); track(events.NAV_MOBILE_TOGGLE); }}
        className={cn(
          FOCUS_RING,
          'md:hidden ml-auto rounded-xl text-text-secondary hover:text-text-primary transition-colors p-1.5'
        )}
        aria-expanded={mobileOpen}
        aria-label={mobileOpen ? 'Закрыть меню' : 'Открыть меню'}
      >
        {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
      </button>

      {mobileOpen && (
        <div className="absolute left-0 right-0 top-full z-[110] mt-2 max-h-[min(80vh,520px)] overflow-y-auto rounded-2xl border border-border-subtle bg-surface p-4 shadow-2xl ring-1 ring-black/[0.08] md:hidden">
          <div className="flex flex-col gap-1">
            <NavLink to="/" end className={linkClass} onClick={closeAll}>
              Главная
            </NavLink>
            <p className="text-[10px] uppercase tracking-wider text-text-tertiary px-2 pt-3 pb-1">
              Категории
            </p>
            {CATEGORIES.map((c) =>
              c.apiCategory ? (
                <NavLink
                  key={c.slug}
                  to={`/category/${c.slug}`}
                  className={linkClass}
                  onClick={closeAll}
                >
                  {c.name}
                </NavLink>
              ) : (
                <span key={c.slug} className="text-sm text-text-tertiary/90 px-2 py-1">
                  {c.name}{' '}
                  <span className="text-[10px] uppercase font-mono">скоро</span>
                </span>
              )
            )}
            <div className="mx-2 my-1 h-px bg-border-subtle" />
            <NavLink to="/demographics" className={linkClass} onClick={closeAll}>
              Возрастная структура
            </NavLink>
            <NavLink to="/calculator" className={linkClass} onClick={closeAll}>
              Калькулятор
            </NavLink>
            <NavLink to="/about" className={linkClass} onClick={closeAll}>
              О проекте
            </NavLink>
          </div>
        </div>
      )}
    </nav>
    </>
  );
}
