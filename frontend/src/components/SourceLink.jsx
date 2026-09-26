import { Link, useInRouterContext } from 'react-router-dom';
import { trackOutbound } from '../lib/track';
import { isExternalHref } from '../lib/sourceLink';

/**
 * Ссылка на источник данных: внешний http(s) href — <a target=_blank> с
 * outbound-трекингом; иначе внутренний <Link> на fallbackTo (или на href,
 * если это внутренний путь); без обоих — просто текст.
 */
export default function SourceLink({ href, fallbackTo, className, textClassName, children, ...rest }) {
  const inRouter = useInRouterContext();
  if (isExternalHref(href)) {
    const url = href.trim();
    return (
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className={className}
        onClick={() => trackOutbound(url)}
        data-source-link="external"
        {...rest}
      >
        {children}
      </a>
    );
  }
  const to = (typeof href === 'string' && href.startsWith('/') ? href : null) || fallbackTo;
  if (to && !inRouter) {
    return (
      <a href={to} className={className} data-source-link="internal" {...rest}>
        {children}
      </a>
    );
  }
  if (to) {
    return (
      <Link to={to} className={className} data-source-link="internal" {...rest}>
        {children}
      </Link>
    );
  }
  return <span className={textClassName ?? className}>{children}</span>;
}
