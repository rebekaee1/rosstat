// Переключатель и подпись отметок событий на графиках (круг 11, зона C). Вертикали рисует lib/chartEventMarks.jsx.
// Список событий короткий и общий (lib/chartEvents.js). Подписи называют событие и ничего не объясняют про скачок линии.
import Chip from './Chip';
import { useT } from '../i18n';
import '../styles/c11c-charts.css';

/** Кнопка «События»; не показывается, если в окне графика событий нет. */
export function EventsChip({
  on, onToggle, count, className,
}) {
  const t = useT();
  if (!count) return null;
  return (
    <Chip
      active={on}
      onClick={onToggle}
      className={className}
      title={t('c11c.events.hint')}
      data-testid="chart-events-toggle"
    >
      {t('c11c.events.chip')}
    </Chip>
  );
}

/** Список под графиком: год и название, чтобы отметки читались и на телефоне без наведения. */
export function ChartEventsList({ marks }) {
  const t = useT();
  if (!marks?.length) return null;
  return (
    <ul className="c11c-events" data-no-export="true" data-testid="chart-events-list" aria-label={t('c11c.events.aria')}>
      {marks.map((mark) => (
        <li key={mark.id}>
          <span className="c11c-events__year">{mark.year}</span>
          <span>{t(`c11c.event.${mark.id}`)}</span>
        </li>
      ))}
    </ul>
  );
}
