// Единый слайдер денежных калькуляторов (/calculator*): подпись слева,
// значение справа, трек на всю ширину — одинаковая высота строк в грид-сетке.
// Подпись НЕ обрезается (не truncate) — на узких колонках 3-в-ряд «ПЕРВОНАЧ.
// ВЗНОС» с крупным tracking резалось до «ПЕРВ.» (созвон «На правки 13»,
// 2026-07-08); вместо обрезки — перенос на вторую строку, письменности не
// теряем.
export default function CalcSlider({ label, value, display, onChange, min, max, step = 1, suffix = '' }) {
  return (
    <div className="min-w-0">
      <div className="flex items-start justify-between gap-2 mb-2">
        <span className="text-[10px] uppercase tracking-[0.12em] font-medium text-text-tertiary leading-tight">{label}</span>
        <span className="text-sm font-mono font-bold text-text-primary tabular-nums whitespace-nowrap shrink-0">
          {display ?? `${value}${suffix}`}
        </span>
      </div>
      <input
        type="range" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        aria-label={label}
        className="calc-slider w-full"
      />
    </div>
  );
}
