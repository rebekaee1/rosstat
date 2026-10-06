import { forwardRef } from 'react';
import { cn } from '../lib/format';
import Spinner from './Spinner';

/**
 * Единая кнопка. variant: primary | secondary | ghost; size: md (44 px на сенсорных, 40 px иначе) | sm.
 * `as` — любой компонент ссылки (например, Link) или 'a'; `loading` блокирует нажатие и показывает кольцо.
 * Цвета берутся из токенов: заливка primary — глубокий синий `--fe-glass-primary` со светлым текстом (круг 6, контраст ≥ 8:1).
 * Золотая заливка — только у CTA регистрации: добавьте класс `fe-cta-gold` (одна такая кнопка на страницу).
 */
const Button = forwardRef(function Button({
  as: Tag = 'button', variant = 'primary', size = 'md', loading = false, disabled = false,
  className, children, type, ...rest
}, ref) {
  const isNative = Tag === 'button';
  const blocked = disabled || loading;
  const extra = { ...rest };
  if (!isNative && blocked) extra.onClick = (event) => event.preventDefault();
  return (
    <Tag
      ref={ref}
      className={cn('fe-btn fe-press', `fe-btn--${variant}`, size === 'sm' && 'fe-btn--sm', className)}
      aria-busy={loading || undefined}
      aria-disabled={!isNative && blocked ? true : undefined}
      disabled={isNative ? blocked : undefined}
      type={isNative ? (type || 'button') : undefined}
      {...extra}
    >
      {loading && <Spinner size={14} className="fe-btn__spinner" />}
      {children}
    </Tag>
  );
});

export default Button;
