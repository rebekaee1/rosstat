// Единый слайдер денежных калькуляторов (/calculator*): подпись слева,
// значение справа, трек на всю ширину — одинаковая высота строк в грид-сетке.
// Подпись НЕ обрезается (не truncate) — на узких колонках 3-в-ряд «ПЕРВОНАЧ.
// ВЗНОС» с крупным tracking резалось до «ПЕРВ.» (созвон «На правки 13»,
// 2026-07-08); вместо обрезки — перенос на вторую строку, письменности не
// теряем.
// Значение — 16 px жирным с единицей измерения (suffix «%» или готовый display),
// aria-valuetext повторяет его словами; на сенсорных экранах элемент 44 px (см. styles/calc-ui.css).
import { useId, useState } from 'react';
import { useLocale, useT } from '../i18n';
import '../styles/calc-ui.css';
import '../styles/k8-tools.css';

/** Число знаков после запятой у шага (0,1 → 1): значение из поля округляется так же, как ходит бегунок. */
function stepDecimals(step) {
  const text = String(step);
  return text.includes('.') ? text.split('.')[1].length : 0;
}

/**
 * Круг 9 (K5): число можно ввести руками рядом с бегунком. `editable` заменяет подпись значения полем;
 * `extra` — пояснение рядом («— 1 600 000 ₽» для взноса). Вне допустимых границ значение прижимается к ним.
 */
export default function CalcSlider({
  label, ariaLabel, value, display, onChange, min, max, step = 1, suffix = '', className = '', stacked = false,
  editable = false, extra = '',
}) {
  const id = useId();
  const { locale } = useLocale();
  const t = useT();
  const [draft, setDraft] = useState(null);
  const numeric = locale === 'en' ? String(value) : String(value).replace('.', ',');
  const shown = display ?? `${numeric}${suffix}`;
  // Доля заполнения 0..1: жидкое золото в жёлобе доходит до бусины (k8-tools.css, --k8-r).
  const span = Number(max) - Number(min);
  const ratio = span > 0 ? Math.min(1, Math.max(0, (Number(value) - Number(min)) / span)) : 0;
  const decimals = stepDecimals(step);

  const parseDraft = (text) => {
    const cleaned = String(text).replace(/\s/g, '').replace(',', '.');
    if (!cleaned || !/^\d*\.?\d*$/.test(cleaned)) return null;
    const parsed = Number(cleaned);
    return Number.isFinite(parsed) ? parsed : null;
  };
  const clampToRange = (parsed) => {
    const clamped = Math.min(Number(max), Math.max(Number(min), parsed));
    return Number(clamped.toFixed(decimals));
  };
  const commit = () => {
    if (draft != null) {
      const parsed = parseDraft(draft);
      if (parsed != null) {
        const next = clampToRange(parsed);
        if (next !== value) onChange(next);
      }
    }
    setDraft(null);
  };
  const editor = editable ? (
    <span className="flex shrink-0 items-baseline gap-1.5">
      <input
        type="text"
        inputMode="decimal"
        autoComplete="off"
        enterKeyHint="done"
        value={draft ?? numeric}
        aria-label={t('c9d.slider.typeValue', { label: ariaLabel || label })}
        onFocus={(event) => event.target.select()}
        onChange={(event) => {
          setDraft(event.target.value);
          const parsed = parseDraft(event.target.value);
          if (parsed != null && parsed >= Number(min) && parsed <= Number(max)) {
            const next = Number(parsed.toFixed(decimals));
            if (next !== value) onChange(next);
          }
        }}
        onBlur={commit}
        onKeyDown={(event) => {
          if (event.key === 'Enter') event.currentTarget.blur();
          if (event.key === 'Escape') { setDraft(null); event.currentTarget.blur(); }
        }}
        className="calc-slider-input fe-k8-well rounded-xl text-right font-sans text-base font-bold tabular-nums text-text-primary"
      />
      {(suffix || extra) && (
        <span className="text-base font-bold leading-tight text-text-primary tabular-nums whitespace-nowrap">
          {suffix}
          {extra ? <span className="ml-1 text-xs font-medium text-text-secondary">{extra}</span> : null}
        </span>
      )}
    </span>
  ) : null;

  return (
    <div className={`min-w-0 ${className}`}>
      <div className={stacked ? 'mb-2 flex flex-col gap-0.5' : 'flex items-start justify-between gap-2 mb-2'}>
        <label
          htmlFor={id}
          className="text-[13px] font-medium text-text-secondary leading-tight"
        >
          {label}
        </label>
        {editor || (
          <span className={stacked
            ? 'font-display text-2xl font-bold leading-tight text-text-primary tabular-nums whitespace-nowrap'
            : 'text-base font-sans font-bold text-text-primary tabular-nums whitespace-nowrap shrink-0 leading-tight'}
          >
            {shown}
          </span>
        )}
      </div>
      <input
        id={id}
        type="range" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        aria-label={ariaLabel || undefined}
        aria-valuetext={typeof shown === 'string' ? shown.replaceAll('\u00A0', ' ') : undefined}
        className="calc-slider w-full"
        style={{ '--k8-r': ratio }}
      />
    </div>
  );
}
