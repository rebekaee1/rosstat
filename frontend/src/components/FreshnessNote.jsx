// Блок «Актуальные данные» на странице устаревшего ряда (круг 13, D2): значок «Устарело» говорит, что ряд отстал, а блок
// объясняет почему и показывает, где смотреть свежее. Поле `freshness` приходит от сервера (мир: indicator.freshness,
// Россия: freshness у показателя). Сервер сам решает, устарел ли ряд: у свежих рядов поля нет, и блок ничего не рисует.
// Причина и ближайший показатель — готовые строки на языке запроса; жаргона источников и кодов наборов в них нет.
import { Link } from 'react-router-dom';
import { ArrowUpRight } from 'lucide-react';
import { formatDate } from '../lib/format';
import { glueDate } from '../lib/periodPhrase';
import { freshnessDateFormat } from '../lib/dataFreshness';
import { useLocale, useT } from '../i18n';
import '../styles/c13d-fresh-note.css';

const REASONS = new Set(['source_stopped', 'series_lag', 'update_delayed', 'retired']);

/** Первая фраза блока: причина. Старый ответ сервера без `lead` отдаёт всё сообщение целиком. */
function leadOf(freshness, hasLink) {
  const lead = typeof freshness.lead === 'string' ? freshness.lead.trim() : '';
  if (lead) return lead;
  const message = typeof freshness.message === 'string' ? freshness.message.trim() : '';
  if (!message) return '';
  if (!hasLink) return message;
  // Ссылка рисуется отдельным элементом, поэтому предложение про «ближайший показатель» из общей строки убираем.
  return message.replace(/\s*(Ближайший актуальный показатель|The closest up-to-date measure):.*$/s, '').trim();
}

export default function FreshnessNote({ freshness, className = '' }) {
  const t = useT();
  const { locale } = useLocale();
  if (!freshness || freshness.level !== 'stale') return null;
  const nearest = freshness.nearest && freshness.nearest.url && freshness.nearest.name ? freshness.nearest : null;
  const lead = leadOf(freshness, Boolean(nearest));
  if (!lead && !nearest) return null;
  const reason = REASONS.has(freshness.reason) ? freshness.reason : 'source_stopped';
  const nearestDate = nearest?.last_period
    ? glueDate(formatDate(nearest.last_period, freshnessDateFormat(nearest.frequency), locale))
    : null;
  const checked = freshness.source_updated_at
    ? glueDate(formatDate(freshness.source_updated_at, 'day', locale))
    : null;
  return (
    <section
      className={`c13d-note rounded-3xl fe-glass-lite${className ? ` ${className}` : ''}`}
      aria-labelledby="c13d-note-title"
      data-testid="freshness-note"
      data-reason={reason}
    >
      <span className="c13d-note__mark" aria-hidden="true" />
      <div className="c13d-note__body">
        <h2 id="c13d-note-title" className="c13d-note__title">{t('c13d.note.title')}</h2>
        {lead ? <p className="c13d-note__lead" data-testid="freshness-note-lead">{lead}</p> : null}
        {checked ? <p className="c13d-note__meta">{t('c13d.note.checked', { date: checked })}</p> : null}
      </div>
      {nearest ? (
        <Link to={nearest.url} className="c13d-note__link fe-press" data-testid="freshness-note-link">
          <span className="c13d-note__link-label">{t('c13d.note.nearest')}</span>
          <span className="c13d-note__link-name">{nearest.name}</span>
          {nearestDate ? <span className="c13d-note__link-date">{t('c13d.note.until', { date: nearestDate })}</span> : null}
          <ArrowUpRight size={14} aria-hidden="true" className="c13d-note__link-arrow" />
        </Link>
      ) : null}
    </section>
  );
}
