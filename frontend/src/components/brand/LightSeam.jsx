import { useId } from 'react';
import { cn } from '../../lib/format';
import FacetMark from './FacetMark';
import '../../styles/k2-brand.css';

/**
 * Разделитель «световой шов»: луч света 6–10 px высотой, затухающий к краям, в середине грань 10 px.
 * Заменяет hr, пунктиры и линии между секциями (не линия: светящаяся полоса без контура).
 *   variant="beam"  — луч на всю ширину блока (по умолчанию);
 *   variant="arrow" — «грань-стрела» 56×10: короткий штрих с гранью-наконечником, ставится под заголовок секции.
 *   tone="dark"     — для графитового и сапфирового фона (ярче).
 */
export default function LightSeam({ variant = 'beam', tone = 'light', className }) {
  const uid = useId().replace(/:/g, '');
  if (variant === 'arrow') {
    return (
      <svg
        className={cn('fe-facet-arrow', tone === 'dark' && 'fe-facet-arrow--dark', className)}
        width="56"
        height="10"
        viewBox="0 0 56 10"
        aria-hidden="true"
        focusable="false"
      >
        <defs>
          <linearGradient id={`fe-fa-${uid}`} x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor="#C9A24D" stopOpacity="0" />
            <stop offset="1" stopColor="#C9A24D" stopOpacity="0.95" />
          </linearGradient>
          <linearGradient id={`fe-fh-${uid}`} x1="0.1" y1="0" x2="0.9" y2="1">
            <stop offset="0" stopColor="#F3E4B8" />
            <stop offset="0.55" stopColor="#C9A24D" />
            <stop offset="1" stopColor="#B08A3E" />
          </linearGradient>
        </defs>
        <polygon points="0,4.4 44,3.2 44,6.8 0,5.6" fill={`url(#fe-fa-${uid})`} />
        <polygon points="50,0 56,5 50,10 44,5" fill={`url(#fe-fh-${uid})`} />
        <polygon points="50,0 50,5 44,5" fill="#fff" fillOpacity="0.5" />
        <polygon points="50,5 56,5 50,10" fill="#4A3812" fillOpacity="0.24" />
      </svg>
    );
  }
  return (
    <div className={cn('fe-seam', tone === 'dark' && 'fe-seam--dark', className)} role="presentation" aria-hidden="true">
      <FacetMark size={10} tone={tone === 'dark' ? 'light' : 'gold'} />
    </div>
  );
}
