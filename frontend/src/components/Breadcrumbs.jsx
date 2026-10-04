import { Link } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import { cn } from '../lib/format';
import { track, events } from '../lib/track';
import { useT } from '../i18n';
import '../styles/indicator-russia.css';

/**
 * Единый UI хлебных крошек: шеврон, кликабельны все кроме текущего.
 * `items` — [{ path, name }], последний = текущая страница.
 *
 * Обычный регистр. Шеврон держится у предыдущей крошки (не повисает один на новой строке);
 * длинное название текущей страницы обрезается многоточием по ширине строки, а не рвёт вёрстку.
 * `variant="mono"` (карточки индикаторов) — компактнее, без разрядки и капса.
 */
export default function Breadcrumbs({
  items,
  className,
  variant = 'default',
}) {
  const t = useT();
  if (!items?.length) return null;

  const compact = variant === 'mono';

  return (
    <nav
      className={cn('fe-crumbs', compact ? 'fe-crumbs--compact mb-3 md:mb-8' : 'mb-4', className)}
      aria-label={t('crumb.aria')}
    >
      <ol className="fe-crumbs__list">
        {items.map((item, index) => {
          const isLast = index === items.length - 1;
          return (
            <li
              key={`${item.path}-${item.name}-${index}`}
              className={cn('fe-crumbs__item', isLast && 'fe-crumbs__item--last')}
            >
              {isLast ? (
                <span className="fe-crumbs__current" aria-current="page" title={item.name}>
                  {item.name}
                </span>
              ) : (
                <>
                  <Link
                    to={item.path}
                    onClick={() => track(events.BREADCRUMB_CLICK, {
                      to: item.path,
                      name: item.name,
                      position: index + 1,
                    })}
                    className="fe-crumbs__link"
                    title={item.name}
                  >
                    {item.name}
                  </Link>
                  <ChevronRight className="fe-crumbs__sep" aria-hidden="true" />
                </>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
