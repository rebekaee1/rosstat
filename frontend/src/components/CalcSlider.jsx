// Единый слайдер денежных калькуляторов (/calculator*): подпись слева,
// значение справа, трек на всю ширину — одинаковая высота строк в грид-сетке.
// Подпись НЕ обрезается (не truncate) — на узких колонках 3-в-ряд «ПЕРВОНАЧ.
// ВЗНОС» с крупным tracking резалось до «ПЕРВ.» (созвон «На правки 13»,
// 2026-07-08); вместо обрезки — перенос на вторую строку, письменности не
// теряем.
// Значение — 16 px жирным с единицей измерения (suffix «%» или готовый display),
// aria-valuetext повторяет его словами; на сенсорных экранах элемент 44 px (см. styles/calc-ui.css).
import { useId } from 'react';
import { useLocale } from '../i18n';
import '../styles/calc-ui.css';

export default function CalcSlider({
  label, ariaLabel, value, display, onChange, min, max, step = 1, suffix = '', className = '',
}) {
  const id = useId();
  const { locale } = useLocale();
  const numeric = locale === 'en' ? String(value) : String(value).replace('.', ',');
  const shown = display ?? `${numeric}${suffix}`;
  return (
    <div className={`min-w-0 ${className}`}>
      <div className="flex items-start justify-between gap-2 mb-2">
        <label
          htmlFor={id}
          className="text-[11px] uppercase tracking-[0.12em] font-medium text-text-secondary leading-tight"
        >
          {label}
        </label>
        <span className="text-base font-sans font-bold text-text-primary tabular-nums whitespace-nowrap shrink-0 leading-tight">
          {shown}
        </span>
      </div>
      <input
        id={id}
        type="range" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        aria-label={ariaLabel || undefined}
        aria-valuetext={typeof shown === 'string' ? shown.replaceAll('\u00A0', ' ') : undefined}
        className="calc-slider w-full"
      />
    </div>
  );
}
