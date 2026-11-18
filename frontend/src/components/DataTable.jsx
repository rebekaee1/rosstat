import {
  useState, useMemo, useEffect, useRef, useCallback,
} from 'react';
import {
  ChevronDown, ChevronLeft, ChevronRight, ChevronUp, Search,
} from 'lucide-react';
import { formatDate, formatValue, unitSuffix, cn } from '../lib/format';
import { valueWithUnit } from '../lib/valueText';
import { track, events } from '../lib/track';
import { useT } from '../i18n';
import { tableRowMatches } from '../lib/tableSearch';
import { formatDeltaNumber } from '../lib/deltaText';
import {
  growthDigits, isPercentChangeUnit, unitKind,
} from '../lib/indicatorSummary';
import { medianStepDays } from '../lib/chartEvents';
import {
  currentJumpValue, nearestRow, onPeriodPick, periodJumpOptions,
} from '../lib/periodJump';
import { downloadGrid, safeFilename } from '../lib/gridExport';
import { useLocale } from '../i18n';
import Button from './Button';
import Chip from './Chip';
import Spinner from './Spinner';
import ChartDownloadMenu from './ChartDownloadMenu';
import { EmptyShard } from './K5Accent';
import '../styles/chart-controls.css';
import '../styles/w6e-indicator.css';
import '../styles/z4-indicator.css';
import '../styles/k5-pages.css';
import '../styles/c11c-charts.css';
import { flatUnit } from '../lib/countryFlag';

const PAGE_SIZE = 20;
// Блок появляется средствами CSS сразу, без задержки (раньше gsap скрывал таблицу на ~1.3 с).
const REVEAL_STYLE = { '--fe-duration': '0.28s', '--fe-rise': '8px' };

