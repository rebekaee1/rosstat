// Поле денежной суммы калькуляторов (/calculator*): подпись, видимая единица, цифровая
// клавиатура с разделителем (inputMode="decimal"), понятное сообщение при неверном вводе.
// Прошлое корректное значение остаётся в расчёте — поле больше не «молча» обнуляет результат.
import { useId, useLayoutEffect, useRef, useState } from 'react';
import { cn } from '../lib/format';
import { formatInput } from '../lib/calcFormat';
import { MONEY_MAX, formatMoneyLimit, parseMoneyInput } from '../lib/calcUi';
import { useT } from '../i18n';
import '../styles/calc-ui.css';
import '../styles/k8-tools.css';

/** Позиция курсора после перестановки пробелов: за тем же числом цифр, что стояло слева от него. */
function caretAfter(text, digitsBefore) {
  if (digitsBefore <= 0) return 0;
  let seen = 0;
  for (let i = 0; i < text.length; i += 1) {
    if (/\d/.test(text[i])) seen += 1;
    if (seen === digitsBefore) return i + 1;
  }
  return text.length;
}

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
  hint = '',
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
  const inputRef = useRef(null);
  const caretRef = useRef(null);
  // Что поле само отдало наружу: отличает «родитель сменил значение» (синхронизируем текст)
  // от «родитель принял наше значение» (текст не трогаем, чтобы не сбивать ввод).
  const [emitted, setEmitted] = useState(value);
  if (value !== emitted) {
    setEmitted(value);
    setText(formatInput(value));
    setError(null);
  }

  // Круг 11 (E): после перестановки пробелов курсор возвращается на своё место. Раньше он прыгал в конец или оставался
  // в середине старого текста, и «12000000» превращалось в «80 000 004».
  useLayoutEffect(() => {
    const position = caretRef.current;
    if (position == null) return;
    caretRef.current = null;
    const node = inputRef.current;
    if (!node || typeof document === 'undefined' || document.activeElement !== node) return;
    try { node.setSelectionRange(position, position); } catch { /* тип поля не поддерживает выделение */ }
  });

  const handleFocus = (event) => {
    // Касание выделяет всё число: новая цифра заменяет старое значение, а не вставляется в его середину.
    const node = event.target;
    window.setTimeout(() => {
      if (document.activeElement === node) {
        try { node.select(); } catch { /* поле не выделяется */ }
      }
    }, 0);
  };

  const handleChange = (event) => {
    const raw = event.target.value;
    const caret = event.target.selectionStart;
    const parsed = parseMoneyInput(raw, { max, allowZero });
    if (parsed.error) {
      setText(raw);
      // Пустое поле во время набора не ругаем: человек стирает число, чтобы ввести новое.
      setError(parsed.error === 'empty' && raw.trim() === '' ? null : parsed.error);
      return;
    }
    setError(null);
    const nextText = /[.,]/.test(raw) ? raw : formatInput(parsed.value);
    if (nextText !== raw && typeof caret === 'number') {
      caretRef.current = caretAfter(nextText, raw.slice(0, caret).replace(/\D/g, '').length);
    }
    setText(nextText);
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
          className="text-[13px] font-medium text-text-secondary"
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
          ref={inputRef}
          id={fieldId}
          type="text"
          inputMode="decimal"
          autoComplete="off"
          enterKeyHint="done"
          value={text}
          onChange={handleChange}
          onBlur={handleBlur}
          onFocus={handleFocus}
          placeholder={placeholder}
          aria-invalid={error ? 'true' : undefined}
          aria-describedby={error ? errorId : undefined}
          className={cn(
            'calc-field-input w-full rounded-2xl',
            'font-display font-bold tabular-nums text-text-primary transition-colors',
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
      {!error && hint && <p className="mt-2 text-xs leading-relaxed text-text-secondary">{hint}</p>}
    </div>
  );
}
