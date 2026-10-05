import { Link } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import { cn } from '../lib/format';
import { track, events } from '../lib/track';
import { useT } from '../i18n';
import '../styles/indicator-russia.css';
import '../styles/w6e-indicator.css';

/**
 * Единый UI хлебных крошек: шеврон, кликабельны все кроме текущего.
 * `items` — [{ path, name }], последний = текущая страница.
 *
 * Обычный регистр. Шеврон держится у предыдущей крошки (не повисает один на новой строке);
 * длинное название текущей страницы обрезается многоточием по ширине строки, а не рвёт вёрстку.
 * `variant="mono"` (карточки индикаторов) — компактнее, без разрядки и капса.
 *
 * Пока название ещё грузится (пустая строка или «…»), вместо многоточия рисуется спокойная заглушка того же размера:
 * строка не прыгает, когда название приходит, и в навигации нет «Главная > … > …».
 */
/** Название ещё не пришло: страницы передают «…». Вместо многоточия (выглядит как баг) показываем серую полоску того же места. */
const PLACEHOLDER = '…';

function CrumbText({ name }) {
  if (name !== PLACEHOLDER) return name;
  return <span className="skeleton fe-crumbs__ph" aria-hidden="true" data-testid="crumb-placeholder" />;
}

const isPending = (name) => {
  const text = String(name ?? '').trim();
  return text === '' || text === '\u2026' || text === '...';
};

export default function Breadcrumbs({
  items,
  className,
  variant = 'default',
}) {
  const t = useT();
  if (!items?.length) return null;

  const compact = variant === 'mono';
  const pending = items.some((item) => isPending(item.name));

  return (
    <nav
      className={cn('fe-crumbs', compact ? 'fe-crumbs--compact mb-3 md:mb-8' : 'mb-4', className)}
      aria-label={t('crumb.aria')}
      aria-busy={pending ? true : undefined}
    >
      <ol className="fe-crumbs__list">
        {items.map((item, index) => {
          const isLast = index === items.length - 1;
          if (isPending(item.name)) {
            return (
              <li key={`${item.path}-pending-${index}`} className="fe-crumbs__item" aria-hidden="true">
                <span className="fe-crumbs__ghost" />
                {!isLast && <ChevronRight className="fe-crumbs__sep" aria-hidden="true" />}
              </li>
            );
          }
          return (
            <li
              key={`${item.path}-${item.name}-${index}`}
              className={cn('fe-crumbs__item', isLast && 'fe-crumbs__item--last')}
            >
              {isLast ? (
                <span className="fe-crumbs__current" aria-current="page" title={item.name === PLACEHOLDER ? undefined : item.name}>
                  <CrumbText name={item.name} />
                </span>
              ) : (
                <>
                  <Link
                    to={item.path}
                    state={{ crumbName: item.name }}
                    onClick={() => track(events.BREADCRUMB_CLICK, {
                      to: item.path,
                      name: item.name,
                      position: index + 1,
                    })}
                    className="fe-crumbs__link"
                    title={item.name === PLACEHOLDER ? undefined : item.name}
                  >
                    <CrumbText name={item.name} />
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
