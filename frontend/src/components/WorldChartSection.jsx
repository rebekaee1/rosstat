import { useRef } from 'react';
import { Terminal, Download, Lock, Image as ImageIcon } from 'lucide-react';
import { resolveDateFormat, cn } from '../lib/format';
import { track, events } from '../lib/track';
import { useDownloadAccess } from '../lib/useDownloadAccess';
import { exportNodeToPng } from '../lib/chartImage';
import IndicatorChart from './IndicatorChart';
import { ChartSkeleton } from './Skeleton';
import { worldChartTitle, worldRangePreset } from '../lib/worldViewModes';

/**
 * Секция графика мировой карточки.
 * Переиспользует IndicatorChart; прогноза нет — ни тоггла, ни ссылки
 * на методологию прогнозов (жёсткое требование владельца).
 */
function DownloadButton({ label, onDownload, blocked, hint }) {
  const handleClick = () => {
    if (blocked) {
      window.dispatchEvent(new CustomEvent('fe:download-limit'));
      return;
    }
    onDownload?.();
  };
  const tooltip = blocked ? 'Скачивание данных — после бесплатной регистрации' : hint;
  return (
    <div className="relative group/dl">
      <button
        type="button"
        onClick={handleClick}
        aria-disabled={blocked}
        className={cn(
          'flex items-center gap-1.5 px-3 py-1.5 rounded-lg border transition-colors text-xs font-mono uppercase tracking-wider',
          blocked
            ? 'border-border-subtle/60 text-text-tertiary/50 cursor-pointer'
            : 'border-border-subtle text-text-tertiary hover:text-champagne hover:border-champagne/30',
        )}
        title={blocked ? 'Скачивание данных — после бесплатной регистрации' : `Скачать ${label}`}
      >
        {blocked ? <Lock className="w-3.5 h-3.5" /> : <Download className="w-3.5 h-3.5" />}
        {label}
      </button>
      {tooltip && (
        <div className="absolute top-full right-0 mt-2 px-3 py-2 rounded-xl bg-obsidian border border-border-subtle text-[11px] normal-case tracking-normal text-text-secondary whitespace-nowrap opacity-0 group-hover/dl:opacity-100 transition-opacity duration-200 pointer-events-none shadow-xl z-50">
          {tooltip}
        </div>
      )}
    </div>
  );
}

function ImageButton({ onDownload, authed }) {
  const tooltip = authed
    ? 'Скачать график картинкой (PNG)'
    : 'Скачивание графика — после бесплатной регистрации';
  return (
    <div className="relative group/img" data-no-export="true">
      <button
        type="button"
        onClick={onDownload}
        aria-disabled={!authed}
        className={cn(
          'flex items-center gap-1.5 px-3 py-1.5 rounded-lg border transition-colors text-xs font-mono uppercase tracking-wider',
          authed
            ? 'border-border-subtle text-text-tertiary hover:text-champagne hover:border-champagne/30'
            : 'border-border-subtle/60 text-text-tertiary/50 cursor-pointer',
        )}
        title={tooltip}
      >
        {authed ? <ImageIcon className="w-3.5 h-3.5" /> : <Lock className="w-3.5 h-3.5" />}
        PNG
      </button>
      <div className="absolute top-full right-0 mt-2 px-3 py-2 rounded-xl bg-obsidian border border-border-subtle text-[11px] normal-case tracking-normal text-text-secondary whitespace-nowrap opacity-0 group-hover/img:opacity-100 transition-opacity duration-200 pointer-events-none shadow-xl z-50">
        {tooltip}
      </div>
    </div>
  );
}

export default function WorldChartSection({
  code,
  indicator,
  modeMeta,
  dataPoints,
  chartLoading,
  emptyHint,
  onFullData,
  onDownloadCsv,
  onDownloadExcel,
  frequency,
  aggregated = false,
  unit: unitOverride,
}) {
  const { blocked: downloadBlocked, isAuthed: downloadAuthed } = useDownloadAccess();
  const chartRef = useRef(null);
  const unit = unitOverride || modeMeta?.unit || indicator?.unit || '';
  const activeFreq = frequency || modeMeta?.freq || indicator?.frequency;
  const title = worldChartTitle(indicator, modeMeta, activeFreq);

  const handleDownloadImage = async () => {
    if (!downloadAuthed) {
      track(events.CHART_IMAGE_BLOCKED, { indicator: code, world: true });
      window.dispatchEvent(new CustomEvent('fe:download-limit'));
      return;
    }
    const ok = await exportNodeToPng(chartRef.current, {
      filename: `${code}_${modeMeta?.id || 'level'}.png`,
      watermark: false,
    }).catch(() => false);
    if (ok) {
      track(events.CHART_IMAGE_DOWNLOAD, {
        indicator: code,
        mode: modeMeta?.id,
        world: true,
      });
    }
  };

  return (
    <section data-block="chart" className="mb-16">
      <div className="flex items-center justify-between mb-6 border-b border-border-subtle pb-4 flex-wrap gap-3">
        <div className="flex items-center gap-4 min-w-0">
          <Terminal className="w-4 h-4 text-champagne shrink-0" />
          <span className="text-[11px] font-mono uppercase tracking-widest text-text-tertiary truncate">
            {title}
          </span>
        </div>

        <div className="flex items-center gap-3" data-no-export="true">
          <DownloadButton label="CSV" onDownload={onDownloadCsv} blocked={downloadBlocked} />
          <DownloadButton label="Excel" onDownload={onDownloadExcel} blocked={downloadBlocked} />
          <ImageButton onDownload={handleDownloadImage} authed={downloadAuthed} />
        </div>
      </div>

      {aggregated && (
        <p className="mb-3 text-[12px] text-text-secondary">
          Ряд получен пересчётом на сайте, а не официальной публикацией Евростата
          с этой частотой.
        </p>
      )}

      {chartLoading ? (
        <ChartSkeleton />
      ) : (
        <div ref={chartRef} className="relative overflow-hidden rounded-[2rem]">
          <IndicatorChart
            key={`${code}-${modeMeta?.id}-${activeFreq}`}
            mode="cpi"
            cpiData={dataPoints || []}
            forecastData={null}
            showForecast={false}
            onFullData={onFullData}
            cpiChartTitle={title}
            levelTooltipLabel={modeMeta?.label || modeMeta?.group || 'Значение'}
            emptyHint={emptyHint}
            dateFormat={resolveDateFormat({ frequency: activeFreq, chartMode: 'cpi' })}
            unit={unit}
            rangePreset={worldRangePreset(activeFreq)}
            chartMode={modeMeta?.id || 'level'}
            indicatorCode={code}
            indicatorCategory={indicator?.category}
            referenceLineY={unit === '%' || unit === 'п.п.' ? 0 : null}
          />
        </div>
      )}
    </section>
  );
}
