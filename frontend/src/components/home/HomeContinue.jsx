import { useContext, useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  BarChart3, Calculator, CalendarDays, Coins, GitCompare, Globe2, History, Landmark, MapPin, TrendingUp, X,
} from 'lucide-react';
import { AuthContext } from '../../context/authContext';
import { clearRecentVisited, continueItems, useRecentVisited } from '../../lib/homeContinue';
import { track, events } from '../../lib/track';
import { useT } from '../../i18n';
import '../../styles/c11d-home.css';

const KIND_ICON = {
  country: Globe2,
  indicator: TrendingUp,
  rating: BarChart3,
  compare: GitCompare,
  calculator: Calculator,
  currency: Coins,
  region: MapPin,
  russia: Landmark,
  calendar: CalendarDays,
  other: History,
};

/**
 * Круг 11 (D): «Продолжить» и «Вы смотрели» на главной для вошедшего. Первая карточка ведёт туда, где человек остановился,
 * остальные — на последние открытые страницы (до шести). Список хранится только в этом браузере (`lib/homeContinue.js`,
 * его пишет зона G); на сервер он не уходит, в аналитику попадает только вид страницы без названия и адреса.
 * До монтирования и для гостя блока нет (разметка сервера и клиента совпадают); без записей он не занимает места.
 */
export default function HomeContinue() {
  const t = useT();
  const auth = useContext(AuthContext);
  const visited = useRecentVisited(12);
  const items = useMemo(() => continueItems(visited, 6), [visited]);
  if (!auth?.isAuthed || items.length === 0) return null;
  return (
    <section data-block="home-continue" className="c11d-continue" aria-labelledby="home-continue-title">
      <header className="c11d-continue__head">
        <h2 id="home-continue-title" className="c11d-continue__title">{t('c11d.continue.title')}</h2>
        <button type="button" className="c11d-continue__clear fe-press" onClick={clearRecentVisited}>
          <X size={14} aria-hidden="true" />
          {t('c11d.continue.clear')}
        </button>
      </header>
      <ul className="c11d-continue__row" aria-label={t('c11d.continue.aria')}>
        {items.map((item, index) => {
          const Icon = KIND_ICON[item.kind] || History;
          return (
            <li key={item.path} className={index === 0 ? 'is-first' : undefined}>
              <Link
                to={item.path}
                className="c11d-continue__card fe-press"
                onClick={() => track(events.HOME_COUNTRIES_CTA, { target: 'continue', kind: item.kind })}
              >
                <span className="c11d-continue__tile" aria-hidden="true"><Icon size={18} /></span>
                <span className="c11d-continue__text">
                  <span className="c11d-continue__kind">{index === 0 ? t('c11d.continue.resume') : t(`c11d.continue.kind.${item.kind}`)}</span>
                  <span className="c11d-continue__name">{item.title}</span>
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
