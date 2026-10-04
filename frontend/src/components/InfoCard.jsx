// Карточка-раздел для «О проекте» и «Методологии»: иконка, короткий заголовок, 1–2 предложения.
// Всё, что нужно только экспертам, прячется в <InfoMore> («Подробнее»).
import { cn } from '../lib/format';
import '../styles/w5-pages.css';

export function InfoCard({ icon: Icon, title, id, wide = false, className, children }) {
  return (
    <section id={id} className={cn('x4-card fe-panel', wide && 'x4-card--wide', className)}>
      <div className="x4-card__head">
        {Icon && (
          <span className="x4-card__icon" aria-hidden="true">
            <Icon className="h-5 w-5" />
          </span>
        )}
        <h2 className="x4-card__title">{title}</h2>
      </div>
      <div className="x4-card__body">{children}</div>
    </section>
  );
}

export function InfoMore({ label, defaultOpen = false, children }) {
  return (
    <details className="w5-more-inline" open={defaultOpen || undefined}>
      <summary>{label}</summary>
      <div>{children}</div>
    </details>
  );
}

export function InfoGrid({ children, className }) {
  return <div className={cn('x4-cards', className)}>{children}</div>;
}
