import { useId } from 'react';
import { cn } from '../../lib/format';
import '../../styles/k2-brand.css';

const TONES = {
  // золото бренда: светлая грань сверху слева, тёмная внизу справа
  gold: ['#F3E4B8', '#C9A24D', '#B08A3E'],
  // для тёмного хрусталя (подвал): светлее и ярче
  light: ['#FFF3CF', '#EBCF8C', '#C9A24D'],
  // второе место
  silver: ['#F4F6FA', '#C3CBD8', '#8F9BAF'],
  // третье место
  bronze: ['#F6DDBD', '#D1A06A', '#9A6A36'],
  // лёд: парные линии сравнения
  ice: ['#EAF4FB', '#A9C8E4', '#6F94BC'],
};

/**
 * Фирменная «Грань»: ромб из четырёх граней со световым бликом. Маркер вместо тире и точек, узел разделителя,
 * буллет, индикатор «обновлено». Размеры по сетке: 6, 10, 14, 28 px (ширина). `tall` — пропорция 1:2,1 (как у буквы F).
 * Декоративна: aria-hidden, смысл несёт соседний текст.
 */
export default function FacetMark({ size = 10, tall = false, tone = 'gold', pulse = false, className, style }) {
  const uid = useId().replace(/:/g, '');
  const [c0, c1, c2] = TONES[tone] || TONES.gold;
  const w = 10;
  const h = tall ? 21 : 10;
  const cy = h / 2;
  return (
    <svg
      className={cn('fe-facet', size >= 28 && 'fe-facet--big', pulse && 'fe-facet--pulse', className)}
      style={style}
      width={size}
      height={Math.round((size * h) / w)}
      viewBox={`0 0 ${w} ${h}`}
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        <linearGradient id={`fe-fm-${uid}`} x1="0.1" y1="0" x2="0.9" y2="1">
          <stop offset="0" stopColor={c0} />
          <stop offset="0.55" stopColor={c1} />
          <stop offset="1" stopColor={c2} />
        </linearGradient>
      </defs>
      <polygon points={`5,0 10,${cy} 5,${h} 0,${cy}`} fill={`url(#fe-fm-${uid})`} />
      <polygon points={`5,0 5,${cy} 0,${cy}`} fill="#fff" fillOpacity="0.5" />
      <polygon points={`5,0 10,${cy} 5,${cy}`} fill="#fff" fillOpacity="0.14" />
      <polygon points={`0,${cy} 5,${cy} 5,${h}`} fill="#4A3812" fillOpacity="0.1" />
      <polygon points={`5,${cy} 10,${cy} 5,${h}`} fill="#4A3812" fillOpacity="0.26" />
    </svg>
  );
}

/**
 * Место в рейтинге: цифра в графитовом круге 28 px (круг 6, зона P). Прежняя гранёная медаль золото/серебро/бронза снята
 * как «игровая» (принцип владельца 2): место читается цифрой, а не цветом камня. `data-rank` оставлен для стилей.
 */
export function FacetMedal({ rank, className }) {
  return (
    <span className={cn('fe-medal', className)} data-rank={rank}>
      <span className="fe-medal__n">{rank}</span>
    </span>
  );
}
