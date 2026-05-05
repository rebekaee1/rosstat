/**
 * MathFormula — лёгкие inline-математические блоки без внешних зависимостей
 * (KaTeX/MathJax не нужны для пары формул на странице).
 *
 * Поддерживает символы с верхними и нижними пределами (∏, ∑) — limits
 * выставлены в столбик через CSS, как в учебниках, а не сбоку Unicode-сабом.
 *
 * Используется в `cpiViewModeContent.js` (методология CPI/инфляции).
 */
export function ProdLimits({ from, to }) {
  return (
    <span
      className="inline-flex flex-col items-center align-middle font-mono leading-none mx-0.5"
      aria-hidden="true"
    >
      <span className="text-[8px] text-text-tertiary">{to}</span>
      <span className="text-base text-text-secondary leading-none">∏</span>
      <span className="text-[8px] text-text-tertiary">{from}</span>
    </span>
  );
}

export function Formula({ children }) {
  return (
    <span className="font-mono text-text-tertiary leading-relaxed">
      {children}
    </span>
  );
}
