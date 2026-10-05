import { cn } from '../../lib/format';
import '../../styles/k2-brand.css';

/**
 * Эмблема «F-кристалл» (K2.3). Две версии одного знака:
 *   variant="vector" — перерисованный SVG (/brand/emblem-f.svg), чёткий при любом размере;
 *   variant="photo"  — растровая вырезка с прозрачностью (/brand/emblem-f.webp, 512 px): стеклянные грани, золотая кромка.
 * spin — «вращающаяся грань»: поворот вокруг вертикальной оси 3,2 с (лоадер); при prefers-reduced-motion стоит.
 * Декоративна (alt пустой): название сайта всегда стоит рядом.
 */
export default function Emblem({ size = 96, variant = 'vector', spin = false, eager = false, className, style }) {
  const src = variant === 'photo' ? '/brand/emblem-f.webp' : '/brand/emblem-f.svg';
  return (
    <span
      className={cn('fe-emblem', spin && 'fe-emblem--spin', className)}
      style={{ '--fe-emblem-size': `${size}px`, ...style }}
      aria-hidden="true"
    >
      <img
        src={src}
        width={size}
        height={size}
        alt=""
        decoding="async"
        loading={eager ? 'eager' : 'lazy'}
        draggable="false"
      />
    </span>
  );
}
