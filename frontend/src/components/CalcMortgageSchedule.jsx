// Круг 11 (E): таблица платежей по ипотеке (по годам и по месяцам) и выгрузка в CSV через POST /export/grid.
// Гость без права на скачивание получает окно регистрации (событие fe:download-limit), как у выгрузки рядов.
import { useMemo, useState } from 'react';
import { Download, Table2 } from 'lucide-react';
import { revealStyle } from '../lib/calcUi';
import { formatAmountPlain } from '../lib/calcFormat';
import { downloadGrid } from '../lib/calcExport';
import { scheduleGrid } from '../lib/mortgageSchedule';
import { track, events } from '../lib/track';
import Chip from './Chip';
import Button from './Button';
import { useT } from '../i18n';
import '../styles/calc-ui.css';

const MONTHS_STEP = 24;

export default function CalcMortgageSchedule({ schedule, filenameBase = 'mortgage-schedule', historyParams, index = 8 }) {
  const t = useT();
  const [mode, setMode] = useState('year');
  const [shown, setShown] = useState(MONTHS_STEP);
  const [status, setStatus] = useState('');
  const [busy, setBusy] = useState(false);
  const hasExtra = useMemo(() => schedule.rows.some((row) => row.extra > 0), [schedule]);
  const rows = mode === 'year' ? schedule.years : schedule.rows.slice(0, shown);
  const labels = useMemo(() => ({
    year: t('c11e.table.year'),
    month: t('c11e.table.month'),
    payment: t('c11e.table.payment'),
    principal: t('c11e.table.principal'),
    interest: t('c11e.table.interest'),
    extra: t('c11e.table.extra'),
    balance: t('c11e.table.balance'),
  }), [t]);
  if (!schedule.rows.length) return null;

  const download = async () => {
    setBusy(true);
    setStatus('');
    const grid = scheduleGrid(schedule, { granularity: mode === 'year' ? 'year' : 'month', labels });
    const outcome = await downloadGrid({
      format: 'csv',
      filename: `${filenameBase}-${mode === 'year' ? 'years' : 'months'}.csv`,
      title: t('c11e.table.title'),
      grid,
      history: { source: 'calc-mortgage', subject_key: 'mortgage-schedule', params: historyParams },
    });
    setBusy(false);
    if (outcome === 'ok') track(events.DOWNLOAD_CSV, { source: 'calc-mortgage', granularity: mode });
    setStatus(outcome === 'ok' ? '' : outcome === 'limit' ? t('c11e.table.limit') : t('c11e.table.error'));
  };

  return (
    <section
      style={revealStyle(index)}
      className="fe-reveal fe-panel rounded-[2rem] shadow-sm shadow-black/[0.03] p-5 md:p-6 mb-6"
      data-block="calc-schedule"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-2">
          <Table2 className="w-4 h-4 text-champagne" aria-hidden="true" />
          <h3 className="text-base font-semibold text-text-primary">{t('c11e.table.title')}</h3>
        </div>
        <div className="flex flex-wrap gap-1.5" role="group" aria-label={t('c11e.table.modeAria')}>
          <Chip active={mode === 'year'} onClick={() => setMode('year')}>{t('c11e.table.byYear')}</Chip>
          <Chip active={mode === 'month'} onClick={() => { setMode('month'); setShown(MONTHS_STEP); }}>{t('c11e.table.byMonth')}</Chip>
        </div>
      </div>

      <div className="fe-c11e-tablewrap" tabIndex={0} role="region" aria-label={t('c11e.table.title')}>
        <table className="fe-c11e-table">
          <thead>
            <tr>
              <th scope="col">{mode === 'year' ? labels.year : labels.month}</th>
              <th scope="col">{labels.payment}</th>
              <th scope="col">{labels.principal}</th>
              <th scope="col">{labels.interest}</th>
              {hasExtra && <th scope="col">{labels.extra}</th>}
              <th scope="col">{labels.balance}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={mode === 'year' ? row.year : row.month}>
                <th scope="row">{mode === 'year' ? row.year : row.month}</th>
                <td>{formatAmountPlain(row.payment)}</td>
                <td>{formatAmountPlain(row.principalPaid)}</td>
                <td>{formatAmountPlain(row.interestPaid)}</td>
                {hasExtra && <td>{formatAmountPlain(row.extra)}</td>}
                <td>{formatAmountPlain(row.balance)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-text-secondary">{t('c11e.table.unitNote')}</p>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {mode === 'month' && shown < schedule.rows.length && (
          <Button variant="secondary" size="sm" onClick={() => setShown((n) => n + MONTHS_STEP)}>
            {t('c11e.table.more', { n: Math.min(MONTHS_STEP, schedule.rows.length - shown) })}
          </Button>
        )}
        <Button variant="secondary" size="sm" onClick={download} loading={busy} data-testid="schedule-download">
          <Download className="w-3.5 h-3.5" aria-hidden="true" />
          {t('c11e.table.download')}
        </Button>
      </div>
      {status && <p role="status" className="mt-2 text-xs text-text-secondary">{status}</p>}
    </section>
  );
}
