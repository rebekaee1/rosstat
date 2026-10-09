// «Лучшие десять / последние десять» рядом с картой регионов (круг 11, F): человек видит, кто впереди и кто позади,
// не наводя мышь на 85 регионов. Строка выбирает регион на карте. Внизу — выгрузка таблицы по всем регионам.
import { useMemo, useState } from 'react';
import { Download } from 'lucide-react';
import DownloadMenu from './DownloadMenu';
import { formatRegionWithUnit } from '../../lib/regionUi';
import { leadersAndTrailers, leadersDirection, rankRegions } from '../../lib/regionLeaders';
import { downloadGrid, gridFilename } from '../../lib/gridDownload';
import { track, events } from '../../lib/track';
import { useAuth } from '../../context/authContext';
import { useLocale } from '../../i18n';
import '../../styles/regions-w4.css';

function Row({ row, unit, locale, picked, onPick }) {
  return (
    <li>
      <button
        type="button"
        className="fe-lead__row fe-press"
        aria-pressed={picked === row.slug}
        onClick={() => onPick(row.slug)}
      >
        <span className="fe-lead__place">{row.place}</span>
        <span className="fe-lead__name">{row.name}</span>
        <span className="fe-lead__value fe-num">{formatRegionWithUnit(row.value, unit, locale)}</span>
      </button>
    </li>
  );
}

export default function RegionLeaders({
  valuesBySlug, namesBySlug, unit = '', indicatorName = '', year = null, heatmap = null, pickedSlug = null, onPick,
}) {
  const { t, locale } = useLocale();
  const { isAuthed } = useAuth();
  const [exporting, setExporting] = useState(false);
  const direction = leadersDirection(heatmap);
  const achievement = Boolean(heatmap?.rank_as_achievement);
  const ranked = useMemo(
    () => rankRegions(valuesBySlug, namesBySlug, { direction }),
    [valuesBySlug, namesBySlug, direction],
  );
  const { top, bottom, total } = useMemo(() => leadersAndTrailers(ranked, 10), [ranked]);
  if (total < 6) return null;

  const handleExport = async (format) => {
    if (exporting) return;
    const indicator = `regions-leaders:${heatmap?.indicator?.code || ''}`;
    if (!isAuthed) {
      track(events.DOWNLOAD_LIMIT_HIT, { indicator });
      window.dispatchEvent(new CustomEvent('fe:download-limit'));
      return;
    }
    setExporting(true);
    try {
      const title = [indicatorName, year ? String(year) : ''].filter(Boolean).join(', ');
      await downloadGrid({
        format,
        filename: gridFilename(`regions_${heatmap?.indicator?.code || 'ranking'}_${year || ''}`, format),
        title,
        columns: [
          { key: 'rank', label: t('c11f.reg.leaders.colRank') },
          { key: 'region', label: t('c11f.reg.leaders.colRegion') },
          { key: 'value', label: indicatorName || t('c11f.reg.leaders.colValue'), unit: unit || undefined },
        ],
        rows: ranked.map((row, index) => ({ rank: index + 1, region: row.name, value: Number(row.value.toFixed(4)) })),
        meta: { country: locale === 'en' ? 'Russia' : 'Россия', source: heatmap?.indicator?.source || undefined },
        history: { source: 'region', subject_key: heatmap?.indicator?.code || '', params: { year } },
      });
      track(format === 'csv' ? events.DOWNLOAD_CSV : events.DOWNLOAD_EXCEL, { indicator, rows: ranked.length });
    } catch (err) {
      if (err?.code === 'download_limit') window.dispatchEvent(new CustomEvent('fe:download-limit'));
    } finally {
      setExporting(false);
    }
  };

  const list = (rows, heading, tone) => (
    <section className="fe-lead__col" data-tone={tone}>
      <h3 className="fe-lead__head">{heading}</h3>
      <ol className="fe-lead__list">
        {rows.map((row) => (
          <Row key={row.slug} row={row} unit={unit} locale={locale} picked={pickedSlug} onPick={onPick} />
        ))}
      </ol>
    </section>
  );

  return (
    <aside className="fe-lead fe-glass-lite" data-testid="region-leaders" aria-label={t('c11f.reg.leaders.aria')}>
      <div className="fe-lead__top">
        <h2 className="fe-lead__title">{t('c11f.reg.leaders.title')}</h2>
        <DownloadMenu
          disabled={exporting}
          items={[
            { key: 'csv', label: 'CSV', hint: t('c11f.reg.leaders.all', { n: total }), icon: Download, onSelect: () => handleExport('csv') },
            { key: 'xlsx', label: 'Excel', hint: t('c11f.reg.leaders.all', { n: total }), icon: Download, onSelect: () => handleExport('xlsx') },
          ]}
        />
      </div>
      <p className="fe-lead__sub">{[indicatorName, year ? String(year) : ''].filter(Boolean).join(', ')}</p>
      <div className="fe-lead__cols">
        {list(top, t(achievement ? 'c11f.reg.leaders.best' : 'c11f.reg.leaders.most'), 'top')}
        {list(bottom, t(achievement ? 'c11f.reg.leaders.worst' : 'c11f.reg.leaders.least'), 'bottom')}
      </div>
    </aside>
  );
}
