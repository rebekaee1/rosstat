import { forwardRef } from 'react';
import { cn } from '../lib/format';
import Spinner from './Spinner';
import { useT } from '../i18n/localeContext';

/**
 * Единая кнопка. variant: primary | secondary | ghost; size: md (44 px на сенсорных, 40 px иначе) | sm.
 * `as` — любой компонент ссылки (например, Link) или 'a'; `loading` блокирует нажатие и показывает кольцо.
 * Круг 11, G: `pending` — то же состояние ожидания под названием, общим с `Chip`: кнопка тускнеет, на ней тонкое кольцо (оно проявляется
 * через 140 мс, быстрые ответы не мигают), повторное нажатие не срабатывает, `aria-busy` сообщает о состоянии. Удобно вместе с `usePending`.
 * Цвета берутся из токенов: заливка primary — глубокий синий `--fe-glass-primary` со светлым текстом (круг 6, контраст ≥ 8:1).
 * Золотая заливка — только у CTA регистрации: добавьте класс `fe-cta-gold` (одна такая кнопка на страницу).
 */
const Button = forwardRef(function Button({
  as: Tag = 'button', variant = 'primary', size = 'md', loading = false, pending = false, disabled = false,
  className, children, type, ...rest
}, ref) {
  const t = useT();
  const isNative = Tag === 'button';
  const busy = loading || pending;
  const blocked = disabled || busy;
  const extra = { ...rest };
  if (!isNative && blocked) extra.onClick = (event) => event.preventDefault();
  return (
    <Tag
      ref={ref}
      className={cn('fe-btn fe-press', `fe-btn--${variant}`, size === 'sm' && 'fe-btn--sm', className)}
      aria-busy={busy || undefined}
      aria-disabled={!isNative && blocked ? true : undefined}
      disabled={isNative ? blocked : undefined}
      type={isNative ? (type || 'button') : undefined}
      {...extra}
    >
      {busy && <Spinner size={14} className="fe-btn__spinner" />}
      {children}
      {pending && !loading ? <span className="sr-only">{t('c11g.pending')}</span> : null}
    </Tag>
  );
});

export default Button;
