import { Link } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import { cn } from '../lib/format';
import { track, events } from '../lib/track';
import { useT } from '../i18n';

/**
 * Единый UI хлебных крошек: шеврон, кликабельны все кроме текущего.
 * `items` — [{ path, name }], последний = текущая страница.
 *
 * Промежуточные узлы не truncate'ятся: на десктопе читаются целиком,
 * на узкой ширине trail переносится строкой (без ellipsis на «Россия»).
 */
export default function Breadcrumbs({
  items,
  className,
  /** denser mono style (карточки индикаторов) */
  variant = 'default',
}) {
  const t = useT();
  if (!items?.length) return null;

  const isMono = variant === 'mono';

  return (
    <nav
      className={cn(
        'flex flex-wrap items-center gap-x-1.5 gap-y-1',
        isMono
          ? 'mb-3 text-[11px] font-mono uppercase tracking-widest text-text-tertiary md:mb-8 md:text-xs md:gap-x-2'
          : 'mb-4 gap-x-2 text-xs text-text-tertiary sm:text-sm',
        className,
      )}
      aria-label={t('crumb.aria')}
    >
      {items.map((item, index) => {
        const isLast = index === items.length - 1;
        return (
          <span
            key={`${item.path}-${item.name}-${index}`}
            className="inline-flex max-w-full items-center gap-1.5 md:gap-2"
          >
            {index > 0 && (
              <ChevronRight
                className={cn(
                  'shrink-0 opacity-60',
                  isMono ? 'h-3 w-3 md:h-3.5 md:w-3.5' : 'h-3.5 w-3.5 sm:h-4 sm:w-4',
                )}
                aria-hidden
              />
            )}
            {isLast ? (
              <span
                className={cn(
                  isMono ? 'text-text-secondary' : 'font-medium text-text-primary',
                )}
                aria-current="page"
              >
                {item.name}
              </span>
            ) : (
              <Link
                to={item.path}
                onClick={() => track(events.BREADCRUMB_CLICK, {
                  to: item.path,
                  name: item.name,
                  position: index + 1,
                })}
                className="transition-colors hover:text-champagne"
              >
                {item.name}
              </Link>
            )}
          </span>
        );
      })}
    </nav>
  );
}
