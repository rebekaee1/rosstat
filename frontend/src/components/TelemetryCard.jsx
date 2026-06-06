import { useEffect, useRef } from 'react';
import gsap from 'gsap';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { formatValue, formatChange, unitSuffix, unitDigits, cn } from '../lib/format';

/**
 * Карточка одного телеметрического значения на странице индикатора.
 *
 * Используется в IndicatorDetail для четырёх блоков:
 *   текущее значение, предыдущее, абсолютный максимум, среднее.
 *
 * Если задан `change` — показывает дельту с иконкой, цветом, единицей измерения.
 * Если задан `pctChange` — показывает процентное изменение вместо абсолютного.
 *
 * Анимация: при появлении карточка плывёт снизу вверх, число счётчиком
 * увеличивается до целевого значения. Уважает `prefers-reduced-motion`.
 */
export default function TelemetryCard({
  label, value, unit, change, pctChange, meta, delay = 0,
  deltaSuffix = 'к пред. месяцу',
}) {
  const ref = useRef(null);
  const valRef = useRef(null);
  const animated = useRef(false);

  useEffect(() => {
    if (animated.current || !ref.current) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    animated.current = true;
    const tween = gsap.fromTo(ref.current,
      { y: 20, opacity: 0 },
      { y: 0, opacity: 1, duration: 0.8, ease: 'power3.out', delay: 0.4 + delay * 0.1 }
    );
    return () => tween.kill();
  }, [delay]);

  const digits = unitDigits(unit);
  useEffect(() => {
    if (value == null || !valRef.current) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      valRef.current.textContent = formatValue(value, digits);
      return;
    }
    const raw = valRef.current.textContent.replace(/\s/g, '') || '0';
    const from = parseFloat(raw) || 0;
    const target = Number(value);
    const counter = { v: from };
    const tween = gsap.to(counter, {
      v: target,
      duration: from === 0 ? 1.5 : 0.6,
      ease: 'power2.out',
      delay: from === 0 ? 0.2 : 0,
      onUpdate() {
        if (valRef.current) {
          valRef.current.textContent = formatValue(counter.v, digits);
        }
      },
    });
    return () => tween.kill();
  }, [value, digits]);

  const changeNum = change != null ? Number(change) : null;
  const isUp = changeNum != null && changeNum > 0;
  const isDown = changeNum != null && changeNum < 0;

  return (
    <div ref={ref} className="group relative p-3 sm:p-6 rounded-2xl sm:rounded-[2rem] bg-surface border border-border-subtle hover:border-champagne/30 transition-colors duration-500 overflow-hidden lift-hover">
      <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-champagne/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-700" />

      <p className="text-[9px] sm:text-[10px] uppercase tracking-widest text-text-tertiary font-medium mb-2 sm:mb-4 line-clamp-2 leading-tight">
        {label}
      </p>

      <div className="flex items-baseline gap-1 sm:gap-2 mb-1 sm:mb-2 flex-wrap">
        <span ref={valRef} className={cn(
          'font-mono font-bold tracking-tight text-text-primary whitespace-nowrap',
          String(formatValue(value, unitDigits(unit))).length > 12
            ? 'text-lg sm:text-xl md:text-2xl'
            : 'text-xl sm:text-2xl md:text-3xl'
        )}>
          {formatValue(value, unitDigits(unit))}
        </span>
        <span className="text-xs font-medium text-text-tertiary shrink-0 whitespace-nowrap">{unitSuffix(unit)}</span>
      </div>

      <div className="flex flex-col gap-1 sm:gap-1.5 mt-2 sm:mt-4 pt-2 sm:pt-4 border-t border-border-subtle/50">
        {changeNum != null && (
          <div className={cn(
            'flex items-center gap-1 sm:gap-1.5 text-[10px] sm:text-xs font-mono font-medium flex-wrap',
            isUp ? 'text-positive' : '',
            isDown ? 'text-negative' : '',
            !isUp && !isDown ? 'text-text-tertiary' : ''
          )}>
            {isUp && <TrendingUp className="w-3.5 h-3.5 shrink-0" />}
            {isDown && <TrendingDown className="w-3.5 h-3.5 shrink-0" />}
            <span>{pctChange != null ? `${formatChange(pctChange)}%` : `Δ ${formatChange(changeNum)}`}</span>
            <span className="text-text-tertiary text-[9px] sm:text-[10px] uppercase tracking-wider ml-0.5 sm:ml-1">
              {deltaSuffix}
            </span>
          </div>
        )}
        {meta && (
          <div className="text-[9px] sm:text-[10px] font-mono uppercase tracking-widest text-text-tertiary leading-snug">
            {meta}
          </div>
        )}
      </div>
    </div>
  );
}
