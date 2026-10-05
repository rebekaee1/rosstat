// Переключатель калькуляторов: три вкладки высотой 48 px под заголовком каждого калькулятора, чтобы «Ипотечный»
// и «Сложные проценты» находились сразу, а форма оставалась на первом экране. Текущий выделен золотом.
// На телефоне подписи короткие («Инфляция», «Ипотека», «Проценты»), на компьютере полные и с пометкой, для каких стран подходит.
import { Link } from 'react-router-dom';
import { Building2, PiggyBank, Percent } from 'lucide-react';
import { cn } from '../lib/format';
import { track, events } from '../lib/track';
import { useT } from '../i18n';
import '../styles/w6-g.css';
import '../styles/z8-tools.css';
import '../styles/k8-tools.css';

const ITEMS = [
  {
    id: 'inflation', to: '/calculator', icon: Percent,
    titleKey: 'footer.calcInflation', shortKey: 'z8.calc.tab.inflation', forKey: 'w6g.calc.for.inflation',
  },
  {
    id: 'mortgage', to: '/calculator/mortgage', icon: Building2,
    titleKey: 'calc.inflation.otherMortgageTitle', shortKey: 'z8.calc.tab.mortgage', forKey: 'w6g.calc.for.mortgage',
  },
  {
    id: 'compound', to: '/calculator/compound', icon: PiggyBank,
    titleKey: 'calc.inflation.otherCompoundTitle', shortKey: 'z8.calc.tab.compound', forKey: 'w6g.calc.for.compound',
  },
];

export default function CalculatorShowcase({ current }) {
  const t = useT();
  // Золотой бегунок в жёлобе встаёт под активную вкладку (k8-tools / z8-tools: --k8-i).
  const activeIndex = Math.max(0, ITEMS.findIndex((item) => item.id === current));
  return (
    <nav data-block="calc-showcase" className="fe-z8-tabs" style={{ '--k8-i': activeIndex }} aria-label={t('w6g.calc.showcaseAria')}>
      {ITEMS.map((item) => {
        const Icon = item.icon;
        const active = item.id === current;
        return (
          <Link
            key={item.id}
            to={item.to}
            aria-current={active ? 'page' : undefined}
            aria-label={t(item.titleKey)}
            onClick={() => { if (!active) track(events.RELATED_LINK_CLICK, { from: current, to: item.id, surface: 'calc-showcase' }); }}
            className={cn('fe-z8-tab fe-press', active && 'is-active')}
          >
            <span className="fe-z8-tab__icon" aria-hidden="true"><Icon size={18} /></span>
            <span className="fe-z8-tab__text" aria-hidden="true">
              <span className="fe-z8-tab__title">
                <span className="fe-z8-tab__full">{t(item.titleKey)}</span>
                <span className="fe-z8-tab__short">{t(item.shortKey)}</span>
              </span>
              <span className="fe-z8-tab__for">{t(item.forKey)}</span>
            </span>
          </Link>
        );
      })}
    </nav>
  );
}
