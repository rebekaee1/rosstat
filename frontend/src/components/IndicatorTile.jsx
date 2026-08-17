import { useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import gsap from 'gsap';
import { TrendingUp, TrendingDown, ArrowRight } from 'lucide-react';
import { formatValue, formatChange, formatDate, resolveDateFormat, cn, isCpiIndex, relativeTime } from '../lib/format';
import { FOCUS_RING_SURFACE } from '../lib/uiTokens';
import { track, events } from '../lib/track';
import {
  russiaIndicatorPath,
} from '../lib/sitePaths';
import { useLocale, useT } from '../i18n';
import { findCategoryByApiLabel } from '../lib/categories';

/**
 * Listing-карточка индикатора. Используется и на главной (где это
 * `home_indicator_click`), и на /russia/category/:slug (где это `category_tile_click`).
 * `surface` различает источник клика — нужен для funnel-анализа в Метрике
 * (Webvisor показывает category→indicator как отдельную ось, без surface
 * мы потеряем контекст).
 */
export default function IndicatorTile({ indicator, delay = 0, displayOverride, surface = 'home' }) {
  const t = useT();
  const { locale } = useLocale();
  const ref = useRef(null);
  const glowRef = useRef(null);

  useEffect(() => {
    if (!ref.current) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const tween = gsap.fromTo(ref.current,
      { y: 30, opacity: 0 },
      { y: 0, opacity: 1, duration: 0.8, ease: 'power3.out', delay: 0.2 + delay * 0.1 }
    );
    return () => tween.kill();
  }, [delay]);

  const handleMouseMove = (e) => {
    if (!glowRef.current || !indicator.is_active) return;
    const rect = ref.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    glowRef.current.style.setProperty('--mouse-x', `${x}px`);
    glowRef.current.style.setProperty('--mouse-y', `${y}px`);
  };

  // Hero override от бэка: для индекс-индикаторов (ИПП, ИЦП, цены на жильё)
  // «первая цифра» карточки = изменение г/г %, а не уровень индекса. Так число
  // на карточке каталога совпадает с тем, что пользователь видит при первом
  // входе на страницу (там по умолчанию режим «год к году»).
  const hasHero = !displayOverride && indicator.hero_value != null;
  // Для индекс-карточек (hero = Г/г %) бейдж изменения = ускорение Г/г в п.п.
  // (hero_change), а не дельта уровня индекса.
  const rawChange = displayOverride ? displayOverride.change
    : hasHero ? indicator.hero_change
      : indicator.change;
  const changeNum = rawChange != null ? Number(rawChange) : null;
  const isUp = changeNum != null && changeNum > 0;
  const isDown = changeNum != null && changeNum < 0;
  const isActive = indicator.is_active;
  const displayVal = displayOverride
    ? displayOverride.value
    : hasHero
      ? indicator.hero_value
      : isCpiIndex(indicator.code)
        ? (indicator.current_value != null ? Number(indicator.current_value) - 100 : null)
        : indicator.current_value;
  const displayUnit = hasHero ? (indicator.hero_unit || '%') : indicator.unit;
  const dateFmt = resolveDateFormat({ frequency: indicator.frequency });

  const handleClick = () => {
    if (!isActive) return;
    const event = surface === 'category' ? events.CATEGORY_TILE_CLICK : events.HOME_INDICATOR_CLICK;
    track(event, {
      indicator: indicator.code,
      indicatorCategory: indicator.category,
      surface,
    });
  };

  return (
    <Link
      ref={ref}
      to={isActive ? russiaIndicatorPath(indicator.code) : '#'}
      onClick={handleClick}
      onMouseMove={handleMouseMove}
      className={cn(
        FOCUS_RING_SURFACE,
        'group relative p-4 sm:p-6 rounded-[2rem] border transition-all duration-500 overflow-hidden',
        'bg-surface border-border-subtle',
        isActive
          ? 'hover:border-champagne/40 cursor-pointer lift-hover'
          : 'opacity-40 cursor-default pointer-events-none grayscale'
      )}
    >
      {/* Dynamic Glow Effect on Hover */}
      {isActive && (
        <div
          ref={glowRef}
          className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none"
          style={{
            background: `radial-gradient(circle 300px at var(--mouse-x, 0) var(--mouse-y, 0), rgba(184, 148, 47, 0.06), transparent 80%)`,
          }}
        />
      )}

      <div className="relative z-10 flex flex-col h-full">
        <div className="flex items-center justify-between mb-5 sm:mb-8">
          <span className="text-[10px] uppercase tracking-[0.2em] font-medium text-text-tertiary">
            {(locale === 'en' ? (findCategoryByApiLabel(indicator.category_ru || indicator.category)?.nameEn) : null) || indicator.category || t('tile.metric')}
          </span>
          {!isActive && (
            <span className="text-[9px] uppercase tracking-widest px-2.5 py-1 rounded-full bg-obsidian border border-border-subtle text-text-tertiary font-medium">
              {t('tile.pending')}
            </span>
          )}
          {isActive && (
            <div className="w-8 h-8 rounded-full border border-border-subtle flex items-center justify-center bg-obsidian-light group-hover:bg-champagne/10 group-hover:border-champagne/30 transition-colors duration-300">
              <ArrowRight className="w-3.5 h-3.5 text-text-tertiary group-hover:text-champagne transition-colors" />
            </div>
          )}
        </div>

        <div className="mt-auto">
          <h3 className="text-sm font-semibold text-text-primary mb-1 group-hover:text-champagne transition-colors duration-300">
            {locale === 'en' && indicator.name_en ? indicator.name_en : indicator.name}
          </h3>
          {locale === 'en'
            ? (indicator.name && indicator.name_en && (
              <p className="text-xs text-text-tertiary mb-6 font-mono">{indicator.name}</p>
            ))
            : (indicator.name_en && (
              <p className="text-xs text-text-tertiary mb-6 font-mono">{indicator.name_en}</p>
            ))}

          <div className="flex items-end justify-between gap-x-3 gap-y-2 flex-wrap">
            <div className="min-w-0">
              <div className="flex items-baseline gap-1.5 mb-1">
                <span className={cn(
                  'font-bold tracking-tight text-text-primary font-mono whitespace-nowrap',
                  String(formatValue(displayVal)).length > 12 ? 'text-lg' : 'text-2xl'
                )}>
                  {formatValue(displayVal)}
                </span>
                <span className="text-xs font-medium text-text-tertiary whitespace-nowrap">{displayUnit}</span>
              </div>
              
              {indicator.current_date && (
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="text-[10px] uppercase tracking-widest text-text-tertiary font-mono">
                    {formatDate(indicator.current_date, dateFmt)}
                    {hasHero ? ` ${t('tile.yoy')}` : ''}
                  </p>
                  {relativeTime(indicator.current_date) && (
                    <span className="text-[9px] text-text-tertiary/60 font-mono">
                      {relativeTime(indicator.current_date)}
                    </span>
                  )}
                </div>
              )}
            </div>

            {changeNum != null && (
              <div className={cn(
                'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border font-mono text-xs font-medium shrink-0',
                isUp ? 'bg-positive/10 border-positive/20 text-positive' : '',
                isDown ? 'bg-negative/10 border-negative/20 text-negative' : '',
                !isUp && !isDown ? 'bg-obsidian border-border-subtle text-text-tertiary' : ''
              )}>
                {isUp && <TrendingUp className="w-3 h-3" />}
                {isDown && <TrendingDown className="w-3 h-3" />}
                <span>{formatChange(changeNum)}</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </Link>
  );
}
