import { useRef } from 'react';
import { Link } from 'react-router-dom';
import { Terminal, Download, Lock, Image as ImageIcon, HelpCircle } from 'lucide-react';
import { unitSuffix, resolveDateFormat, cn } from '../lib/format';
import { track, events } from '../lib/track';
import { useDownloadAccess } from '../lib/useDownloadAccess';
import { exportNodeToPng } from '../lib/chartImage';
import IndicatorChart from './IndicatorChart';
import { ChartSkeleton } from './Skeleton';
import { getCpiChartTitle } from '../lib/cpiViewModeContent';
import { getHousingChartTitle } from '../lib/housingViewModeContent';
import { getPpiChartTitle } from '../lib/ppiViewModeContent';
import { getCbrTermSliceChartTitle } from '../lib/cbrTermSliceRateContent';
import { getUnemploymentChartTitle } from '../lib/unemploymentViewModeContent';
import { chartSeriesForViewMode } from '../lib/chartSeriesForViewMode';

/* ── Mode-зависимые подписи ──
   chartMode принимает значения: 'cpi' (default для всех некоммодити-индикаторов),
   'quarterly', 'annual', 'weekly', 'inflation' (только для CPI семьи).
   Для не-CPI индикаторов важен `indicator.frequency` — он задаёт ритм ряда
   (daily/weekly/monthly/quarterly/annual). Прогноз идёт в том же ритме —
   подписи tooltip/легенды/заголовка отражают это. */

const FREQUENCY_LABEL = {
  daily: 'днев.',
  weekly: 'нед.',
  monthly: 'мес.',
  quarterly: 'кв.',
  annual: 'год.',
};

const FREQUENCY_LONG = {
  daily: 'днев.',
  weekly: 'недельная',
  monthly: 'помесячно',
  quarterly: 'квартально',
  annual: 'годовая',
};

function freqLabel(indicator) {
  return FREQUENCY_LABEL[indicator?.frequency] || '';
}

function freqLong(indicator) {
  return FREQUENCY_LONG[indicator?.frequency] || '';
}

function chartTitle({
  chartMode, isPriceCategory, isHousingFamily, isPpiFamily,
  isCbrTermSliceFamily, isUnemploymentFamily,
  indicator, safeViewMode,
}) {
  if (isUnemploymentFamily) {
    return getUnemploymentChartTitle(chartMode);
  }
  if (isPpiFamily) {
    return getPpiChartTitle(chartMode, safeViewMode);
  }
  if (isCbrTermSliceFamily) {
    return getCbrTermSliceChartTitle(chartMode, indicator?.code);
  }
  if (isHousingFamily && indicator?.code) {
    return getHousingChartTitle(chartMode, indicator.code, safeViewMode);
  }
  if (isPriceCategory && indicator?.code) {
    return getCpiChartTitle(chartMode, indicator.code, safeViewMode);
  }
  const suffix = unitSuffix(indicator?.unit);
  const freq = freqLong(indicator);
  const baseTitle = `${indicator?.name || 'Показатель'}${suffix ? ` (${suffix})` : ''}`;
  return freq ? `${baseTitle} — ${freq}` : baseTitle;
}

function levelTooltipLabel({
  chartMode, isPriceCategory, isHousingFamily, isPpiFamily,
  isCbrTermSliceFamily,
  indicator,
}) {
  if (isCbrTermSliceFamily && chartMode === 'level') return 'Ставка';
  if ((isHousingFamily || isPpiFamily) && chartMode === 'index') return 'Индекс';
  if (isPpiFamily && chartMode === 'mom') return 'М/м';
  if (isHousingFamily && chartMode === 'annual') return 'Г/г';
  if (chartMode === 'quarterly') return 'Кв. инфляция';
  if (chartMode === 'annual') return 'Год. инфляция';
  if (chartMode === 'weekly') return 'Нед. ИПЦ';
  if (chartMode === 'yoy') return 'Г/г';
  if (chartMode === 'qoq') return 'Кв/Кв';
  if (chartMode === 'period-weekly') return 'С нач. мес.';
  if (chartMode === 'period-monthly') return 'За месяц';
  if (chartMode === 'index') return 'ИПЦ';
  if (isPriceCategory) return 'Прирост';
  const freq = freqLabel(indicator);
  return freq ? `Факт (${freq})` : 'Значение';
}

