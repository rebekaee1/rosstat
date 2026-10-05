// Витрина калькуляторов: три карточки с пометкой, для каких стран и валют каждый подходит.
// Стоит под заголовком каждого калькулятора, чтобы «Ипотечный» и «Сложные проценты» находились сразу,
// а не только внизу страницы. Текущий выделен.
import { Link } from 'react-router-dom';
import { Building2, PiggyBank, Percent } from 'lucide-react';
import { cn } from '../lib/format';
import { track, events } from '../lib/track';
import { useT } from '../i18n';
import '../styles/w6-g.css';

const ITEMS = [
  {
    id: 'inflation', to: '/calculator', icon: Percent,
    titleKey: 'footer.calcInflation', descKey: 'w6g.calc.show.inflation', forKey: 'w6g.calc.for.inflation',
  },
  {
    id: 'mortgage', to: '/calculator/mortgage', icon: Building2,
    titleKey: 'calc.inflation.otherMortgageTitle', descKey: 'w6g.calc.show.mortgage', forKey: 'w6g.calc.for.mortgage',
  },
  {
    id: 'compound', to: '/calculator/compound', icon: PiggyBank,
    titleKey: 'calc.inflation.otherCompoundTitle', descKey: 'w6g.calc.show.compound', forKey: 'w6g.calc.for.compound',
  },
];

export default function CalculatorShowcase({ current }) {
  const t = useT();
  return (
    <nav data-block="calc-showcase" className="fe-w6g-showcase" aria-label={t('w6g.calc.showcaseAria')}>
      {ITEMS.map((item) => {
        const Icon = item.icon;
        const active = item.id === current;
        return (
          <Link
            key={item.id}
            to={item.to}
            aria-current={active ? 'page' : undefined}
            onClick={() => { if (!active) track(events.RELATED_LINK_CLICK, { from: current, to: item.id, surface: 'calc-showcase' }); }}
            className={cn('fe-w6g-showcase__card fe-press', active && 'is-active')}
          >
            <span className="fe-w6g-showcase__icon" aria-hidden="true"><Icon size={18} /></span>
            <span className="fe-w6g-showcase__body">
              <span className="fe-w6g-showcase__title">{t(item.titleKey)}</span>
              <span className="fe-w6g-showcase__desc">{t(item.descKey)}</span>
              <span className="fe-w6g-showcase__for">{t(item.forKey)}</span>
            </span>
          </Link>
        );
      })}
    </nav>
  );
}
