// «Цена на дату»: недельные цены на топливо в регионе (ЕМИСС 37426, с 2022 года; 18.11.2026).
// Выбор дня → цена последней записи Росстата не позже него, рядом — Россия в тот же день;
// ниже — все недельные записи, выбранная строка подсвечена. Блок есть, только если API отдал `weekly`.
import { useEffect, useMemo, useRef, useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { useLocale } from '../../i18n';
import { formatDate } from '../../lib/format';
import { kopText, pointOn, weeklyRows } from '../../lib/weeklyPrice';
import { track, events } from '../../lib/track';
import '../../styles/calc-ui.css';
import '../../styles/fw-weekly.css';

export default function WeeklyPrices({ weekly, weeklyRussia, regionName, isRussia = false, subject }) {
  const { t, locale } = useLocale();
  const [picked, setPicked] = useState('');
  const [open, setOpen] = useState(false);
  const selectedRow = useRef(null);
  const first = weekly[0];
  const last = weekly[weekly.length - 1];
  const point = pointOn(weekly, picked);
  const rows = useMemo(() => weeklyRows(weekly, isRussia ? [] : weeklyRussia), [weekly, weeklyRussia, isRussia]);
  const rf = !isRussia ? (weeklyRussia || []).find((p) => p.date === point?.date) : null;
  const day = (iso) => formatDate(iso, 'day', locale);
  const today = new Date().toISOString().slice(0, 10);

  useEffect(() => {
    if (open && picked && selectedRow.current) selectedRow.current.scrollIntoView({ block: 'nearest' });
  }, [open, picked, point?.date]);

  if (!point) return null;
  let note = null;
  if (picked && picked < first.date) note = t('fw.beforeFirst', { date: day(first.date) });
  else if (picked && picked !== point.date) note = t('fw.nearest', { date: day(picked) });

  return (
    <section data-block="region-weekly" className="fw-card mb-6 rounded-3xl p-4 sm:p-5 fe-glass-lite" aria-labelledby="fw-title">
      <div className="fw-head">
        <h2 id="fw-title" className="text-sm font-semibold text-text-primary">{t('fw.title')}</h2>
        <p className="fw-lead">{t('fw.lead')}</p>
      </div>
      <div className="fw-body">
        <label className="fw-pick">
          <span className="fw-pick__label">{t('fw.pickLabel')}</span>
          <span className="fw-pick__field">
            <input
              type="date"
              aria-label={t('fw.pickAria')}
              className="calc-field-input fw-pick__input fe-num"
              min="2000-01-01"
              max={today}
              value={picked}
              onChange={(e) => {
                setPicked(e.target.value);
                if (e.target.value) track(events.REGION_WEEKLY_DATE, { subject, date: e.target.value });
              }}
              aria-describedby="fw-answer"
            />
          </span>
        </label>
        <div id="fw-answer" className="fw-answer" aria-live="polite">
          <p className="fw-answer__value fe-num">{kopText(point.value, locale)}<span className="fw-answer__unit">{t('fw.perLitre')}</span></p>
          <p className="fw-answer__date">{t('fw.onDate', { date: day(point.date) })}</p>
          {rf && (
            <p className="fw-answer__rf fe-num">{t('fw.russiaSameDay', { value: kopText(rf.value, locale) })}</p>
          )}
          {note && <p className="fw-answer__note">{note}</p>}
        </div>
      </div>
      <p className="fw-foot">{t('fw.foot', { first: day(first.date), last: day(last.date) })}</p>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="fw-toggle w-full flex items-center justify-between rounded-2xl px-3 py-2.5 hover:bg-surface-hover transition-colors"
        aria-expanded={open}
      >
        <span className="text-[13px] font-medium text-text-primary">{t('fw.tableToggle', { n: weekly.length })}</span>
        <ChevronDown size={16} className={`text-text-secondary transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="fw-table max-h-96 overflow-auto">
          <table className="w-full min-w-[18rem] text-[13px]">
            <thead className="sticky top-0 bg-surface">
              <tr className="text-left text-text-secondary">
                <th className="px-3 py-2 font-medium">{t('fw.colDate')}</th>
                <th className="px-3 py-2 text-right font-medium">{regionName}</th>
                {!isRussia && <th className="px-3 py-2 text-right font-medium">{t('regions.ind.russia')}</th>}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const on = r.date === point.date;
                return (
                  <tr key={r.date} ref={on ? selectedRow : null} className={on ? 'fw-row--on' : undefined} aria-current={on ? 'true' : undefined}>
                    <td className="fe-num px-3 py-1.5 text-text-secondary">{day(r.date)}</td>
                    <td className="fe-num px-3 py-1.5 text-right text-text-primary">{kopText(r.value, locale)}</td>
                    {!isRussia && <td className="fe-num px-3 py-1.5 text-right text-text-secondary">{r.russia != null ? kopText(r.russia, locale) : '—'}</td>}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
