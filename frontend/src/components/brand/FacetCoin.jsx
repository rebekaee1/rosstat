import { useId } from 'react';
import { cn } from '../../lib/format';
import { FACET_COIN_TONES } from './brandTones';
import '../../styles/k2-brand.css';

const PALETTE = {
  gold: ['#F3E4B8', '#C9A24D', '#B08A3E', '#231B0B'],
  champagne: ['#FBF1D6', '#E3CC91', '#C2A25C', '#231B0B'],
  ice: ['#EAF4FB', '#A9C8E4', '#6F94BC', '#14213D'],
  sapphire: ['#A9BCE6', '#5A78B8', '#2F4A86', '#FFFFFF'],
  bronze: ['#F6DDBD', '#D1A06A', '#9A6A36', '#231B0B'],
  graphite: ['#7B8AA6', '#3E4C6A', '#1E2638', '#FFFFFF'],
};

/**
 * «Грань-монета» категории (K2.9): шестигранный камень 44 px с бликом и тенью, в центре символ (children — иконка).
 * tone — один из FACET_COIN_TONES или число (индекс категории по кругу).
 */
export default function FacetCoin({ tone = 'gold', size = 44, children, className }) {
  const uid = useId().replace(/:/g, '');
  const name = typeof tone === 'number' ? FACET_COIN_TONES[((tone % 6) + 6) % 6] : tone;
  const [c0, c1, c2, ink] = PALETTE[name] || PALETTE.gold;
  const hex = '22,2 39.3,12 39.3,32 22,42 4.7,32 4.7,12';
  return (
    <span className={cn('fe-coin', className)} style={{ '--fe-coin-size': `${size}px`, '--fe-coin-ink': ink }}>
      <svg width={size} height={size} viewBox="0 0 44 44" aria-hidden="true" focusable="false">
        <defs>
          <linearGradient id={`fe-co-${uid}`} x1="0.1" y1="0" x2="0.9" y2="1">
            <stop offset="0" stopColor={c0} />
            <stop offset="0.55" stopColor={c1} />
            <stop offset="1" stopColor={c2} />
          </linearGradient>
        </defs>
        <polygon points={hex} fill={`url(#fe-co-${uid})`} />
        <polygon points="22,22 22,2 4.7,12" fill="#fff" fillOpacity="0.38" />
        <polygon points="22,22 22,2 39.3,12" fill="#fff" fillOpacity="0.14" />
        <polygon points="22,22 39.3,32 22,42" fill="#2A1E08" fillOpacity="0.2" />
        <polygon points="22,22 22,42 4.7,32" fill="#2A1E08" fillOpacity="0.08" />
      </svg>
      <span className="fe-coin__icon">{children}</span>
    </span>
  );
}
