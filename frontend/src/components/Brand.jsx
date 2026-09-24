import { cn } from '../lib/format';

/** The approved wordmark; decorative SVG, accessible name supplied by its link. */
export default function Brand({ className, compact = false }) {
  return (
    <span className={cn('fe-brand', compact && 'fe-brand-compact', className)}>
      <svg viewBox="0 0 40 44" aria-hidden="true" focusable="false">
        <path d="M8 38V17Q8 5 21 5H34V13H22Q17 13 17 19V20H31V28H17V38Z" fill="currentColor" />
        <path d="M29 30H35V38H29Z" fill="var(--color-champagne)" />
      </svg>
      <span className="fe-brand-wordmark">
        forecast<span className="fe-brand-light">economy</span>
        <small>ECONOMIC INTELLIGENCE</small>
      </span>
    </span>
  );
}
