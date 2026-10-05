// Две карточки под первым экраном главной: калькулятор «Сколько стоили бы ваши деньги…» и курсы валют.
// Без заголовка и без большого блока «Инструменты»: он снят с главной ранее по решению владельца,
// здесь только два живых входа с готовым примером.
import { Link } from 'react-router-dom';
import { Coins, Percent } from 'lucide-react';
import { track, events } from '../../lib/track';
import { useT } from '../../i18n';
import '../../styles/w6-g.css';

const CARDS = [
  { id: 'calculator', to: '/calculator', icon: Percent, titleKey: 'w6g.home.calc.title', textKey: 'w6g.home.calc.text' },
  { id: 'currencies', to: '/currencies', icon: Coins, titleKey: 'w6g.home.cur.title', textKey: 'w6g.home.cur.text' },
];

export default function HomeTools() {
  const t = useT();
  return (
    <section data-block="home-tools" className="fe-w6g-home-tools" aria-label={t('w6g.home.toolsAria')}>
      <div className="fe-w6g-home-tools__grid">
        {CARDS.map((card) => {
          const Icon = card.icon;
          return (
            <Link
              key={card.id}
              to={card.to}
              className="fe-panel fe-press fe-w6g-home-tools__card"
              onClick={() => track(events.HOME_CATEGORY_CLICK, { category: card.id, surface: 'home-tools' })}
            >
              <span className="fe-w6g-showcase__icon" aria-hidden="true"><Icon size={18} /></span>
              <span className="fe-w6g-showcase__body">
                <span className="fe-w6g-showcase__title">{t(card.titleKey)}</span>
                <span className="fe-w6g-showcase__desc">{t(card.textKey)}</span>
              </span>
            </Link>
          );
        })}
      </div>
    </section>
  );
}
