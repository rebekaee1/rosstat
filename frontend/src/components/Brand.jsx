import { useId } from 'react';
import { cn } from '../lib/format';
import '../styles/k2-brand.css';

/**
 * The approved wordmark; decorative SVG, accessible name supplied by its link.
 * Знак остаётся плоским (читаемость), но раз в 12 с по золотому квадрату проходит блик (K2.3): прямоугольник
 * со смещением, обрезанный по квадрату; анимируется только transform, при prefers-reduced-motion стоит.
 */
export default function Brand({ className, compact = false }) {
  const uid = useId().replace(/:/g, '');
  return (
    <span className={cn('fe-brand', compact && 'fe-brand-compact', className)}>
      <svg viewBox="0 0 40 44" aria-hidden="true" focusable="false">
        <defs>
          <clipPath id={`fe-bg-${uid}`}><path d="M29 30H35V38H29Z" /></clipPath>
          <linearGradient id={`fe-bl-${uid}`} x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor="#fff" stopOpacity="0" />
            <stop offset="0.5" stopColor="#fff" stopOpacity="0.95" />
            <stop offset="1" stopColor="#fff" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d="M8 38V17Q8 5 21 5H34V13H22Q17 13 17 19V20H31V28H17V38Z" fill="currentColor" />
        <path d="M29 30H35V38H29Z" fill="var(--color-champagne)" />
        <g clipPath={`url(#fe-bg-${uid})`}>
          <rect className="fe-brand-glint" x="26" y="28" width="5" height="12" fill={`url(#fe-bl-${uid})`} />
        </g>
      </svg>
      <span className="fe-brand-wordmark">
        forecast<span className="fe-brand-light">economy</span>
        <small>ECONOMIC INTELLIGENCE</small>
      </span>
    </span>
  );
}