function forecastTooltipLabel({ chartMode, indicator }) {
  if (chartMode === 'quarterly') return 'Прогноз (кв.)';
  if (chartMode === 'annual') return 'Прогноз (год.)';
  if (chartMode === 'weekly') return 'Прогноз (нед.)';
  if (chartMode === 'inflation') return 'Прогноз (12 мес.)';
  if (chartMode === 'index') return 'Прогноз (мес. ИПЦ)';
  const freq = freqLabel(indicator);
  return freq ? `Прогноз (${freq})` : 'Прогноз';
}

function rangePresetFor({ chartMode, indicator }) {
  /* Mode-driven для CPI семьи (annual mode → 10y/25y/all). */
  if (chartMode === 'annual') return 'annual';
  if (chartMode === 'quarterly' || chartMode === 'qoq') return 'quarterly';
  if (chartMode === 'weekly') return 'weekly';
  if (chartMode === 'yoy' || chartMode === 'period-weekly' || chartMode === 'period-monthly') return 'default';
  // Накопленный индекс CPI — длинная история (2000+), показываем 5y/10y/25y/all.
  if (chartMode === 'index') return 'quarterly';
  /* Frequency-driven для остальных индикаторов. */
  const freq = indicator?.frequency;
  if (freq === 'quarterly') return 'quarterly';
  if (freq === 'annual') return 'annual';
  if (freq === 'weekly') return 'weekly';
  if (freq === 'daily') return 'daily';
  return 'default';
}

/**
 * Кнопка выгрузки (CSV/Excel) с гейтом лимита (ADR-0007 Phase 2).
 * Гость до лимита и любой авторизованный — активна. Гость после лимита —
 * тускнеет, на hover подсказка зовёт войти, клик ведёт на регистрацию.
 */
