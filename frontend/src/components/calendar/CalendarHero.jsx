import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Calendar as CalendarIcon } from 'lucide-react';
import {
  russiaIndicatorPath,
} from '../../lib/sitePaths';
import { useLocale, useT } from '../../i18n';
import { plural } from '../../lib/calcFormat';
import '../../styles/ui-detail-nav-calendar.css';


function CountdownUnit({ value, label }) {
  return (
    <div className="text-center">
      <div className="text-2xl md:text-3xl font-display font-bold text-text-primary tabular-nums leading-none">
        {String(value).padStart(2, '0')}
      </div>
      <div className="text-[13px] text-text-secondary mt-1">{label}</div>
    </div>
  );
}

function Separator() {
  return <span className="text-xl text-text-tertiary/40 font-light self-start mt-1">:</span>;
}

function pluralUnit(n, unit, t, locale) {
  const form = locale === 'en' ? (n === 1 ? 'one' : 'many') : plural(n, 'one', 'few', 'many');
  return t(`w3.cal.unit.${unit}.${form}`);
}

export default function CalendarHero({ nextEvent }) {
  const t = useT();
  const { locale } = useLocale();
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

  if (!nextEvent || !remaining) return null;

  const dateLocale = locale === 'en' ? 'en-US' : 'ru-RU';

  return (
    <div
      style={{ '--fe-duration': '0.4s', '--fe-rise': '12px' }}
      className="fe-reveal fe-reveal--free fe-panel relative overflow-hidden rounded-[1.5rem] border border-champagne/15 bg-gradient-to-br from-surface via-surface to-champagne/[0.04] p-6 md:p-8 mb-8"
    >
      <div className="absolute top-0 right-0 w-48 h-48 bg-champagne/5 rounded-full -translate-y-1/2 translate-x-1/2 blur-3xl pointer-events-none" />

      <div className="relative flex flex-col md:flex-row md:items-center md:justify-between gap-6">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-3">
            <CalendarIcon className="w-4 h-4 text-champagne" />
            <span className="text-sm text-champagne-ink font-semibold">
              {t('calendar.hero.nextEvent')}
            </span>
          </div>
          <h2 className="text-lg md:text-xl font-semibold text-text-primary leading-snug mb-2 line-clamp-2">
            {nextEvent.title}
          </h2>
          <p className="text-sm text-text-secondary">
            {new Date(nextEvent.scheduled_date).toLocaleDateString(dateLocale, {
              weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'
            })}
            {nextEvent.scheduled_time && (
              <span className="ml-1 tabular-nums">{nextEvent.scheduled_time} {t('calendar.hero.msk')}</span>
            )}
          </p>
          {nextEvent.indicator_code && (
            <Link
              to={russiaIndicatorPath(nextEvent.indicator_code)}
              className="inline-flex items-center gap-1 mt-2 text-sm text-champagne hover:text-champagne-muted transition-colors"
            >
              {t('w3.cal.openIndicator')}
              <ArrowRight className="w-3.5 h-3.5" aria-hidden="true" />
            </Link>
          )}
        </div>

        <div className="flex items-center gap-3 md:gap-4 shrink-0">
          {remaining.d > 0 && (
            <>
              <CountdownUnit value={remaining.d} label={pluralUnit(remaining.d, 'day', t, locale)} />
              <Separator />
            </>
          )}
          <CountdownUnit value={remaining.h} label={pluralUnit(remaining.h, 'hour', t, locale)} />
          <Separator />
          <CountdownUnit value={remaining.m} label={pluralUnit(remaining.m, 'min', t, locale)} />
          {remaining.d === 0 && (
            <>
              <Separator />
              <CountdownUnit value={remaining.s} label={pluralUnit(remaining.s, 'sec', t, locale)} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
