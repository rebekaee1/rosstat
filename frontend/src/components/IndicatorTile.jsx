import { useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import gsap from 'gsap';
import { TrendingUp, TrendingDown, ArrowRight } from 'lucide-react';
import { formatValue, formatChange, formatDate, cn } from '../lib/format';
import { FOCUS_RING_SURFACE } from '../lib/uiTokens';

export default function IndicatorTile({ indicator, delay = 0 }) {
  const ref = useRef(null);
  const glowRef = useRef(null);

  useEffect(() => {
    if (!ref.current) return;
    gsap.fromTo(ref.current,
      { y: 30, opacity: 0 },
      { y: 0, opacity: 1, duration: 0.8, ease: 'power3.out', delay: 0.2 + delay * 0.1 }
    );
  }, [delay]);

  const handleMouseMove = (e) => {
    if (!glowRef.current || !indicator.is_active) return;
    const rect = ref.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    glowRef.current.style.setProperty('--mouse-x', `${x}px`);
    glowRef.current.style.setProperty('--mouse-y', `${y}px`);
  };

  const changeNum = indicator.change != null ? Number(indicator.change) : null;
  const isUp = changeNum != null && changeNum > 0;
  const isDown = changeNum != null && changeNum < 0;
  const isActive = indicator.is_active;

  return (
    <Link
      ref={ref}
      to={isActive ? `/indicator/${indicator.code}` : '#'}
      onMouseMove={handleMouseMove}
      className={cn(
        FOCUS_RING_SURFACE,
        'group relative p-6 rounded-[2rem] border transition-all duration-500 overflow-hidden',
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
        <div className="flex items-center justify-between mb-8">
          <span className="text-[10px] uppercase tracking-[0.2em] font-medium text-text-tertiary">
            {indicator.category || 'Метрика'}
          </span>
          {!isActive && (
            <span className="text-[9px] uppercase tracking-widest px-2.5 py-1 rounded-full bg-obsidian border border-border-subtle text-text-tertiary font-medium">
              Ожидается
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
            {indicator.name}
          </h3>
          {indicator.name_en && (
            <p className="text-xs text-text-tertiary mb-6 font-mono">{indicator.name_en}</p>
          )}

          <div className="flex items-end justify-between">
            <div>
              <div className="flex items-baseline gap-1.5 mb-1">
                <span className="text-3xl font-bold tracking-tight text-text-primary font-mono">
                  {formatValue(indicator.current_value)}
                </span>
                <span className="text-sm font-medium text-text-tertiary">{indicator.unit}</span>
              </div>
              
              {indicator.current_date && (
                <p className="text-[10px] uppercase tracking-widest text-text-tertiary font-mono">
                  {formatDate(indicator.current_date, 'full')}
                </p>
              )}
            </div>

            {changeNum != null && (
              <div className={cn(
                'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border font-mono text-xs font-medium',
                isUp ? 'bg-negative/10 border-negative/20 text-negative' : '',
                isDown ? 'bg-positive/10 border-positive/20 text-positive' : '',
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
