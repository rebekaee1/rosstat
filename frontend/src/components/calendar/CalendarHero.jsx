import { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Calendar as CalendarIcon } from 'lucide-react';
import gsap from 'gsap';
import { cn } from '../../lib/format';

function CountdownUnit({ value, label }) {
  return (
    <div className="text-center">
      <div className="text-2xl md:text-3xl font-display font-bold text-text-primary tabular-nums leading-none">
        {String(value).padStart(2, '0')}
      </div>
      <div className="text-[10px] uppercase tracking-wider text-text-tertiary mt-1">{label}</div>
    </div>
  );
}

function Separator() {
  return <span className="text-xl text-text-tertiary/40 font-light self-start mt-1">:</span>;
}

export default function CalendarHero({ nextEvent }) {
  const ref = useRef(null);
  const [remaining, setRemaining] = useState(null);

  useEffect(() => {
    if (!nextEvent) return;
    const target = new Date(nextEvent.scheduled_date + 'T' + (nextEvent.scheduled_time || '12:00') + ':00+03:00');

    const tick = () => {
      const now = new Date();
      const diff = target.getTime() - now.getTime();
      if (diff <= 0) { setRemaining(null); return; }
      const d = Math.floor(diff / 86400000);
      const h = Math.floor((diff % 86400000) / 3600000);
      const m = Math.floor((diff % 3600000) / 60000);
      const s = Math.floor((diff % 60000) / 1000);
      setRemaining({ d, h, m, s });
    };

    tick();
    const iv = setInterval(tick, 1000);
    return () => clearInterval(iv);
  }, [nextEvent]);

  useEffect(() => {
    if (!ref.current || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const tween = gsap.fromTo(ref.current,
      { y: 20, opacity: 0 },
      { y: 0, opacity: 1, duration: 0.6, ease: 'power3.out' }
    );
    return () => tween.kill();
  }, []);

  if (!nextEvent || !remaining) return null;

  return (
    <div
      ref={ref}
      className="relative overflow-hidden rounded-[2rem] border border-champagne/15 bg-gradient-to-br from-surface via-surface to-champagne/[0.04] p-6 md:p-8 mb-8"
    >
      <div className="absolute top-0 right-0 w-48 h-48 bg-champagne/5 rounded-full -translate-y-1/2 translate-x-1/2 blur-3xl pointer-events-none" />

      <div className="relative flex flex-col md:flex-row md:items-center md:justify-between gap-6">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-3">
            <CalendarIcon className="w-4 h-4 text-champagne" />
            <span className="text-xs uppercase tracking-widest text-champagne font-semibold">
              Ближайшее событие
            </span>
          </div>
          <h2 className="text-lg md:text-xl font-semibold text-text-primary leading-snug mb-2 line-clamp-2">
            {nextEvent.title}
          </h2>
          <p className="text-sm text-text-secondary">
            {new Date(nextEvent.scheduled_date).toLocaleDateString('ru-RU', {
              weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'
            })}
            {nextEvent.scheduled_time && (
              <span className="ml-1 font-mono">{nextEvent.scheduled_time} МСК</span>
            )}
          </p>
          {nextEvent.indicator_code && (
            <Link
              to={`/indicator/${nextEvent.indicator_code}`}
              className="inline-flex items-center gap-1 mt-2 text-sm text-champagne hover:text-champagne-muted transition-colors"
            >
              {nextEvent.indicator_name || nextEvent.indicator_code}
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          )}
        </div>

        <div className="flex items-center gap-3 md:gap-4 shrink-0">
          {remaining.d > 0 && (
            <>
              <CountdownUnit value={remaining.d} label={remaining.d === 1 ? 'день' : remaining.d < 5 ? 'дня' : 'дней'} />
              <Separator />
            </>
          )}
          <CountdownUnit value={remaining.h} label="час." />
          <Separator />
          <CountdownUnit value={remaining.m} label="мин." />
          {remaining.d === 0 && (
            <>
              <Separator />
              <CountdownUnit value={remaining.s} label="сек." />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
