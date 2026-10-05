import { useState, useMemo, useEffect } from 'react';
import { ChevronDown, ChevronUp, Search } from 'lucide-react';
import { formatDate, formatValue, unitSuffix, cn } from '../lib/format';
import { valueWithUnit } from '../lib/valueText';
import { track, events } from '../lib/track';
import { useT } from '../i18n';
import { tableRowMatches } from '../lib/tableSearch';
import { formatDeltaWithUnit } from '../lib/deltaText';
import { formatPercentChange, growthDigits, unitKind } from '../lib/indicatorSummary';
import { useLocale } from '../i18n';
import Button from './Button';
import Spinner from './Spinner';
import { EmptyShard } from './K5Accent';
import '../styles/chart-controls.css';
import '../styles/w6e-indicator.css';
import '../styles/z4-indicator.css';
import '../styles/k5-pages.css';

const PAGE_SIZE = 20;
// Блок появляется средствами CSS сразу, без задержки (раньше gsap скрывал таблицу на ~1.3 с).
const REVEAL_STYLE = { '--fe-duration': '0.28s', '--fe-rise': '8px' };

export default function DataTable({
  data, title, dateFormat = 'full', unit = '%', valueDigits,
  showUnitInValues = true, loading = false,
}) {
  const t = useT();
  const { locale } = useLocale();
  const resolvedTitle = title ?? t('table.historicalDefault');
  const [page, setPage] = useState(0);
  const [sortAsc, setSortAsc] = useState(false);
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');

  useEffect(() => {
    // Дебаунс нужен только для смены текста поиска. Раньше эффект срабатывал и
    // на новую ссылку `data` (родитель пересобрал массив, пришла загрузка), и
    // через 250 мс сбрасывал страницу на первую — «Вперёд» «не реагировал».
    if (searchInput === search) return undefined;
    const timer = setTimeout(() => {
      setSearch(searchInput);
      setPage(0);
      if (searchInput) {
        const results = (data || []).filter(r => tableRowMatches(r, searchInput, { dateFormat, unit, valueDigits })).length;
        track(events.TABLE_SEARCH, { query: searchInput, results });
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [searchInput, search, data, dateFormat, unit, valueDigits]);

  const filtered = useMemo(() => {
    let rows = [...(data || [])];
    if (search) {
      rows = rows.filter(r => tableRowMatches(r, search, { dateFormat, unit, valueDigits }));
    }
    rows.sort((a, b) => sortAsc
      ? new Date(a.date) - new Date(b.date)
      : new Date(b.date) - new Date(a.date)
    );
    return rows;
  }, [data, search, sortAsc, dateFormat, unit, valueDigits]);

  // Изменение к прошлому периоду и самые высокое и низкое значения считаем по всему ряду, а не по странице.
  const { changes, maxDate, minDate } = useMemo(() => {
    const asc = [...(data || [])]
      .filter((r) => r && r.date && Number.isFinite(Number(r.value)))
      .sort((a, b) => new Date(a.date) - new Date(b.date));
    const map = new Map();
    const rate = unitKind(unit) === 'rate';
    let hi = null;
    let lo = null;
    asc.forEach((row, i) => {
      const v = Number(row.value);
      if (hi == null || v > Number(hi.value)) hi = row;
      if (lo == null || v < Number(lo.value)) lo = row;
      if (i === 0) return;
      const prev = Number(asc[i - 1].value);
      if (rate) {
        const shown = formatDeltaWithUnit(v - prev, unit, { digits: valueDigits ?? 2, locale });
        map.set(row.date, shown.flat ? '0' : shown.text);
      } else if (prev > 0 && v >= 0) {
        const pct = (v / prev - 1) * 100;
        map.set(row.date, formatPercentChange(pct, locale, growthDigits(pct)) || '0');
      }
    });
    return {
      changes: map,
      maxDate: asc.length > 2 ? hi?.date : null,
      minDate: asc.length > 2 ? lo?.date : null,
    };
  }, [data, unit, valueDigits, locale]);

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  const visiblePage = Math.min(page, Math.max(0, totalPages - 1));
  const pageData = filtered.slice(visiblePage * PAGE_SIZE, (visiblePage + 1) * PAGE_SIZE);
  const tableUnit = unitSuffix(unit);
  // Длинная единица («индекс, старт = 100») не сжимает заголовок столбца до шести строк: она остаётся в подсказке и в блоке «О показателе».
  const longUnit = String(tableUnit || '').trim().length > 16;

  return (
    <div
      className="fe-reveal fe-datatable fe-histtable k5-table rounded-[1.5rem] overflow-hidden fe-glass-lite"
      style={REVEAL_STYLE}
      aria-busy={loading || undefined}
    >
      <div className="p-5 flex items-center justify-between flex-wrap gap-3">
        <h3 className="min-w-0 text-base font-semibold text-text-primary">
          {resolvedTitle}
        </h3>
        <div className="relative w-full sm:w-64">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-tertiary" />
          <input
            type="text"
            placeholder={t('w3.table.search')}
            aria-label={t('w3.table.search')}
            value={searchInput}
            onChange={e => setSearchInput(e.target.value)}
            className="w-full pl-8 pr-3 py-2 text-base sm:text-sm rounded-xl text-text-primary placeholder:text-text-tertiary focus:outline-none fe-glass-2"
          />
        </div>
      </div>

      <div className="fe-histtable__scroll overflow-x-auto scrollbar-hide">
        <table className="w-full text-sm">
          <thead>
            <tr>
              <th
                scope="col"
                aria-sort={sortAsc ? 'ascending' : 'descending'}
                className="text-left px-5 py-1 text-[13px] font-semibold text-text-secondary"
              >
                <button
                  type="button"
                  className="inline-flex min-h-[44px] items-center gap-1 hover:text-text-primary transition-colors select-none"
                  onClick={() => { const next = !sortAsc; setSortAsc(next); track(events.TABLE_SORT, { order: next ? 'asc' : 'desc' }); }}
                >
                  {t('table.date')}
                  {sortAsc ? <ChevronUp className="w-3 h-3" aria-hidden="true" /> : <ChevronDown className="w-3 h-3" aria-hidden="true" />}
                </button>
              </th>
              <th
                scope="col"
                className="fe-histtable__valhead text-right px-5 py-3 text-[13px] font-semibold text-text-secondary"
                title={tableUnit && longUnit ? t('table.valueWithUnit', { unit: tableUnit }) : undefined}
              >
                {tableUnit && !longUnit ? t('table.valueWithUnit', { unit: tableUnit }) : t('table.value')}
              </th>
              <th scope="col" className="text-right px-5 py-3 text-[13px] font-semibold text-text-secondary">
                {t('w6e.table.change')}
              </th>
            </tr>
          </thead>
          <tbody>
            {pageData.length === 0 ? (
              <tr>
                <td
                  colSpan={3}
                  role="status"
                  className="px-5 py-12 text-center text-sm text-text-secondary"
                >
                  {loading ? (
                    <span className="inline-flex items-center gap-2">
                      <Spinner size={16} />
                      {t('table.loading')}
                    </span>
                  ) : (
                    <span className="k5-empty">
                      <EmptyShard size={72} />
                      <span>{search ? t('table.emptySearch') : t('table.emptyPeriod')}</span>
                    </span>
                  )}
                </td>
              </tr>
            ) : (
              pageData.map((row) => (
                <tr
                  key={row.date}
                  className={cn(
                    'transition-colors',
                    row.date === maxDate && 'is-max',
                    row.date === minDate && 'is-min',
                  )}
                >
                  <td className="px-5 py-2.5 text-text-secondary text-sm tabular-nums">
                    {formatDate(row.date, dateFormat)}
                    {row.date === maxDate && <span className="fe-histtable__tag">{t('w6e.table.max')}</span>}
                    {row.date === minDate && <span className="fe-histtable__tag">{t('w6e.table.min')}</span>}
                  </td>
                  <td className="px-5 py-2.5 text-right text-sm font-semibold tabular-nums text-text-primary">
                    {showUnitInValues
                      ? valueWithUnit(row.value, valueDigits, unit)
                      : formatValue(row.value, valueDigits)}
                  </td>
                  <td className="fe-histtable__chg px-5 py-2.5 text-right text-sm">
                    {changes.get(row.date) ?? '\u2014'}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="p-4 flex items-center justify-between k5-seam k5-seam--top">
          <Button
            variant="secondary"
            className="fe-pager-btn"
            onClick={() => { setPage(Math.max(0, visiblePage - 1)); track(events.TABLE_PAGE, { direction: 'prev' }); }}
            disabled={loading || visiblePage === 0}
          >
            {t('table.prev')}
          </Button>
          <span className="text-sm text-text-secondary tabular-nums" aria-live="polite">
            {visiblePage + 1} / {totalPages}
          </span>
          <Button
            variant="secondary"
            className="fe-pager-btn"
            onClick={() => { setPage(Math.min(totalPages - 1, visiblePage + 1)); track(events.TABLE_PAGE, { direction: 'next' }); }}
            disabled={loading || visiblePage >= totalPages - 1}
          >
            {t('table.next')}
          </Button>
        </div>
      )}
    </div>
  );
}
