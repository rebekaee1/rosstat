import { useState, useEffect, useRef } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import { BarChart3, Activity, Menu, X } from 'lucide-react';
import gsap from 'gsap';
import { cn } from '../lib/format';

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const navRef = useRef(null);
  const location = useLocation();

  useEffect(() => {
    setMobileOpen(false);
  }, [location]);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 200);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  useEffect(() => {
    if (!navRef.current) return;
    gsap.fromTo(navRef.current,
      { y: -20, opacity: 0 },
      { y: 0, opacity: 1, duration: 0.8, ease: 'power3.out', delay: 0.2 }
    );
  }, []);

  const linkClass = ({ isActive }) => cn(
    'text-sm font-medium transition-colors duration-200',
    isActive
      ? 'text-champagne'
      : 'text-ivory-muted/70 hover:text-text-primary'
  );

  return (
    <nav
      ref={navRef}
      className={cn(
        'fixed top-4 inset-x-0 mx-auto z-50 transition-all duration-500 ease-out',
        'rounded-[2rem] px-6 py-3 flex items-center gap-6',
        'max-w-3xl w-[calc(100%-2rem)]',
        scrolled
          ? 'glass-surface border border-border-subtle shadow-lg shadow-black/30'
          : 'bg-obsidian/50 backdrop-blur-sm border border-white/[0.03]'
      )}
    >
      <Link to="/" className="flex items-center gap-2 shrink-0">
        <BarChart3 className="w-5 h-5 text-champagne" />
        <span className="text-base font-bold tracking-tight text-text-primary">
          RuStats
        </span>
      </Link>

      <div className="hidden md:flex items-center gap-5 flex-1 justify-end">
        <NavLink to="/" end className={linkClass}>Обзор</NavLink>
        <NavLink to="/indicator/cpi" className={linkClass}>ИПЦ</NavLink>
        <NavLink to="/indicator/cpi-food" className={linkClass}>Продтовары</NavLink>
        <NavLink to="/indicator/cpi-services" className={linkClass}>Услуги</NavLink>
      </div>

      <div className="hidden md:flex items-center shrink-0">
        <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-obsidian-lighter/50 border border-border-subtle">
          <Activity className="w-3 h-3 text-positive pulse-dot" />
          <span className="text-xs font-mono text-text-secondary">Live</span>
        </div>
      </div>

      <button
        onClick={() => setMobileOpen(!mobileOpen)}
        className="md:hidden ml-auto text-text-secondary hover:text-text-primary transition-colors"
      >
        {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
      </button>

      {mobileOpen && (
        <div className="absolute top-full left-0 right-0 mt-2 p-4 rounded-2xl glass-surface border border-border-subtle md:hidden">
          <div className="flex flex-col gap-3">
            <NavLink to="/" end className={linkClass}>Обзор</NavLink>
            <NavLink to="/indicator/cpi" className={linkClass}>ИПЦ</NavLink>
            <NavLink to="/indicator/cpi-food" className={linkClass}>Продтовары</NavLink>
            <NavLink to="/indicator/cpi-services" className={linkClass}>Услуги</NavLink>
          </div>
        </div>
      )}
    </nav>
  );
}
