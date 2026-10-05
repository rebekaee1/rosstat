import { useId } from 'react';
import { cn } from '../../lib/format';
import { useT } from '../../i18n';
import '../../styles/k2-brand.css';

/** Осколки: один фирменный материал, четыре формы (нет данных, нет результатов, ошибка, ожидание). */
function Shard({ variant, size, uid }) {
  const g = `fe-es-g-${uid}`;
  const s = `fe-es-s-${uid}`;
  return (
    <svg className="fe-empty__shard" width={size} height={size} viewBox="0 0 120 120" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id={g} x1="0.1" y1="0" x2="0.9" y2="1">
          <stop offset="0" stopColor="#FFF8E6" />
          <stop offset="0.5" stopColor="#E9CD8E" />
          <stop offset="1" stopColor="#B08A3E" />
        </linearGradient>
        <linearGradient id={s} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#fff" stopOpacity="0.85" />
          <stop offset="1" stopColor="#fff" stopOpacity="0.1" />
        </linearGradient>
      </defs>
      <ellipse cx="60" cy="108" rx="34" ry="5" fill="#3C3018" fillOpacity="0.12" />
      {variant === 'error' ? (
        <>
          <polygon points="26,34 54,22 60,58 36,84" fill={`url(#${g})`} />
          <polygon points="26,34 54,22 46,48" fill={`url(#${s})`} />
          <polygon points="66,30 94,40 88,84 62,96 68,62" fill={`url(#${g})`} fillOpacity="0.92" />
          <polygon points="66,30 94,40 80,58" fill={`url(#${s})`} />
          <polygon points="36,84 60,58 62,96" fill="#4A3812" fillOpacity="0.18" />
        </>
      ) : (
        <>
          <polygon points="60,10 92,40 80,98 60,108 40,98 28,40" fill={`url(#${g})`} />
          <polygon points="60,10 60,64 28,40" fill={`url(#${s})`} />
          <polygon points="60,10 92,40 60,64" fill="#fff" fillOpacity="0.16" />
          <polygon points="28,40 60,64 40,98" fill="#4A3812" fillOpacity="0.1" />
          <polygon points="60,64 92,40 80,98 60,108" fill="#4A3812" fillOpacity="0.26" />
        </>
      )}
      {variant === 'no-results' ? (
        <>
          <circle cx="60" cy="58" r="15" fill="#fff" fillOpacity="0.55" />
          <circle cx="60" cy="58" r="9" fill="none" stroke="#7A5F2A" strokeOpacity="0.55" strokeWidth="3" />
          <path d="M67 66l9 9" stroke="#7A5F2A" strokeOpacity="0.55" strokeWidth="3" strokeLinecap="round" />
        </>
      ) : null}
      {variant === 'waiting' ? <polygon points="60,10 92,40 60,64" className="fe-empty__glint" fill="#fff" /> : null}
    </svg>
  );
}

const KEYS = {
  'no-data': 'k2.empty.noData',
  'no-results': 'k2.empty.noResults',
  error: 'k2.empty.error',
  waiting: 'k2.empty.waiting',
};

/**
 * Пустое состояние (K2.6): осколок 80–120 px, одна фраза и действие.
 *   variant: 'no-data' | 'no-results' | 'error' | 'waiting'.
 * Своя фраза — через `title` (если не нужна стандартная). `action` — кнопка или ссылка.
 * Ошибка объявляется как alert, ожидание — как status.
 */
export default function EmptyState({ variant = 'no-data', title, hint, action, size = 96, className }) {
  const t = useT();
  const uid = useId().replace(/:/g, '');
  const role = variant === 'error' ? 'alert' : variant === 'waiting' ? 'status' : undefined;
  return (
    <div className={cn('fe-empty', `fe-empty--${variant}`, className)} role={role}>
      <Shard variant={variant} size={Math.min(120, Math.max(80, size))} uid={uid} />
      <p className="fe-empty__title">{title ?? t(KEYS[variant] || KEYS['no-data'])}</p>
      {hint ? <p className="fe-empty__hint">{hint}</p> : null}
      {action ? <div className="fe-empty__action">{action}</div> : null}
    </div>
  );
}
