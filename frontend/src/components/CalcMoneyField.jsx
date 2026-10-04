// Поле денежной суммы калькуляторов (/calculator*): подпись, видимая единица, цифровая
// клавиатура с разделителем (inputMode="decimal"), понятное сообщение при неверном вводе.
// Прошлое корректное значение остаётся в расчёте — поле больше не «молча» обнуляет результат.
import { useId, useState } from 'react';
import { cn } from '../lib/format';
import { FOCUS_RING_SURFACE } from '../lib/uiTokens';
import { formatInput } from '../lib/calcFormat';
import { MONEY_MAX, formatMoneyLimit, parseMoneyInput } from '../lib/calcUi';
import { useT } from '../i18n';
import '../styles/calc-ui.css';

const ERROR_KEYS = {
  chars: 'calc.ui.errChars',
  empty: 'calc.ui.errEmpty',
  max: 'calc.ui.errMax',
};

export default function CalcMoneyField({
  id,
  label,
  value,
  onChange,
  prefix = '',
  suffix = '',
  unitName = '',
  placeholder = '',
  size = 'lg',
  max = MONEY_MAX,
  allowZero = false,
  labelAddon = null,
  hideLabel = false,
  className,
  inputClassName,
}) {
  const t = useT();
  const autoId = useId();
  const fieldId = id || `money-${autoId.replaceAll(':', '')}`;
  const errorId = `${fieldId}-error`;
  const [text, setText] = useState(() => (value || allowZero ? formatInput(value) : ''));
  const [error, setError] = useState(null);
  // Что поле само отдало наружу: отличает «родитель сменил значение» (синхронизируем текст)
  // от «родитель принял наше значение» (текст не трогаем, чтобы не сбивать ввод).
  const [emitted, setEmitted] = useState(value);
  if (value !== emitted) {
    setEmitted(value);
    setText(formatInput(value));
    setError(null);
  }

  const handleChange = (event) => {
    const raw = event.target.value;
    const parsed = parseMoneyInput(raw, { max, allowZero });
    if (parsed.error) {
      setText(raw);
      // Пустое поле во время набора не ругаем: человек стирает число, чтобы ввести новое.
      setError(parsed.error === 'empty' && raw.trim() === '' ? null : parsed.error);
      return;
    }
    setError(null);
    setText(/[.,]/.test(raw) ? raw : formatInput(parsed.value));
    if (parsed.value !== value) {
      setEmitted(parsed.value);
      onChange(parsed.value);
    }
  };

  const handleBlur = () => {
    const parsed = parseMoneyInput(text, { max, allowZero });
    if (parsed.error) { setError(parsed.error); return; }
    setError(null);
    setText(formatInput(parsed.value));
  };

  const big = size === 'lg';
  const message = error
    ? t(ERROR_KEYS[error], { max: formatMoneyLimit(max) })
    : '';

  return (
    <div className={className}>
      <div className={cn('flex items-center justify-between gap-3', hideLabel ? 'sr-only' : 'mb-2')}>
        <label
          htmlFor={fieldId}
          className="text-[11px] uppercase tracking-[0.16em] font-medium text-text-secondary"
        >
          {label}
          {unitName && <span className="sr-only">, {unitName}</span>}
        </label>
        {labelAddon}
      </div>
      <div className="relative">
        {prefix && (
          <span
            className={cn(
              'pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 font-display text-text-secondary',
              big ? 'text-xl' : 'text-lg',
            )}
            aria-hidden="true"
          >
            {prefix}
          </span>
        )}
        <input
          id={fieldId}
          type="text"
          inputMode="decimal"
          autoComplete="off"
          enterKeyHint="done"
          value={text}
          onChange={handleChange}
          onBlur={handleBlur}
          placeholder={placeholder}
          aria-invalid={error ? 'true' : undefined}
          aria-describedby={error ? errorId : undefined}
          className={cn(
            FOCUS_RING_SURFACE,
            'calc-field-input w-full rounded-2xl border border-border-subtle bg-obsidian',
            'font-display font-bold tabular-nums text-text-primary transition-colors hover:border-champagne/20',
            'placeholder:font-normal placeholder:text-text-tertiary/60',
            big ? 'py-4 text-2xl md:text-3xl' : 'py-3 text-xl',
            prefix ? (big ? 'pl-10' : 'pl-9') : 'pl-4',
            suffix ? 'pr-24' : 'pr-4',
            inputClassName,
          )}
        />
        {suffix && (
          <span
            className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-xs font-medium text-text-secondary"
            aria-hidden="true"
          >
            {suffix}
          </span>
        )}
      </div>
      {error && (
        <p id={errorId} role="alert" className="mt-2 text-xs leading-relaxed text-negative">
          {message}
        </p>
      )}
    </div>
  );
}
