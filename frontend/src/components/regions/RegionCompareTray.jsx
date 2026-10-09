// Лоток сравнения регионов под картой (круг 11, F): выбранные регионы, их шесть главных показателей одной таблицей
// (лучшее в строке выделено) и выгрузка. Для двух регионов есть ещё полное сравнение на отдельной странице.
import { useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Download, GitCompare, X } from 'lucide-react';
import DownloadMenu from './DownloadMenu';
import { useRegionsHeatmap } from '../../lib/regionsApi';
import { formatRegionWithUnit } from '../../lib/regionUi';
import { buildCompareRows, COMPARE_MAX } from '../../lib/regionCompareTable';
import { downloadGrid, gridColumnKey, gridFilename } from '../../lib/gridDownload';
import { useScrollFades } from '../../lib/useScrollFades';
import { regionIndicatorPath, regionVsPath } from '../../lib/sitePaths';
import { track, events } from '../../lib/track';
import { useAuth } from '../../context/authContext';
import { useLocale } from '../../i18n';
import '../../styles/regions-w4.css';

export default function RegionCompareTray({ slugs, namesBySlug, metrics, onRemove, onClear }) {
  const { t, locale } = useLocale();
  const { isAuthed } = useAuth();
  const [exporting, setExporting] = useState(false);
  const scrollRef = useRef(null);
  const ready = slugs.length >= 2;
  // Шесть срезов одним набором хуков (число фиксировано); грузятся, только когда выбрано два региона и больше.
  const h0 = useRegionsHeatmap(metrics[0]?.code, ready);
  const h1 = useRegionsHeatmap(metrics[1]?.code, ready);
  const h2 = useRegionsHeatmap(metrics[2]?.code, ready);
  const h3 = useRegionsHeatmap(metrics[3]?.code, ready);
  const h4 = useRegionsHeatmap(metrics[4]?.code, ready);
  const h5 = useRegionsHeatmap(metrics[5]?.code, ready);
  const heats = [h0, h1, h2, h3, h4, h5].slice(0, metrics.length).map((query) => query.data);
  const loading = ready && [h0, h1, h2, h3, h4, h5].slice(0, metrics.length).some((query) => query.isLoading);
  const rows = useMemo(
    () => buildCompareRows(metrics.map((metric) => ({ ...metric, label: t(metric.labelKey) })), heats, slugs),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [metrics, slugs, h0.data, h1.data, h2.data, h3.data, h4.data, h5.data, t],
  );
  useScrollFades(scrollRef, [slugs.length, ready]);

  if (slugs.length === 0) return null;
  const nameOf = (slug) => namesBySlug[slug] || slug;

  const handleExport = async (format) => {
    if (exporting) return;
    const indicator = 'regions-compare';
    if (!isAuthed) {
      track(events.DOWNLOAD_LIMIT_HIT, { indicator });
      window.dispatchEvent(new CustomEvent('fe:download-limit'));
      return;
    }
    setExporting(true);
    try {
      const columns = [
        { key: 'metric', label: t('c11f.reg.compare.colMetric') },
        ...slugs.map((slug) => ({ key: gridColumnKey(`r_${slug}`), label: nameOf(slug) })),
      ];
      const data = rows.map((row) => {
        const line = { metric: row.unit ? `${row.label}, ${row.unit}` : row.label };
        row.cells.forEach((cell) => { line[gridColumnKey(`r_${cell.slug}`)] = cell.value == null ? null : Number(cell.value.toFixed(4)); });
        return line;
      });
      await downloadGrid({
        format,
        filename: gridFilename(`regions_compare_${slugs.length}`, format),
        title: slugs.map(nameOf).join(' — '),
        columns,
        rows: data,
        meta: { country: locale === 'en' ? 'Russia' : 'Россия' },
        history: { source: 'region', subject_key: slugs.join(','), params: { regions: slugs } },
      });
      track(format === 'csv' ? events.DOWNLOAD_CSV : events.DOWNLOAD_EXCEL, { indicator, rows: data.length });
    } catch (err) {
      if (err?.code === 'download_limit') window.dispatchEvent(new CustomEvent('fe:download-limit'));
    } finally {
      setExporting(false);
    }
  };

  return (
    <section className="fe-tray fe-glass-lite" data-testid="region-compare-tray" aria-label={t('c11f.reg.compare.title')}>
      <div className="fe-tray__head">
        <h2 className="fe-tray__title">
          <GitCompare size={16} aria-hidden="true" />
          {t('c11f.reg.compare.title')}
        </h2>
        <div className="fe-tray__tools">
          {ready && (
            <DownloadMenu
              disabled={exporting || loading}
              items={[
                { key: 'csv', label: 'CSV', hint: t('x4.download.csvHint'), icon: Download, onSelect: () => handleExport('csv') },
                { key: 'xlsx', label: 'Excel', hint: t('x4.download.xlsxHint'), icon: Download, onSelect: () => handleExport('xlsx') },
              ]}
            />
          )}
          <button type="button" className="fe-chip fe-press" onClick={onClear}>{t('c11f.reg.compare.clear')}</button>
        </div>
      </div>
      <ul className="fe-tray__chips">
        {slugs.map((slug) => (
          <li key={slug}>
            <span className="fe-tray__chip">
              <span className="min-w-0">{nameOf(slug)}</span>
              <button type="button" className="fe-tray__x" aria-label={t('c11f.reg.compare.remove', { name: nameOf(slug) })} onClick={() => onRemove(slug)}>
                <X size={14} aria-hidden="true" />
              </button>
            </span>
          </li>
        ))}
      </ul>
      {!ready && <p className="fe-tray__hint">{t('c11f.reg.compare.pickMore', { max: COMPARE_MAX })}</p>}
      {ready && (
        <div className="fe-tray__scroll" ref={scrollRef}>
          <table className="fe-tray__table">
            <thead>
              <tr>
                <th scope="col" className="fe-tray__metric">{t('c11f.reg.compare.colMetric')}</th>
                {slugs.map((slug) => <th key={slug} scope="col">{nameOf(slug)}</th>)}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.code}>
                  <th scope="row" className="fe-tray__metric">{row.label}</th>
                  {row.cells.map((cell) => (
                    <td key={cell.slug} data-leader={row.leader === cell.slug ? 'true' : undefined}>
                      {cell.value == null
                        ? (loading ? '…' : '—')
                        : (
                          <Link to={regionIndicatorPath(cell.slug, row.code)} className="fe-tray__val fe-num">
                            {formatRegionWithUnit(cell.value, row.unit, locale)}
                          </Link>
                        )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {slugs.length === 2 && (
        <Link to={regionVsPath(slugs[0], slugs[1])} className="fe-tray__open fe-press">
          {t('c11f.reg.compare.openPair')}
        </Link>
      )}
    </section>
  );
}
