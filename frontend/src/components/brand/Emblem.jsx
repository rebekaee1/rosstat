import { cn } from '../../lib/format';
import '../../styles/k2-brand.css';

/**
 * Эмблема «F-кристалл» (K2.3). Две версии одного знака:
 *   variant="vector" — перерисованный SVG (/brand/emblem-f.svg), чёткий при любом размере;
 *   variant="photo"  — растровая вырезка с прозрачностью (/brand/emblem-f-phone.webp, 856x1000, высота показа до 600 px при 2x):
 *                      большая F из холодного стекла с тонкой золотой кромкой (круг 6, зона B). Она не квадратная: `size` это высота,
 *                      ширина size x 0,74. Для крупного показа (> 600 px) использовать /brand/emblem-f-2x.webp (1300x1519).
 * spin — «вращающаяся грань»: поворот вокруг вертикальной оси 3,2 с (лоадер); при prefers-reduced-motion стоит.
 * Декоративна (alt пустой): название сайта всегда стоит рядом.
 */
export const EMBLEM_PHOTO_RATIO = 856 / 1000;

export default function Emblem({ size = 96, variant = 'vector', spin = false, eager = false, className, style }) {
  const photo = variant === 'photo';
  const src = photo ? '/brand/emblem-f-phone.webp' : '/brand/emblem-f.svg';
  const width = photo ? Math.round(size * EMBLEM_PHOTO_RATIO) : size;
  return (
    <span
      className={cn('fe-emblem', spin && 'fe-emblem--spin', className)}
      style={{ '--fe-emblem-size': `${size}px`, '--fe-emblem-w': `${width}px`, ...style }}
      aria-hidden="true"
    >
      <img
        src={src}
        width={width}
        height={size}
        alt=""
        decoding="async"
        loading={eager ? 'eager' : 'lazy'}
        draggable="false"
      />
    </span>
  );
}