/** Есть ли справа то, что не поместилось: тогда у края рисуется затухание (подсказка «можно прокрутить»). */
function useScrollMore(ref, deps) {
  const [more, setMore] = useState(false);
  const check = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    setMore(el.scrollWidth - el.clientWidth - el.scrollLeft > 2);
  }, [ref]);
  useEffect(() => {
    check();
    const el = ref.current;
    if (!el) return undefined;
    el.addEventListener('scroll', check, { passive: true });
    window.addEventListener('resize', check);
    return () => {
      el.removeEventListener('scroll', check);
      window.removeEventListener('resize', check);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [check, ...deps]);
  return more;
}

export default function DataTable({
  data, title, dateFormat = 'full', unit = '%', valueDigits,
  showUnitInValues = true, loading = false, exportMeta = null, pageSize = PAGE_SIZE,
}) {
  const t = useT();
  const { locale } = useLocale();
  const resolvedTitle = title ?? t('table.historicalDefault');
  const [page, setPage] = useState(0);
  const [sortAsc, setSortAsc] = useState(false);
  // null — выбор не сделан: ступенчатый ряд (ставка «14,00» каждый день) по умолчанию показывает только дни перемен.
  const [onlyChangesChoice, setOnlyChangesChoice] = useState(null);
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  // Диапазон «от / до» (круг 11): строки таблицы и «Скачать этот диапазон» берут одни и те же границы.
  const [rangeFrom, setRangeFrom] = useState('');
  const [rangeTo, setRangeTo] = useState('');
  const scrollRef = useRef(null);
  // Строка, к которой перешли (год из списка или точка на графике): подсвечена, пока не выбрана другая.
  const [pickedDate, setPickedDate] = useState(null);

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

  // Даты, на которые значение изменилось (и первая точка): остальные строки повторяют предыдущую.
  const { changedDates, repeats } = useMemo(() => {
    const asc = [...(data || [])]
      .filter((r) => r && r.date)
      .sort((a, b) => new Date(a.date) - new Date(b.date));
    const set = new Set();
    let prev = null;
    asc.forEach((row, i) => {
      const v = Number(row.value);
      if (i === 0 || !Number.isFinite(v) || !Number.isFinite(prev) || v !== prev) set.add(row.date);
      prev = v;
    });
    return { changedDates: set, repeats: asc.length - set.size };
  }, [data]);
  const stepLike = (data || []).length >= 40 && repeats / (data || []).length > 0.6;
  const onlyChanges = repeats > 0 && (onlyChangesChoice ?? stepLike);

  // Годовые ряды выбирают границы годом, остальные датой.
  const yearMode = useMemo(() => {
    const dates = (data || []).map((r) => r?.date).filter(Boolean);
    return dates.length > 1 && medianStepDays(dates) >= 300;
  }, [data]);
  const bounds = useMemo(() => {
    const dates = (data || []).map((r) => String(r?.date ?? '').slice(0, 10)).filter(Boolean).sort();
    return { first: dates[0] || '', last: dates[dates.length - 1] || '' };
  }, [data]);
  const fromIso = rangeFrom ? (yearMode && /^\d{4}$/.test(rangeFrom) ? `${rangeFrom}-01-01` : rangeFrom) : '';
  const toIso = rangeTo ? (yearMode && /^\d{4}$/.test(rangeTo) ? `${rangeTo}-12-31` : rangeTo) : '';
  const rangeActive = Boolean(fromIso || toIso);
  // Поле даты на компьютере открывает календарь только по значку, щелчок по тексту ставит курсор в день:
  // на ИПЦ «От» нажимали очередью (Пульс 17.11). Календарь открывается щелчком по всему полю.
  const openDatePicker = (event) => {
    if (yearMode) return;
    try {
      if (window.matchMedia?.('(pointer: fine)').matches) event.currentTarget.showPicker?.();
    } catch {
      /* браузер без showPicker или без жеста пользователя: остаётся обычное поле */
    }
  };
  const inRange = useCallback((row) => {
    const d = String(row?.date ?? '').slice(0, 10);
    if (fromIso && d < fromIso) return false;
    if (toIso && d > toIso) return false;
    return true;
  }, [fromIso, toIso]);

  const filtered = useMemo(() => {
    let rows = [...(data || [])];
    if (rangeActive) rows = rows.filter(inRange);
    if (onlyChanges) rows = rows.filter((r) => changedDates.has(r.date));
    if (search) {
      rows = rows.filter(r => tableRowMatches(r, search, { dateFormat, unit, valueDigits }));
    }
    rows.sort((a, b) => sortAsc
      ? new Date(a.date) - new Date(b.date)
      : new Date(b.date) - new Date(a.date)
    );
    return rows;
  }, [data, search, sortAsc, dateFormat, unit, valueDigits, onlyChanges, changedDates, rangeActive, inRange]);

  // Изменение к прошлому периоду и самые высокое и низкое значения считаем по всему ряду, а не по странице.
  // Единица изменения пишется один раз в заголовке столбца («Изменение, п. п.»), в строках только число со знаком.
  const rate = unitKind(unit) === 'rate';
  const { changes, changeNums, maxDate, minDate } = useMemo(() => {
    const asc = [...(data || [])]
      .filter((r) => r && r.date && Number.isFinite(Number(r.value)))
      .sort((a, b) => new Date(a.date) - new Date(b.date));
    const map = new Map();
    const nums = new Map();
    let hi = null;
    let lo = null;
    asc.forEach((row, i) => {
      const v = Number(row.value);
      if (hi == null || v > Number(hi.value)) hi = row;
      if (lo == null || v < Number(lo.value)) lo = row;
      if (i === 0) return;
      const prev = Number(asc[i - 1].value);
      if (rate) {
        const shown = formatDeltaNumber(v - prev, { digits: valueDigits ?? 2, locale });
        map.set(row.date, shown.text);
        nums.set(row.date, v - prev);
      } else if (prev > 0 && v >= 0) {
        const pct = (v / prev - 1) * 100;
        const shown = formatDeltaNumber(pct, { digits: growthDigits(pct), locale });
        map.set(row.date, shown.text);
        nums.set(row.date, pct);
      }
    });
    return {
      changes: map,
      changeNums: nums,
      maxDate: asc.length > 2 ? hi?.date : null,
      minDate: asc.length > 2 ? lo?.date : null,
    };
  }, [data, rate, valueDigits, locale]);

  const totalPages = Math.ceil(filtered.length / pageSize);
  const visiblePage = Math.min(page, Math.max(0, totalPages - 1));
  const pageData = filtered.slice(visiblePage * pageSize, (visiblePage + 1) * pageSize);

  // Переход к периоду вместо листания (18.11.2026): список лет или отрезков страниц в текущем порядке строк.
  const jump = useMemo(() => periodJumpOptions(filtered, pageSize, {
    yearMode,
    pageLabel: (a, b) => {
      const fmt = yearMode ? 'annual' : (dateFormat === 'day' || dateFormat === 'weekly' ? 'dayShort' : 'short');
      const left = formatDate(a, fmt);
      const right = formatDate(b, fmt);
      return left === right ? left : `${left} – ${right}`;
    },
  }), [filtered, pageSize, yearMode, dateFormat]);
  // Выбранная строка на открытой странице задаёт год в списке: после «2018» список не показывает «2019» из первой строки страницы.
  const pickedOnPage = jump.kind === 'year' && pickedDate && pageData.some((row) => row.date === pickedDate);
  const jumpValue = pickedOnPage
    ? String(pickedDate).slice(0, 4)
    : currentJumpValue(jump, filtered, visiblePage, pageSize);
  const goToJump = (value) => {
    const option = jump.options.find((o) => o.value === value);
    if (!option) return;
    setPage(option.page);
    setPickedDate(jump.kind === 'year'
      ? (filtered.find((row) => String(row.date).startsWith(value))?.date ?? null)
      : null);
    track(events.TABLE_JUMP, { source: jump.kind, to: value });
  };

  // Точка, выбранная на графике той же страницы, открывает в таблице свою строку (без прокрутки страницы).
  const latest = useRef({ filtered, pageSize, sortAsc });
  useEffect(() => { latest.current = { filtered, pageSize, sortAsc }; }, [filtered, pageSize, sortAsc]);
  useEffect(() => onPeriodPick(({ date }) => {
    const { filtered: rows, pageSize: size, sortAsc: asc } = latest.current;
    const hit = nearestRow(rows, date, { asc });
    if (!hit) return;
    setPage(Math.floor(hit.index / size));
    setPickedDate(hit.date);
  }), []);
  const tableUnit = unitSuffix(unit);
  // Ряд уже «изменение за год, %»: в строках стоит короткий «%», полная единица один раз в заголовке (круг 9, W10).
  const rowUnit = isPercentChangeUnit(unit) ? '%' : unit;
  // Длинная единица («индекс, старт = 100») не сжимает заголовок столбца до шести строк: она остаётся в подсказке и в блоке «О показателе».
  const longUnit = String(tableUnit || '').trim().length > 16;
  // Единица стоит в заголовке столбца, поэтому в строках её нет (раньше «34,88 %» и «−23,62 annual change» в каждой строке резали таблицу).
  const headerHoldsUnit = Boolean(tableUnit) && !longUnit;
  const unitInCells = showUnitInValues && !headerHoldsUnit;
  const ppLabel = t('c11c.table.pp');
  const percentLike = /%|п\.\s?п\.|\bpp\b/.test(String(unit ?? ''));
  const changeUnit = rate
    ? (percentLike ? ppLabel : (String(tableUnit || '').length <= 14 ? tableUnit : ''))
    : '%';
  const changeHead = changeUnit
    ? t('c11c.table.changeUnit', { unit: changeUnit })
    : t('w6e.table.change');
  const moreRight = useScrollMore(scrollRef, [pageData.length, headerHoldsUnit, changeHead]);

  const exportRows = useMemo(() => [...(data || [])]
    .filter((r) => r && r.date && inRange(r))
    .sort((a, b) => new Date(a.date) - new Date(b.date)), [data, inRange]);
  const runExport = async (format) => {
    if (!exportRows.length) return;
    const first = String(exportRows[0].date).slice(0, 10);
    const last = String(exportRows[exportRows.length - 1].date).slice(0, 10);
    const ext = format === 'csv' ? 'csv' : 'xlsx';
    const valueHead = tableUnit ? t('table.valueWithUnit', { unit: flatUnit(tableUnit) }) : t('table.value');
    try {
      await downloadGrid({
        format,
        filename: safeFilename(`${exportMeta?.filename || 'history'}_${first}_${last}`, ext),
        title: exportMeta?.name || resolvedTitle,
        columns: [
          { key: 'date', label: t('table.date') },
          { key: 'value', label: valueHead, unit: tableUnit || undefined },
          { key: 'change', label: changeHead, unit: changeUnit || undefined },
        ],
        rows: exportRows.map((row) => ({
          date: String(row.date).slice(0, 10),
          value: Number.isFinite(Number(row.value)) ? Number(row.value) : null,
          change: changeNums.get(row.date) ?? null,
        })),
        meta: exportMeta?.meta,
        history: {
          source: 'table',
          subject_key: exportMeta?.code,
          params: { ...(exportMeta?.params || {}), from: first, to: last },
        },
      }, {
        source: 'table-range',
        subject: {
          indicator: exportMeta?.code,
          code: exportMeta?.code,
          country: exportMeta?.params?.country,
          region: exportMeta?.params?.region,
        },
      });
    } catch {
      /* ошибка сети: кнопка остаётся, повторное нажатие повторит запрос */
    }
  };


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
        {repeats > 0 ? (
          <Chip
            active={onlyChanges}
            onClick={() => setOnlyChangesChoice(!onlyChanges)}
            className="fe-histtable__only"
          >
            {t('c9c.table.onlyChanges')}
          </Chip>
        ) : null}
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

      {bounds.first && (data || []).length > 1 && (
        <div className="c11c-range" data-testid="table-range">
          <label className="c11c-range__field">
            <span>{t('c11c.table.from')}</span>
            <input
              type={yearMode ? 'number' : 'date'}
              inputMode={yearMode ? 'numeric' : undefined}
              value={rangeFrom}
              min={yearMode ? bounds.first.slice(0, 4) : bounds.first}
              max={yearMode ? bounds.last.slice(0, 4) : bounds.last}
              placeholder={yearMode ? bounds.first.slice(0, 4) : undefined}
              onChange={(e) => { setRangeFrom(e.target.value); setPage(0); }}
              onClick={openDatePicker}
              aria-label={t('c11c.table.from')}
            />
          </label>
          <label className="c11c-range__field">
            <span>{t('c11c.table.to')}</span>
            <input
              type={yearMode ? 'number' : 'date'}
              inputMode={yearMode ? 'numeric' : undefined}
              value={rangeTo}
              min={yearMode ? bounds.first.slice(0, 4) : bounds.first}
              max={yearMode ? bounds.last.slice(0, 4) : bounds.last}
              placeholder={yearMode ? bounds.last.slice(0, 4) : undefined}
              onChange={(e) => { setRangeTo(e.target.value); setPage(0); }}
              onClick={openDatePicker}
              aria-label={t('c11c.table.to')}
            />
          </label>
          <div className="c11c-range__actions">
            {rangeActive && (
              <Chip
                aria-pressed={undefined}
                onClick={() => { setRangeFrom(''); setRangeTo(''); setPage(0); }}
              >
                {t('c11c.table.resetRange')}
              </Chip>
            )}
            <ChartDownloadMenu
              formats={['csv', 'excel']}
              label={rangeActive ? t('c11c.table.downloadRange') : t('c11c.table.downloadAll')}
              menuLabel={t('c11c.table.downloadRange')}
              onCsv={() => runExport('csv')}
              onExcel={() => runExport('xlsx')}
              showSaveButton={false}
            />
          </div>
          {rangeActive && (
            <p className="c11c-range__note" role="status">
              {t('c11c.table.rangeCount', { shown: filtered.length, total: (data || []).length })}
            </p>
          )}
        </div>
      )}

      <div className="c11c-histtable__wrap relative" data-more={moreRight ? 'true' : undefined}>
      <div ref={scrollRef} className="fe-histtable__scroll c11c-histtable__scroll scrollbar-hide" tabIndex={moreRight ? 0 : undefined} aria-label={moreRight ? title || t('table.historicalDefault') : undefined}>
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
                  onClick={() => { const next = !sortAsc; setSortAsc(next); setPage(0); track(events.TABLE_SORT, { order: next ? 'asc' : 'desc' }); }}
                >
                  {t('table.date')}
                  {sortAsc ? <ChevronUp className="w-3 h-3" aria-hidden="true" /> : <ChevronDown className="w-3 h-3" aria-hidden="true" />}
                </button>
              </th>
              <th
                scope="col"
                className="fe-histtable__valhead text-right px-5 py-3 text-[13px] font-semibold text-text-secondary"
                title={tableUnit && longUnit ? t('table.valueWithUnit', { unit: flatUnit(tableUnit) }) : undefined}
              >
                {tableUnit && !longUnit ? t('table.valueWithUnit', { unit: flatUnit(tableUnit) }) : t('table.value')}
              </th>
              <th
                scope="col"
                className="text-right px-5 py-3 text-[13px] font-semibold text-text-secondary"
                title={changeUnit ? undefined : (tableUnit || undefined)}
              >
                {changeHead}
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
                    row.date === pickedDate && 'is-picked',
                  )}
                  aria-current={row.date === pickedDate ? 'true' : undefined}
                >
                  <td className="px-5 py-2.5 text-text-secondary text-sm tabular-nums">
                    {formatDate(row.date, dateFormat)}
                    {row.date === maxDate && <span className="fe-histtable__tag">{t('w6e.table.max')}</span>}
                    {row.date === minDate && <span className="fe-histtable__tag">{t('w6e.table.min')}</span>}
                  </td>
                  <td className="px-5 py-2.5 text-right text-sm font-semibold tabular-nums text-text-primary">
                    {unitInCells
                      ? valueWithUnit(row.value, valueDigits, rowUnit)
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
      <span className="c11c-histtable__fade" aria-hidden="true" />
      </div>

      {totalPages > 1 && (
        <div className="fe-histtable__pager p-4 flex items-center justify-between gap-3 k5-seam k5-seam--top">
          {/* По умолчанию сверху новые строки: «Вперёд» уводил в прошлое. Кнопки названы по времени (18.11.2026). */}
          <Button
            variant="secondary"
            className="fe-pager-btn"
            onClick={() => { setPage(Math.max(0, visiblePage - 1)); track(events.TABLE_PAGE, { direction: 'prev' }); }}
            disabled={loading || visiblePage === 0}
          >
            <ChevronLeft className="w-4 h-4 shrink-0" aria-hidden="true" />
            {sortAsc ? t('table.earlier') : t('table.later')}
          </Button>
          {jump.options.length > 1 ? (
            <label className="fe-histtable__jump fe-tap">
              <span className="sr-only">{jump.kind === 'year' ? t('table.jumpYear') : t('table.jumpPeriod')}</span>
              <select
                value={jumpValue}
                onChange={(e) => goToJump(e.target.value)}
                disabled={loading}
                aria-label={jump.kind === 'year' ? t('table.jumpYear') : t('table.jumpPeriod')}
              >
                {jump.options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
              <ChevronDown className="fe-histtable__jump-icon" aria-hidden="true" />
            </label>
          ) : (
            <span className="text-sm text-text-secondary tabular-nums" aria-live="polite">
              {visiblePage + 1} / {totalPages}
            </span>
          )}
          <Button
            variant="secondary"
            className="fe-pager-btn"
            onClick={() => { setPage(Math.min(totalPages - 1, visiblePage + 1)); track(events.TABLE_PAGE, { direction: 'next' }); }}
            disabled={loading || visiblePage >= totalPages - 1}
          >
            {sortAsc ? t('table.later') : t('table.earlier')}
            <ChevronRight className="w-4 h-4 shrink-0" aria-hidden="true" />
          </Button>
        </div>
      )}
    </div>
  );
}
