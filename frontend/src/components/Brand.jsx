import { useId } from 'react';
import { cn } from '../lib/format';
import '../styles/k2-brand.css';

const F_PATH = 'M8 38V17Q8 5 21 5H34V13H22Q17 13 17 19V20H31V28H17V38Z';
const GEM = 'M29 30H35V38H29Z';

/**
 * The approved wordmark; decorative SVG, accessible name supplied by its link.
 * Знак объёмный, как кристалл-грань (круг 4): буква F на своём цвете (читаемость не страдает) с тонким внутренним
 * градиентом, световой гранью по верхнему и левому краю, тёмной нижней кромкой; золотой квадрат — гранёный камень
 * (четыре грани, блик сверху) с бликом, который раз в 12 с проходит по нему (transform, при prefers-reduced-motion стоит).
 * Мягкую цветную тень-парение даёт CSS (.fe-brand svg, k2-brand.css). Размеры, aria и надпись не менялись.
 */
export default function Brand({ className, compact = false }) {
  const uid = useId().replace(/:/g, '');
  return (
    <span className={cn('fe-brand', compact && 'fe-brand-compact', className)}>
      <svg viewBox="0 0 40 44" aria-hidden="true" focusable="false">
        <defs>
          <clipPath id={`fe-bg-${uid}`}><path d={GEM} /></clipPath>
          <linearGradient id={`fe-bl-${uid}`} x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor="#fff" stopOpacity="0" />
            <stop offset="0.5" stopColor="#fff" stopOpacity="0.95" />
            <stop offset="1" stopColor="#fff" stopOpacity="0" />
          </linearGradient>
          <linearGradient id={`fe-bv-${uid}`} x1="0.1" y1="0" x2="0.9" y2="1">
            <stop offset="0" stopColor="#fff" stopOpacity="0.26" />
            <stop offset="0.5" stopColor="#fff" stopOpacity="0" />
            <stop offset="1" stopColor="#000" stopOpacity="0.22" />
          </linearGradient>
          <linearGradient id={`fe-bg2-${uid}`} x1="0.1" y1="0" x2="0.9" y2="1">
            <stop offset="0" stopColor="#F3E4B8" />
            <stop offset="0.55" stopColor="#C9A24D" />
            <stop offset="1" stopColor="#9C772B" />
          </linearGradient>
        </defs>
        <path d={F_PATH} fill="currentColor" />
        <path className="fe-brand-vol" d={F_PATH} fill={`url(#fe-bv-${uid})`} />
        <path className="fe-brand-top" d="M8 17Q8 5 21 5H34L32.3 7.3H21.3Q10.3 7.3 10.3 17.3V38H8Z" fill="#fff" fillOpacity="0.32" />
        <path className="fe-brand-top" d="M17 20H31L29.5 22H17Z" fill="#fff" fillOpacity="0.3" />
        <path className="fe-brand-edge" d="M8 38H17V36.2H10Z" fill="#000" fillOpacity="0.22" />
        <path d={GEM} fill={`url(#fe-bg2-${uid})`} />
        <path d="M29 30H35L32 34Z" fill="#fff" fillOpacity="0.7" />
        <path d="M29 30L32 34L29 38Z" fill="#fff" fillOpacity="0.25" />
        <path d="M35 30L32 34L35 38Z" fill="#4A3812" fillOpacity="0.3" />
        <path d="M29 38L32 34L35 38Z" fill="#4A3812" fillOpacity="0.14" />
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
