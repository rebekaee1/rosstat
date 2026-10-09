import { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Check, Pencil, Trash2, X } from 'lucide-react';
import { useLocale, useT } from '../../i18n';
import { formatDate, cn } from '../../lib/format';
import {
  FAVORITE_KIND_ORDER, KIND_LABEL_KEY, cabinetErrorKey, savedItemHref,
} from '../../lib/cabinetItems';
import { useImportNotice } from '../../lib/useCabinet';
import { useSavedItems } from '../../lib/useSavedItems';
import Button from '../Button';
import Spinner from '../Spinner';

/** Название строки: заданное имя, иначе вид записи («Показатель без названия»), коды и ключи не показываем. */
function rowTitle(item, t) {
  const name = String(item.title || '').trim();
  if (name) return name;
  return t('c11b.row.untitled', { kind: t(KIND_LABEL_KEY[item.kind] || 'c11b.kind.indicator') });
}

function rowSubtitle(item, t, locale) {
  const sub = typeof item.payload?.subtitle === 'string' ? item.payload.subtitle.trim() : '';
  const names = Array.isArray(item.payload?.names) ? item.payload.names.filter((n) => typeof n === 'string' && n).slice(0, 6) : [];
  const first = names.length ? names.join(', ') : sub;
  const when = item.created_at ? t('c11b.row.savedOn', { date: formatDate(item.created_at, 'day', locale) }) : '';
  return [first, when].filter(Boolean).join(', ');
}

function SavedRow({ item, onRename, onRemove, t, locale }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState('');
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef(null);
  const href = savedItemHref(item);
  const title = rowTitle(item, t);
  const pending = Boolean(item.pending);

  const start = () => { setValue(item.title || ''); setError(null); setEditing(true); };
  const commit = async () => {
    const next = value.trim();
    if (!next) { setError(t('c11b.row.nameEmpty')); return; }
    if (next === (item.title || '')) { setEditing(false); return; }
    setBusy(true);
    const res = await onRename(item.id, next);
    setBusy(false);
    if (res.ok) setEditing(false); else setError(t(cabinetErrorKey(res.reason)));
  };

  const remove = async () => {
    setBusy(true);
    const res = await onRemove(item.id);
    if (!res.ok) { setBusy(false); setError(t(cabinetErrorKey(res.reason))); }
  };

  return (
    <li className={cn('c11b-row', pending && 'is-pending')} aria-busy={pending || undefined}>
      {editing ? (
        <div className="c11b-row__edit">
          <input
            ref={inputRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') { e.preventDefault(); commit(); }
              if (e.key === 'Escape') setEditing(false);
            }}
            maxLength={200}
            autoFocus
            aria-label={t('c11b.row.renameAria', { name: title })}
            aria-invalid={error ? true : undefined}
            className="fe-k8-well c11b-row__input"
          />
          <Button variant="ghost" size="sm" onClick={commit} loading={busy} className="px-2" aria-label={t('common.save')}>
            <Check size={16} aria-hidden="true" />
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setEditing(false)} disabled={busy} className="px-2" aria-label={t('common.cancel')}>
            <X size={16} aria-hidden="true" />
          </Button>
        </div>
      ) : (
        <>
          {href ? (
            <Link to={href} className="c11b-row__main">
              <span className="c11b-row__title">{title}</span>
              <span className="c11b-row__sub">{rowSubtitle(item, t, locale)}</span>
            </Link>
          ) : (
            <span className="c11b-row__main">
              <span className="c11b-row__title">{title}</span>
              <span className="c11b-row__sub">{rowSubtitle(item, t, locale)}</span>
            </span>
          )}
          <span className="c11b-row__actions">
            <button type="button" className="c11b-icon-btn" onClick={start} disabled={pending || busy} aria-label={t('c11b.row.renameAria', { name: title })} title={t('c11b.row.rename')}>
              <Pencil size={15} aria-hidden="true" />
            </button>
            <button type="button" className="c11b-icon-btn" onClick={remove} disabled={pending || busy} aria-label={t('c11b.row.removeAria', { name: title })} title={t('c11b.row.remove')}>
              <Trash2 size={15} aria-hidden="true" />
            </button>
          </span>
        </>
      )}
      <span role="alert" className="c11b-row__err empty:hidden">{error}</span>
    </li>
  );
}

function ImportNotice({ t }) {
  const { result, dismiss } = useImportNotice();
  if (!result || (!result.imported && !result.limitReached)) return null;
  return (
    <div role="status" className="c11b-note">
      <span>
        {result.imported ? t('c11b.import.done', { n: result.imported }) : ''}
        {result.limitReached ? ` ${t('c11b.import.limit')}` : ''}
      </span>
      <button type="button" className="c11b-icon-btn" onClick={dismiss} aria-label={t('common.close')}><X size={14} aria-hidden="true" /></button>
    </div>
  );
}

/**
 * Список сохранённого в кабинете.
 * `mode="favorites"`: показатели, страны, регионы, таблицы рейтингов и расчёты, по видам;
 * `mode="comparisons"`: сохранённые сравнения. Строка открывает сохранённую страницу; можно переименовать и убрать.
 */
export default function SavedList({ mode = 'favorites' }) {
  const t = useT();
  const { locale } = useLocale();
  const { items, status, pendingLocal, remove, rename, limit } = useSavedItems();

  const comparisons = mode === 'comparisons';
  const visible = items.filter((it) => (comparisons ? it.kind === 'comparison' : it.kind !== 'comparison'));

  if (status === 'idle' || (status === 'loading' && !items.length)) {
    return <div role="status" className="c11b-empty"><Spinner size={16} /> {t('common.loading')}</div>;
  }
  if (status === 'error' && !items.length) {
    return <div role="alert" className="c11b-empty">{t('c11b.err.generic')}</div>;
  }

  const head = (
    <>
      <ImportNotice t={t} />
      {pendingLocal > 0 ? <p className="c11b-hint">{t('c11b.import.pending', { n: pendingLocal })}</p> : null}
    </>
  );

  if (!visible.length) {
    return (
      <div>
        {head}
        <div className="c11b-empty">
          <p>{comparisons ? t('c11b.compare.empty') : t('c11b.saved.empty')}</p>
          <Button as={Link} to={comparisons ? '/compare' : '/'} variant="secondary" size="sm">
            {comparisons ? t('c11b.compare.emptyCta') : t('c11b.saved.emptyCta')}
          </Button>
        </div>
      </div>
    );
  }

  const groups = comparisons
    ? [{ kind: 'comparison', rows: visible }]
    : FAVORITE_KIND_ORDER.map((kind) => ({ kind, rows: visible.filter((it) => it.kind === kind) })).filter((g) => g.rows.length);

  return (
    <div>
      {head}
      {groups.map((group) => (
        <section key={group.kind} className="c11b-group" aria-label={t(`${KIND_LABEL_KEY[group.kind]}Plural`)}>
          {!comparisons ? <h3 className="c11b-group__title">{t(`${KIND_LABEL_KEY[group.kind]}Plural`)}</h3> : null}
          <ul className="c11b-list">
            {group.rows.map((item) => (
              <SavedRow key={item.id || `${item.kind}:${item.item_key}`} item={item} onRename={rename} onRemove={remove} t={t} locale={locale} />
            ))}
          </ul>
        </section>
      ))}
      {limit ? <p className="c11b-hint">{t('c11b.saved.count', { n: items.length, max: limit })}</p> : null}
    </div>
  );
}
