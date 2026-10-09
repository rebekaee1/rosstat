// Круг 11 (E): две ставки рядом. Вторая ставка двигается бегунком или берётся готовой («ключевая ставка ЦБ», «средняя по ипотеке»);
// видно разницу в платеже и в переплате. Сумма и срок общие, берутся из калькулятора.
import { Scale } from 'lucide-react';
import { revealStyle } from '../lib/calcUi';
import { decimalText, fitAmountText, formatRubles } from '../lib/calcFormat';
import CalcSlider from './CalcSlider';
import Chip from './Chip';
import { useT } from '../i18n';
import '../styles/calc-ui.css';

const fit = (n) => fitAmountText(formatRubles(n), n, { maxChars: 15 });
const signed = (n) => `${n > 0 ? '+' : n < 0 ? '−' : ''}${fit(Math.abs(n))}`;
const pct = (rate) => `${decimalText(rate, 1)}%`;

/** rateB: число или null (сравнение выключено); onOpen/onClose включают и выключают блок. presets: [{ id, label, rate }]. */
export default function CalcRateCompare({ rateB, onRateB, onOpen, onClose, rateA, comparison, presets = [], index = 7 }) {
  const t = useT();
  if (rateB == null) {
    return (
      <section style={revealStyle(index)} className="fe-reveal fe-c11e-cmp-open mb-6" data-block="calc-rate-compare">
        <button type="button" className="fe-c11e-cmp-open__btn fe-press" onClick={onOpen}>
          <Scale className="w-4 h-4" aria-hidden="true" />
          {t('c11e.cmp.open')}
        </button>
      </section>
    );
  }
  const { a, b } = comparison;
  const rows = [
    { key: 'payment', label: t('calc.mortgage.payment'), a: fit(a.payment), b: fit(b.payment), diff: b.payment - a.payment },
    { key: 'overpay', label: t('calc.mortgage.overpay'), a: fit(a.overpay), b: fit(b.overpay), diff: b.overpay - a.overpay },
    { key: 'total', label: t('calc.mortgage.total'), a: fit(a.total), b: fit(b.total), diff: b.total - a.total },
  ];
  return (
    <section
      style={revealStyle(index)}
      className="fe-reveal fe-panel rounded-[2rem] shadow-sm shadow-black/[0.03] p-5 md:p-6 mb-6"
      data-block="calc-rate-compare"
    >
      <div className="flex items-start justify-between gap-3 mb-1">
        <div className="flex items-center gap-2">
          <Scale className="w-4 h-4 text-champagne" aria-hidden="true" />
          <h3 className="text-base font-semibold text-text-primary">{t('c11e.cmp.title')}</h3>
        </div>
        <button type="button" className="fe-c11e-link fe-press" onClick={onClose}>{t('c11e.cmp.close')}</button>
      </div>
      <p className="text-xs text-text-secondary mb-4">{t('c11e.cmp.hint')}</p>

      <CalcSlider label={t('c11e.cmp.rateB')} value={rateB} onChange={onRateB} min={0.1} max={30} step={0.1} suffix="%" editable />
      {presets.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5" role="group" aria-label={t('c11e.cmp.presetsAria')}>
          {presets.map((preset) => (
            <Chip key={preset.id} active={Math.abs(rateB - preset.rate) < 0.05} onClick={() => onRateB(preset.rate)}>
              {`${preset.label} ${pct(preset.rate)}`}
            </Chip>
          ))}
        </div>
      )}

      <div className="fe-c11e-cmp mt-5" role="table" aria-label={t('c11e.cmp.title')} data-testid="rate-compare-table">
        <div className="fe-c11e-cmp__row fe-c11e-cmp__row--head" role="row">
          <span role="columnheader" />
          <span role="columnheader">{pct(rateA)}</span>
          <span role="columnheader">{pct(rateB)}</span>
          <span role="columnheader">{t('c11e.cmp.diff')}</span>
        </div>
        {rows.map((row) => (
          <div key={row.key} className="fe-c11e-cmp__row" role="row">
            <span role="rowheader" className="fe-c11e-cmp__label">{row.label}</span>
            <span role="cell">{row.a}</span>
            <span role="cell">{row.b}</span>
            <span role="cell" className="fe-c11e-cmp__diff">{signed(row.diff)}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
