import { useId } from 'react';

/**
 * K5. Мелкие общие детали страниц показателя, сравнения и прогнозов.
 *
 * AccentTitle: золотое слово-акцент в названии показателя. Текст не меняется: последнее слово заворачивается в span
 * с золотой гравировкой (`.k5-accent`), пробелы и знаки препинания остаются на местах, поэтому textContent заголовка
 * прежний. Короткое слово (до 3 букв) и название из одного слова остаются без акцента: «в», «на» золотом выглядят
 * случайной точкой.
 *
 * EmptyShard: осколок для пустых мест (CSS/SVG-аналог EmptyState из K2, пока он не слит).
 */
const SPLIT = /^([\s\S]*\s)([^\s)\]»"'.,;:!?]{3,})([)\]»"'.,;:!?]*)$/;

export function splitAccent(text) {
  const value = String(text ?? '');
  const m = SPLIT.exec(value);
  if (!m) return null;
  return { head: m[1], word: m[2], tail: m[3] };
}

export default function AccentTitle({ text }) {
  const parts = splitAccent(text);
  if (!parts) return text ?? null;
  return (
    <>
      {parts.head}
      <span className="k5-accent">{parts.word}</span>
      {parts.tail}
    </>
  );
}

/** Три грани стекла с золотым отсветом, без контура. Декоративен (aria-hidden): смысл несёт фраза рядом. */
export function EmptyShard({ size = 64, className = '' }) {
  const gid = useId().replace(/:/g, '');
  return (
    <svg
      className={`k5-shard ${className}`.trim()}
      viewBox="0 0 64 64"
      width={size}
      height={size}
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        <linearGradient id={`${gid}-a`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#FFFFFF" stopOpacity="0.95" />
          <stop offset="1" stopColor="#E9CD8E" stopOpacity="0.55" />
        </linearGradient>
        <linearGradient id={`${gid}-b`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#F3E4B8" stopOpacity="0.9" />
          <stop offset="1" stopColor="#B08A3E" stopOpacity="0.75" />
        </linearGradient>
        <linearGradient id={`${gid}-c`} x1="1" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#CFE0F0" stopOpacity="0.85" />
          <stop offset="1" stopColor="#FFFFFF" stopOpacity="0.4" />
        </linearGradient>
      </defs>
      <path d="M32 6 L50 30 L32 40 L14 30 Z" fill={`url(#${gid}-a)`} />
      <path d="M14 30 L32 40 L26 58 L8 44 Z" fill={`url(#${gid}-b)`} />
      <path d="M50 30 L32 40 L38 58 L56 44 Z" fill={`url(#${gid}-c)`} />
      <path d="M32 6 L50 30 L32 22 Z" fill="#fff" opacity="0.5" />
    </svg>
  );
}
