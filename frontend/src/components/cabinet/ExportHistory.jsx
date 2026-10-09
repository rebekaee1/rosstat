import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ExternalLink, Trash2 } from 'lucide-react';
import { useLocale, useT } from '../../i18n';
import { formatCount, formatDate } from '../../lib/format';
import { clearExports, deleteExport, listExports } from '../../lib/cabinetApi';
import { cabinetErrorCode, cabinetErrorKey, safePath } from '../../lib/cabinetItems';
import Button from '../Button';
import Spinner from '../Spinner';

/** Название выгрузки для человека: заданное при выгрузке, иначе имя файла без расширения. Ключи и коды не показываем. */
function exportTitle(row, t) {
  const p = row.params || {};
  const named = [p.title, p.indicator_name].find((v) => typeof v === 'string' && v.trim());
  if (named) return named.trim();
  if (typeof p.filename === 'string' && p.filename.trim()) return p.filename.trim().replace(/\.(csv|xlsx)$/i, '').replace(/[_]+/g, ' ');
  return t('c11b.export.untitled');
}

function exportDetails(row, t, locale) {
  const p = row.params || {};
  const period = p.period && p.period.from && p.period.to
    ? `${formatDate(p.period.from, 'short', locale)} — ${formatDate(p.period.to, 'short', locale)}`
    : '';
  return [
    String(row.format || '').toUpperCase(),
    row.rows_count ? t('c11b.export.rows', { n: formatCount(row.rows_count, locale) }) : '',
    p.country,
    period,
    formatDate(row.created_at, 'day', locale),
  ].filter(Boolean).join(', ');
}

/**
 * История выгрузок: что, когда и в каком формате вы скачали. Хранятся только параметры, не файлы:
 * чтобы скачать снова, откройте ту же страницу кнопкой справа и нажмите «Скачать» там.
 */
export default function ExportHistory() {
  const t = useT();
  const { locale } = useLocale();
  const [state, setState] = useState({ status: 'loading', items: [] });
  const [error, setError] = useState(null);
  const [confirmClear, setConfirmClear] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    setState((s) => ({ ...s, status: 'loading' }));
    return Promise.resolve()
      .then(() => listExports({ limit: 50 }))
      .then((res) => setState({ status: 'ready', items: Array.isArray(res?.items) ? res.items : [] }))
      .catch(() => setState({ status: 'error', items: [] }));
  }, []);

  useEffect(() => { load(); }, [load]);

  const remove = async (id) => {
    setError(null);
    const before = state.items;
    setState((s) => ({ ...s, items: s.items.filter((r) => r.id !== id) }));
    try {
      await deleteExport(id);
    } catch (err) {
      if (cabinetErrorCode(err) !== 'not_found') {
        setState((s) => ({ ...s, items: before }));
        setError(t(cabinetErrorKey(cabinetErrorCode(err))));
      }
    }
  };

  const clearAll = async () => {
    setBusy(true); setError(null);
    try {
      await clearExports();
      setState({ status: 'ready', items: [] });
      setConfirmClear(false);
    } catch (err) {
      setError(t(cabinetErrorKey(cabinetErrorCode(err))));
    } finally {
      setBusy(false);
    }
  };

  if (state.status === 'loading' && !state.items.length) {
    return <div role="status" className="c11b-empty"><Spinner size={16} /> {t('common.loading')}</div>;
  }
  if (state.status === 'error') {
    return (
      <div role="alert" className="c11b-empty">
        <p>{t('c11b.err.generic')}</p>
        <Button variant="secondary" size="sm" onClick={load}>{t('common.retry')}</Button>
      </div>
    );
  }
  if (!state.items.length) {
    return (
      <div className="c11b-empty">
        <p>{t('c11b.export.empty')}</p>
        <Button as={Link} to="/" variant="secondary" size="sm">{t('c11b.saved.emptyCta')}</Button>
      </div>
    );
  }

  return (
    <div>
      <p className="c11b-hint">{t('c11b.export.intro')}</p>
      <ul className="c11b-list">
        {state.items.map((row) => {
          const href = safePath(row.params?.href);
          const title = exportTitle(row, t);
          return (
            <li key={row.id} className="c11b-row">
              <span className="c11b-row__main">
                <span className="c11b-row__title">{title}</span>
                <span className="c11b-row__sub">{exportDetails(row, t, locale)}</span>
              </span>
              <span className="c11b-row__actions">
                {href ? (
                  <Link to={href} className="c11b-icon-btn" aria-label={t('c11b.export.openAria', { name: title })} title={t('c11b.export.open')}>
                    <ExternalLink size={15} aria-hidden="true" />
                  </Link>
                ) : null}
                <button type="button" className="c11b-icon-btn" onClick={() => remove(row.id)} aria-label={t('c11b.export.removeAria', { name: title })} title={t('c11b.row.remove')}>
                  <Trash2 size={15} aria-hidden="true" />
                </button>
              </span>
            </li>
          );
        })}
      </ul>
      <div className="c11b-foot">
        {confirmClear ? (
          <>
            <span className="c11b-hint">{t('c11b.export.clearAsk')}</span>
            <Button variant="secondary" size="sm" onClick={clearAll} loading={busy} className="text-negative!">{t('c11b.export.clearYes')}</Button>
            <Button variant="ghost" size="sm" onClick={() => setConfirmClear(false)} disabled={busy}>{t('common.cancel')}</Button>
          </>
        ) : (
          <Button variant="ghost" size="sm" onClick={() => setConfirmClear(true)}>{t('c11b.export.clear')}</Button>
        )}
      </div>
      <p role="alert" className="c11b-row__err empty:hidden">{error}</p>
    </div>
  );
}
