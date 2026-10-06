import { useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { BarChart3, Ellipsis, GitCompare, Globe2, TrendingUp } from 'lucide-react';
import { cn } from '../lib/format';
import { useT } from '../i18n';
import { FORECASTS_TO, OPEN_NAV_MENU_EVENT, WORLD_RATING_TO, resolveActiveNavId } from '../lib/navItems';
import { comparePath } from '../lib/sitePaths';
import { useScrollDirection } from '../lib/useScrollDirection';
import { useFooterTone } from '../lib/useFooterTone';
import '../styles/k3-shell.css';

const ITEMS = [
  { id: 'countries', to: '/#countries', labelKey: 'w6b.nav.countriesShort', icon: Globe2 },
  { id: 'world-rating', to: WORLD_RATING_TO, labelKey: 'w6b.nav.ratingShort', icon: BarChart3 },
  { id: 'compare', to: comparePath(), labelKey: 'nav.compare', icon: GitCompare },
  { id: 'forecasts', to: FORECASTS_TO, labelKey: 'w6b.nav.forecasts', icon: TrendingUp },
];

/**
 * Нижняя док-панель телефона: пять главных разделов под большим пальцем (графитовое стекло, капсула 64 px).
 * Появляется после первой прокрутки, прячется, пока страница едет вниз, и возвращается при движении вверх или остановке.
 * Только на телефоне (до 768 px, CSS); на /admin/* не показывается. Резерв места под ней задаёт `--fe-dock-h`
 * на корне документа (подвал и cookie-значок читают её), пока панель на экране.
 */
export default function MobileDock() {
  const t = useT();
  const { pathname, hash } = useLocation();
  const { deep, dir, idle } = useScrollDirection();
  const hidden = pathname.startsWith('/admin');
  const overFooter = useFooterTone().dock;
  const visible = !hidden && deep && (dir === 'up' || idle);
  const activeId = pathname === '/' && hash === '#countries' ? 'countries' : resolveActiveNavId(pathname);

  // --fe-dock-reserve: место под панелью, пока она смонтирована (main и подвал на телефоне добавляют его к нижнему отступу);
  // --fe-dock-h: сколько занимает панель сейчас (0, пока спрятана); data-fe-dock: признак «панель на экране» для CSS.
  useEffect(() => {
    if (hidden) return undefined;
    const root = document.documentElement;
    root.style.setProperty('--fe-dock-reserve', '76px');
    return () => root.style.removeProperty('--fe-dock-reserve');
  }, [hidden]);
  useEffect(() => {
    if (hidden) return undefined;
    const root = document.documentElement;
    root.style.setProperty('--fe-dock-h', visible ? '76px' : '0px');
    if (visible) root.dataset.feDock = 'visible';
    else delete root.dataset.feDock;
    return () => {
      root.style.removeProperty('--fe-dock-h');
      delete root.dataset.feDock;
    };
  }, [visible, hidden]);

  if (hidden) return null;

  return (
    <nav
      className="fe-dock"
      data-visible={visible ? 'true' : 'false'}
      data-tone={overFooter ? 'dark' : undefined}
      aria-label={t('k3.dock.aria')}
    >
      <ul className="fe-dock__list">
        {ITEMS.map(({ id, to, labelKey, icon: Icon }) => {
          const active = activeId === id;
          return (
            <li key={id} className="fe-dock__cell">
              <Link
                to={to}
                className={cn('fe-dock__item', active && 'is-active')}
                aria-current={active ? 'page' : undefined}
                tabIndex={visible ? undefined : -1}
              >
                <span className="fe-dock__icon" aria-hidden="true"><Icon strokeWidth={1.5} /></span>
                <span className="fe-dock__label">{t(labelKey)}</span>
              </Link>
            </li>
          );
        })}
        <li className="fe-dock__cell">
          <button
            type="button"
            className="fe-dock__item"
            aria-haspopup="dialog"
            tabIndex={visible ? undefined : -1}
            onClick={() => window.dispatchEvent(new CustomEvent(OPEN_NAV_MENU_EVENT))}
          >
            <span className="fe-dock__icon" aria-hidden="true"><Ellipsis strokeWidth={1.5} /></span>
            <span className="fe-dock__label">{t('k3.dock.more')}</span>
          </button>
        </li>
      </ul>
    </nav>
  );
}
