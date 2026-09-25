import { Link } from 'react-router-dom';
import { useT } from '../i18n';

const CALCULATORS = [
  {
    id: 'inflation',
    to: '/calculator',
    titleKey: 'footer.calcInflation',
    descKey: 'calc.sibling.inflationDesc',
  },
  {
    id: 'mortgage',
    to: '/calculator/mortgage',
    titleKey: 'calc.inflation.otherMortgageTitle',
    descKey: 'calc.inflation.otherMortgageDesc',
  },
  {
    id: 'compound',
    to: '/calculator/compound',
    titleKey: 'calc.inflation.otherCompoundTitle',
    descKey: 'calc.inflation.otherCompoundDesc',
  },
];

/** Соседние калькуляторы. Текущий не дублируется; анкор — имя страницы, не «калькуляторы». */
export default function CalculatorSiblings({ current }) {
  const t = useT();
  const items = CALCULATORS.filter((item) => item.id !== current);
  if (!items.length) return null;

  return (
    <section data-block="calc-siblings" className="mb-8">
      <h2 className="mb-4 text-xs font-semibold uppercase tracking-[0.2em] text-text-secondary">
        {t('calc.otherHeading')}
      </h2>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {items.map((item) => (
          <Link
            key={item.id}
            to={item.to}
            className="fe-panel group rounded-2xl border border-border-subtle bg-surface p-4 transition-colors hover:border-champagne/30"
          >
            <p className="mb-1 text-sm font-semibold text-text-primary transition-colors group-hover:text-champagne">
              {t(item.titleKey)}
            </p>
            <p className="text-[13px] text-text-secondary">{t(item.descKey)}</p>
          </Link>
        ))}
      </div>
    </section>
  );
}
