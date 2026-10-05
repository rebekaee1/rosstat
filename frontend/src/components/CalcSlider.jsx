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
import '../styles/k8-tools.css';

export default function CalcSlider({
  label, ariaLabel, value, display, onChange, min, max, step = 1, suffix = '', className = '', stacked = false,
}) {
  const id = useId();
  const { locale } = useLocale();
  const numeric = locale === 'en' ? String(value) : String(value).replace('.', ',');
  const shown = display ?? `${numeric}${suffix}`;
  // Доля заполнения 0..1: жидкое золото в жёлобе доходит до бусины (k8-tools.css, --k8-r).
  const span = Number(max) - Number(min);
  const ratio = span > 0 ? Math.min(1, Math.max(0, (Number(value) - Number(min)) / span)) : 0;
  return (
    <div className={`min-w-0 ${className}`}>
      <div className={stacked ? 'mb-2 flex flex-col gap-0.5' : 'flex items-start justify-between gap-2 mb-2'}>
        <label
          htmlFor={id}
          className="text-[13px] font-medium text-text-secondary leading-tight"
        >
          {label}
        </label>
        <span className={stacked
          ? 'font-display text-2xl font-bold leading-tight text-text-primary tabular-nums whitespace-nowrap'
          : 'text-base font-sans font-bold text-text-primary tabular-nums whitespace-nowrap shrink-0 leading-tight'}
        >
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
        style={{ '--k8-r': ratio }}
      />
    </div>
  );
}