function ruYears(n) {
  const mod100 = Math.abs(n) % 100;
  const mod10 = n % 10;
  if (mod100 > 10 && mod100 < 20) return `${n} лет`;
  if (mod10 === 1) return `${n} год`;
  if (mod10 >= 2 && mod10 <= 4) return `${n} года`;
  return `${n} лет`;
}

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
        onClick={handleClick}
        aria-disabled={blocked}
        className={cn(
          'flex items-center gap-1.5 px-3 py-1.5 rounded-lg border transition-colors text-xs font-mono uppercase tracking-wider',
          blocked
            ? 'border-border-subtle/60 text-text-tertiary/50 cursor-pointer'
            : 'border-border-subtle text-text-tertiary hover:text-champagne hover:border-champagne/30 magnetic-btn',
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

/**
 * Кнопка «скачать график картинкой». Гость видит замок и подсказку, клик ведёт
 * на регистрацию (через onDownload, который сам решает гейт). Авторизованный —
 * скачивает чистый PNG текущего вида (без водяного знака).
 */
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
            ? 'border-border-subtle text-text-tertiary hover:text-champagne hover:border-champagne/30 magnetic-btn'
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

/**
 * Секция «График» страницы индикатора:
 *   тулбар (заголовок + кнопки CSV/Excel + переключатель прогноза) +
 *   сам IndicatorChart с правильными режим-зависимыми пропсами.
 *
 * Таблица данных и таблица прогноза идут отдельными секциями ниже —
 * этот компонент отвечает только за визуализацию ряда.
 */
export default function IndicatorChartSection({
  code,
  indicator,
  chartMode,
  safeViewMode,
  isPriceCategory,
  isHousingFamily,
  isPpiFamily,
  isCbrTermSliceFamily,
  isUnemploymentFamily,
  chartLoading,

  inflationResp,
  dataPoints,
  momDataPoints,
  quarterlyDataPoints,
  annualDataPoints,
  weeklyDataPoints,
  yoyDataPoints,
  qoqDataPoints,
  periodMonthlyDataPoints,
  periodWeeklyDataPoints,

  displayForecastData,
  quarterlyForecastData,
  annualForecastResp,
  yoyForecastData,
  qoqForecastData,
  periodMonthlyForecastData,
  periodWeeklyForecastData,

  forecastEnabled,
  showForecast,
  onToggleForecast,

  onChartData,
  onFullData,
  onRangeChange,
  emptyHint,

  onDownloadCsv,
  onDownloadExcel,
}) {
  const { blocked: downloadBlocked, isAuthed: downloadAuthed, historyYears } = useDownloadAccess();
  const guestHistoryHint = !downloadAuthed && !downloadBlocked && historyYears > 0
    ? `Гостям — последние ${ruYears(historyYears)}. Весь период истории — после входа`
    : null;
  const chartRef = useRef(null);

  // Скачивание графика картинкой. Единое правило по всему сайту:
  // гость → гейт регистрации (скачать нельзя вообще); зарегистрированный →
  // PNG текущего вида (режим + прогноз как на экране). Водяной знак
  // «forecasteconomy.com» стоит НА ВСЕХ выгружаемых картинках без исключений
  // (решение владельца 2026-07-02): любой скриншот, разошедшийся по сети,
  // работает на бренд.
  const handleDownloadImage = async () => {
    if (!downloadAuthed) {
      track(events.CHART_IMAGE_BLOCKED, { indicator: code, indicatorCategory: indicator?.category });
      window.dispatchEvent(new CustomEvent('fe:download-limit'));
      return;
    }
    const ok = await exportNodeToPng(chartRef.current, {
      filename: `${code}_${safeViewMode || chartMode || 'chart'}.png`,
      watermark: true,
    }).catch(() => false);
    if (ok) {
      track(events.CHART_IMAGE_DOWNLOAD, {
        indicator: code,
        indicatorCategory: indicator?.category,
        mode: safeViewMode || chartMode,
        forecast: forecastEnabled && showForecast,
      });
    }
  };
  const chartCpiData = chartSeriesForViewMode({
    chartMode,
    isUnemploymentFamily,
    dataPoints,
    momDataPoints,
    quarterlyDataPoints,
    annualDataPoints,
    weeklyDataPoints,
    yoyDataPoints,
    qoqDataPoints,
    periodWeeklyDataPoints,
    periodMonthlyDataPoints,
  });

  // Недельный режим — без прогноза (созвон 2026-06-11).
  const forecastData = chartMode === 'quarterly' ? quarterlyForecastData
    : chartMode === 'annual' ? annualForecastResp
      : chartMode === 'weekly' ? null
        : chartMode === 'yoy' ? yoyForecastData
          : chartMode === 'qoq' ? qoqForecastData
            : chartMode === 'period-weekly' ? periodWeeklyForecastData
              : chartMode === 'period-monthly' ? periodMonthlyForecastData
                : displayForecastData;

  const handleForecastToggle = () => {
    if (!forecastEnabled) return;
    onToggleForecast();
    track(events.FORECAST_TOGGLE, {
      show: !showForecast,
      indicator: code,
      indicatorCategory: indicator?.category,
    });
  };

  const handleForecastKeyDown = (e) => {
    if (forecastEnabled && (e.key === ' ' || e.key === 'Enter')) {
      e.preventDefault();
      handleForecastToggle();
    }
  };

  return (
    <section data-block="chart" className="mb-16">
      <div className="flex items-center justify-between mb-6 border-b border-border-subtle pb-4 flex-wrap gap-3">
        <div className="flex items-center gap-4">
          <Terminal className="w-4 h-4 text-champagne" />
          <span className="text-[11px] font-mono uppercase tracking-widest text-text-tertiary">
            {(isPriceCategory || isHousingFamily || isPpiFamily
              || isCbrTermSliceFamily || isUnemploymentFamily
              || chartMode !== 'cpi')
              ? 'График выбранного режима'
              : 'Динамика показателя'}
          </span>
        </div>

        <div className="flex items-center gap-3">
          <DownloadButton label="CSV" onDownload={onDownloadCsv} blocked={downloadBlocked} hint={guestHistoryHint} />
          <DownloadButton label="Excel" onDownload={onDownloadExcel} blocked={downloadBlocked} hint={guestHistoryHint} />
          <ImageButton onDownload={handleDownloadImage} authed={downloadAuthed} />

          <div className="relative group/help">
            <Link
              to="/methodology"
              aria-label="Как рассчитывается прогноз"
              onClick={() => track(events.METHODOLOGY_CLICK, { indicator: code, indicatorCategory: indicator?.category })}
              className="text-text-tertiary hover:text-champagne transition-colors"
            >
              <HelpCircle className="w-4 h-4" />
            </Link>
            <div className="absolute top-full right-0 mt-2 px-3 py-2 rounded-xl bg-obsidian border border-border-subtle text-xs text-text-secondary whitespace-nowrap opacity-0 group-hover/help:opacity-100 transition-opacity duration-200 pointer-events-none shadow-xl z-50">
              Хотите узнать, как рассчитывается прогноз?
            </div>
          </div>

          <div className="relative group">
            <label className={cn(
              'flex items-center gap-3 select-none',
              forecastEnabled ? 'cursor-pointer' : 'cursor-not-allowed opacity-50',
            )}>
              <span className="text-[10px] font-mono uppercase tracking-widest text-text-tertiary group-hover:text-text-secondary transition-colors">
                Прогноз
              </span>
              <div
                role="switch"
                aria-checked={forecastEnabled && showForecast}
                aria-label="Показать прогноз"
                tabIndex={forecastEnabled ? 0 : -1}
                onClick={handleForecastToggle}
                onKeyDown={handleForecastKeyDown}
                className={cn(
                  'relative w-10 h-5 rounded-full transition-colors duration-300',
                  forecastEnabled ? 'cursor-pointer' : 'cursor-not-allowed',
                  forecastEnabled && showForecast
                    ? 'bg-champagne/30'
                    : 'bg-obsidian-lighter border border-border-subtle',
                )}
              >
                <div className={cn(
                  'absolute top-[2px] left-[2px] w-4 h-4 rounded-full transition-transform duration-300',
                  forecastEnabled && showForecast ? 'translate-x-5 bg-champagne' : 'translate-x-0 bg-text-tertiary',
                )} />
              </div>
            </label>
            {!forecastEnabled && (
              <div className="absolute top-full right-0 mt-2 px-3 py-2 rounded-xl bg-obsidian border border-border-subtle text-xs text-text-secondary whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none shadow-xl z-50">
                Прогноз для этого режима недоступен
              </div>
            )}
          </div>
        </div>
      </div>

      {chartLoading ? (
        <ChartSkeleton />
      ) : (
        <div ref={chartRef} className="relative overflow-hidden rounded-[2rem]">
          <IndicatorChart
            key={`${indicator?.code}-${chartMode}`}
            mode={
              isUnemploymentFamily
              || ['quarterly', 'annual', 'weekly', 'index', 'yoy', 'qoq', 'mom', 'real',
                'period-weekly', 'period-monthly'].includes(chartMode)
              || (isCbrTermSliceFamily && chartMode === 'level')
                ? 'cpi'
                : chartMode
            }
            inflation={inflationResp}
            cpiData={chartCpiData}
            forecastData={forecastData}
            showForecast={forecastEnabled && showForecast}
            onChartData={onChartData}
            onFullData={onFullData}
            onRangeChange={onRangeChange}
            referenceLineY={(isPriceCategory || isHousingFamily || isPpiFamily) && chartMode !== 'index' ? 0 : null}
            cpiChartTitle={chartTitle({
              chartMode, isPriceCategory, isHousingFamily, isPpiFamily,
              isCbrTermSliceFamily, isUnemploymentFamily,
              indicator, safeViewMode,
            })}
            levelTooltipLabel={levelTooltipLabel({
              chartMode, isPriceCategory, isHousingFamily, isPpiFamily,
              isCbrTermSliceFamily,
              indicator,
            })}
            forecastTooltipLabel={forecastTooltipLabel({ chartMode, indicator })}
            emptyHint={emptyHint}
            dateFormat={resolveDateFormat({ chartMode, frequency: indicator?.frequency, safeViewMode })}
            unit={chartMode === 'index' ? 'индекс' : ((isPpiFamily || isHousingFamily) && chartMode !== 'index' ? '%' : (indicator?.unit || '%'))}
            rangePreset={rangePresetFor({ chartMode, indicator })}
            chartMode={chartMode}
            indicatorCode={code}
            indicatorCategory={indicator?.category}
          />
        </div>
      )}
    </section>
  );
}
