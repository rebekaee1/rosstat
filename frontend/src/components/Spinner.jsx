import { cn } from '../lib/format';

/** Единое кольцо ожидания. Размер — через проп `size` (px); скринридеру сообщается `label`, если он задан. */
export default function Spinner({ size = 16, label, className }) {
  return (
    <span
      className={cn('fe-spinner', className)}
      style={{ '--fe-spinner-size': `${size}px` }}
      role={label ? 'status' : undefined}
      aria-label={label || undefined}
      aria-hidden={label ? undefined : 'true'}
    />
  );
}
