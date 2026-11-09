// Детальная страница показателя региона: /russia/region/{slug}/{code}
// График + рейтинг среди регионов + сравнение с РФ + таблица значений +
// выгрузка CSV/Excel/PNG (только для зарегистрированных, PNG — без watermark,
// см. правило 2026-07-08 в IndicatorChartSection.jsx).
import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  Trophy, Table2, ChevronDown, ArrowUpRight,
  Download, Image as ImageIcon, GitCompare, Check,
} from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import { getSiteOrigin } from '../lib/siteOrigin';
import { completeDataset } from '../lib/datasetJsonLd';
import { mountJsonLd } from '../lib/jsonLd';
import {
  useRegionIndicator, useRegionIndicatorMonthly, useRegionsLanding,
  formatRegionValue, shortUnit, yearDelta,
} from '../lib/regionsApi';
import DeltaBadge from '../components/DeltaBadge';
import { indicatorPolarity } from '../lib/deltaTone';
import { prioritizeIndicators, formatRegionNumber, isPercentUnit, formatRegionWithUnit, glueNumbers, unitLabel, NBSP } from '../lib/regionUi';
import RegionAnnualChart from '../components/RegionAnnualChart';
import GroupedSiblings, { CompareLines, AreaCalc, CopyForClient, DiscontinuedNote, PairSwitch, RangeChips } from '../components/regions/MonthlyPriceParts';
import {
  bigRub, changeOverMonths, compareRows, guessPriceGroup, pairsFirst, roundBig, sliceMonths, yearlyCost, isRubPerUnit, perUnitPrice, pickField, priceText, shortPriceName, signedPct, unitSuffix, ymLabel, ymLabelFrom,
} from '../lib/z2Price';
import { R6RussiaLine, R6RankCaption, R6SinceStart, R6RatingExtras, R6StaleNote } from '../components/regions/R6Annual';
import { gapText, isYearsUnit } from '../lib/r6Annual';
import DownloadMenu from '../components/regions/DownloadMenu';
import ApiRetryBanner from '../components/ApiRetryBanner';
import LoadingNote from '../components/LoadingNote';
import Breadcrumbs from '../components/Breadcrumbs';
import CabinetActionsSlot from '../components/CabinetActionsSlot';
import { regionIndicatorSubject } from '../lib/cabinetSubjects';
import { SkeletonBox } from '../components/Skeleton';
import Chip from '../components/Chip';
import { useAuth } from '../context/authContext';
import { exportTable } from '../lib/api';
import { exportNodeToPng } from '../lib/chartImage';
import { track, events } from '../lib/track';
import { regionIndicatorTrail } from '../lib/breadcrumbs';
import {
  regionIndicatorPath,
  regionRatingPath,
  russiaIndicatorPath,
} from '../lib/sitePaths';
import { useLocale } from '../i18n';
import '../styles/platform-pages.css';
import '../styles/regions-w4.css';
import '../styles/k6-country.css';

const R6_SIBS_FIRST = 8;

// Годовой ряд → изменения год к году, % (кнопка YoY / «% г/г»).
function toYoYSeries(series) {
  if (!series?.length) return [];
  const byYear = new Map(series.map(p => [p.year, p.value]));
  return series
    .filter(p => {
      const prev = byYear.get(p.year - 1);
      return prev != null && prev !== 0;
    })
    .map(p => {
      const prev = byYear.get(p.year - 1);
      return { year: p.year, value: +(((p.value - prev) / Math.abs(prev)) * 100).toFixed(2) };
    });
}

// В-20 (CTO-аудит 2026-07-06): для знакопеременных рядов (сальдо миграции
// и т.п.) «% г/г» от базы, переходящей через ноль, — нечитаемый процент
// (тысячи % и перевороты знака). Тоггл для таких рядов не показываем.
function isNegativeCapable(series) {
  return Array.isArray(series) && series.some(p => p?.value != null && p.value < 0);
}

function StatCell({ label, children, wide = false }) {
  return (
    <div className={`min-w-0 rounded-2xl p-3 sm:p-3.5 fe-glass-lite${wide ? ' max-sm:col-span-2' : ''}`}>
      <div className="text-xs font-medium leading-snug text-text-secondary">{label}</div>
      <div className="fe-num mt-1 text-[15px] font-semibold leading-tight text-text-primary">
        {children}
      </div>
    </div>
  );
}

// Максимум и минимум одного показателя — с одинаковой точностью (крупные величины целыми).
function statValue(value, { max, min }) {
  return Math.max(Math.abs(max), Math.abs(min)) >= 1000 ? Math.round(value) : value;
}

/** Название месяца на языке интерфейса (ru: «январь», en: «January»). */
function monthName(month, locale) {
  return new Date(2000, month - 1, 1).toLocaleDateString(locale === 'en' ? 'en-US' : 'ru-RU', { month: 'long' });
}

const ABORTION_SIBLING = {  'beremennosti-s-abortivnym-ishodom-na-100-rodov': {
    code: 'beremennosti-s-abortivnym-ishodom-na-1000-zhenschin',
    labelKey: 'regions.ind.abortionPer1000',
  },
  'beremennosti-s-abortivnym-ishodom-na-1000-zhenschin': {
    code: 'beremennosti-s-abortivnym-ishodom-na-100-rodov',
    labelKey: 'regions.ind.abortionPer100',
  },
};

/** `renderActions` — необязательный слот кнопок кабинета («В избранное», «Следить»); их рисует зона кабинета. */
export default function RegionIndicatorPage({ renderActions = null } = {}) {
  const { t, locale } = useLocale();
  const { slug, code } = useParams();
  // Месячный ряд тянется только для показателей, у которых он есть: годовой
  // запрос отдаёт 404 «Нет месячных данных» — по нему и выключаем повторные попытки.
  const monthly = useRegionIndicatorMonthly(slug, code);
  const isMonthly = monthly.data?.frequency === 'monthly' && monthly.data?.series?.length > 0;
  const { data, isError, refetch, isFetching } = useRegionIndicator(slug, code);
  const [showTable, setShowTable] = useState(false);
  const [sibsOpen, setSibsOpen] = useState(false);
  const [showRussia, setShowRussia] = useState(true);
  const [showYoYRaw, setShowYoY] = useState(false);
  // В-20: для знакопеременных рядов режим «% г/г» недоступен.
  const showYoY = showYoYRaw && !isNegativeCapable(data?.series);
  const [exporting, setExporting] = useState(false);
  const [rangeM, setRangeM] = useState(60);
  const { isAuthed } = useAuth();
  const chartRef = useRef(null);

  // Сравнение с другим регионом: вторая линия на графике.
  const [compareSlug, setCompareSlug] = useState('');
  const landing = useRegionsLanding();
  const compare = useRegionIndicator(compareSlug || null, compareSlug ? code : null);
  const compareMonthly = useRegionIndicatorMonthly(
    compareSlug || null, compareSlug ? code : null, !!compareSlug && isMonthly,
  );
  // Запасной путь сравнения с Москвой, пока API не отдаёт compare: тот же показатель по Москве (запрос общий с кэшем).
  const moskvaMonthly = useRegionIndicatorMonthly(
    slug !== 'moskva' ? 'moskva' : null, slug !== 'moskva' ? code : null, isMonthly,
  );
  const regionOptions = useMemo(() => {
    if (!landing.data) return [];
    return landing.data.districts.flatMap(d => d.regions.map(r => ({ slug: r.slug, name: r.name })))
      .filter(r => r.slug !== slug)
      .sort((a, b) => a.name.localeCompare(b.name, locale === 'en' ? 'en' : 'ru'));
  }, [landing.data, slug, locale]);

  // Выгрузка данных региона — только для зарегистрированных: гостю показываем
  // гейт регистрации (то же окно, что в макроблоке). PNG — без watermark.
  const requireAuth = (blockedEvent) => {
    if (isAuthed) return true;
    track(blockedEvent, { indicator: `region:${slug}:${code}` });
    window.dispatchEvent(new CustomEvent('fe:download-limit'));
    return false;
  };

  const handleExportTable = async (format) => {
    const evt = format === 'csv' ? events.DOWNLOAD_CSV : events.DOWNLOAD_EXCEL;
    if (!requireAuth(events.DOWNLOAD_LIMIT_HIT) || !activeSeries.length || exporting) return;
    setExporting(true);
    try {
      const filename = `${slug}_${code}.${format}`;
      const { blob } = await exportTable({
        format,
        filename,
        valueLabel: `${active.indicator.name} (${active.indicator.unit})`,
        points: activeSeries.map(p => ({
          date: isMonthly ? `${p.year}-${String(p.month).padStart(2, '0')}-01` : `${p.year}-01-01`,
          actual: p.value,
          forecast: null,
        })),
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(url), 100);
      track(evt, { indicator: `region:${slug}:${code}`, region: slug });
    } catch {
      // Сетевые сбои экспорта не должны ронять страницу.
    } finally {
      setExporting(false);
    }
  };

  const handleExportPng = async () => {
    if (!requireAuth(events.CHART_IMAGE_BLOCKED) || exporting) return;
    setExporting(true);
    const ok = await exportNodeToPng(chartRef.current, {
      filename: `${slug}_${code}.png`,
      watermark: false,
    }).catch(() => false);
    setExporting(false);
    if (ok) track(events.CHART_IMAGE_DOWNLOAD, { indicator: `region:${slug}:${code}`, region: slug });
  };

  // Активный ряд: месячный, если по показателю он пришёл; иначе годовой.
  // Годовой запрос для месячных показателей отдаёт 404 — ждать его нельзя,
  // карточка рендерится от активного ряда. Все производные — только ниже.
  const active = isMonthly ? monthly.data : data;
  const activeSeries = active?.series || [];
  const regionName = active?.region?.name;
  const indName = active?.indicator?.name;
  const last = activeSeries[activeSeries.length - 1];
  const first = activeSeries[0];
  const lastLabel = last
    ? (isMonthly ? `${monthName(last.month, locale)} ${last.year}` : String(last.year))
    : '';

  // Карточка рендерится от активного ряда (месячного или годового).
  const cardReady = isMonthly ? !!active : !!data;
  const viewTrackedRef = useRef('');
  useEffect(() => {
    if (!active?.indicator) return;
    const key = `${slug}:${code}`;
    if (viewTrackedRef.current === key) return;
    viewTrackedRef.current = key;
    track(events.REGION_INDICATOR_VIEW, {
      indicator: `region:${slug}:${code}`,
      region: slug,
      code,
    });
  }, [active?.indicator, slug, code]);

  useDocumentMeta(active && last ? {
    title: t(isMonthly ? 'regions.ind.metaTitleMonthly' : 'regions.ind.metaTitle', {
      name: indName,
      region: regionName,
      value: formatRegionValue(last.value),
      unit: shortUnit(active.indicator.unit),
      year: isMonthly ? lastLabel : last.year,
    }),
    description: t(isMonthly ? 'regions.ind.metaDescMonthly' : 'regions.ind.metaDesc', {
      name: indName,
      region: regionName,
      value: formatRegionValue(last.value),
      unit: active.indicator.unit,
      year: isMonthly ? lastLabel : last.year,
      from: first.year,
      rank: active.rank
        ? t(
          active.rank.rank_as_achievement
            ? 'regions.ind.metaRankAchieve'
            : 'regions.ind.metaRankNeutral',
          { position: active.rank.position, total: active.rank.total },
        )
        : '.',
    }),
    path: regionIndicatorPath(slug, code),
  } : null);

  useEffect(() => {
    if (!active || !last) return;
    const jsonLd = completeDataset({
      '@context': 'https://schema.org',
      '@type': 'Dataset',
      name: `${indName} — ${regionName}`,
      description: t('regions.ind.jsonLdDesc', {
        name: indName,
        unit: active.indicator.unit,
        region: regionName,
        from: first.year,
        to: last.year,
      }),
      temporalCoverage: `${first.year}/${last.year}`,
      spatialCoverage: regionName,
      creator: { '@type': 'Organization', name: t('regions.ind.creatorRosstat') },
      publisher: { '@type': 'Organization', name: 'Forecast Economy', url: getSiteOrigin() },
    }, locale);
    return mountJsonLd(jsonLd);
  }, [active, indName, regionName, first, last, locale, t]);

  const delta = last && activeSeries.length > 1
    ? yearDelta(last.value, activeSeries[activeSeries.length - 2].value)
    : null;

  const annualSibs = useMemo(() => (isMonthly ? (active?.siblings || []) : prioritizeIndicators(active?.siblings || [])), [isMonthly, active?.siblings]);
  const prevPoint = activeSeries.length > 1 ? activeSeries[activeSeries.length - 2] : null;
  const absDelta = !isMonthly && delta && prevPoint && (isYearsUnit(active?.indicator?.unit) || isPercentUnit(active?.indicator?.unit))
    ? gapText(last.value, prevPoint.value, active.indicator.unit, locale)
    : null;

  const stats = useMemo(() => {
    if (!activeSeries.length) return null;
    const values = activeSeries.map(p => p.value);
    const max = Math.max(...values);
    const min = Math.min(...values);
    const at = (idx) => {
      const p = activeSeries[idx];
      return isMonthly ? monthName(p.month, locale) + ' ' + p.year : p.year;
    };
    return {
      max, maxAt: at(values.indexOf(max)),
      min, minAt: at(values.indexOf(min)),
    };
  }, [activeSeries, isMonthly, locale]);

  // «Лучший / худший год» там, где понятно, что хорошо (безработица ниже — лучше), иначе просто наибольшее и наименьшее.
  const extremePolarity = indicatorPolarity(indName, code);
  // Денежные и штучные уровни (номинальная зарплата, доход, число жителей) почти всегда растут,
  // поэтому «лучший год» — это просто последний, а «худший» — первый. Оценку «лучше/хуже» оставляем
  // процентным показателям (безработица, рост), а у уровней пишем нейтрально «наибольшее/наименьшее».
  const isLevel = !isPercentUnit(active?.indicator?.unit);
  const extremeKeys = extremePolarity === 'up-good' && isLevel
    ? { max: 'w6f.reg.highestYear', min: 'w6f.reg.lowestYear' }
    : extremePolarity === 'up-good'
    ? { max: 'w6f.reg.bestYear', min: 'w6f.reg.worstYear' }
    : extremePolarity === 'up-bad'
      ? { max: 'w6f.reg.worstYear', min: 'w6f.reg.bestYear' }
      : { max: 'w6f.reg.highestYear', min: 'w6f.reg.lowestYear' };

  const tableRows = useMemo(
    () => (activeSeries.length ? [...activeSeries].reverse() : []),
    [activeSeries],
  );

  const abortion = ABORTION_SIBLING[code];

  // Месячные цены: поля Z1 читаем с запасом — нет поля, страница ведёт себя как раньше.
  const isPrice = isMonthly && (/^(Средняя цена|Average (consumer )?price)/i.test(indName || '') || isRubPerUnit(active.indicator.unit));
  const shortName = isMonthly
    ? (pickField(active, 'short_name') || (isPrice ? shortPriceName(indName, active.indicator.unit) : null))
    : null;
  const displayName = shortName || indName;
  const titleParts = (() => {
    const m = String(displayName || '').match(/^(.{20,}?)\s+[—–]\s+(.{25,})$/);
    return m ? [m[1], m[2]] : null;
  })();
  // Нет флага от API — считаем снятым ряд, чья последняя точка старше 12 месяцев.
  const flagged = isMonthly ? pickField(active, 'is_discontinued') : null;
  const now = new Date();
  const staleByDate = isMonthly && last && (now.getFullYear() * 12 + now.getMonth() + 1) - (last.year * 12 + last.month) > 12;
  const discontinued = isMonthly && (flagged === null ? !!staleByDate : flagged === true);
  const priceGroup = isMonthly
    ? (pickField(active, 'price_group') || (isPrice ? guessPriceGroup(indName, active.indicator.unit) : null))
    : null;
  const priceSuffix = isPrice ? unitSuffix(active.indicator.unit) : '';
  const rubCaption = isPrice && priceSuffix && locale === 'ru' ? `₽ ${priceSuffix}` : '';
  const perUnit = isPrice && last ? perUnitPrice(active.indicator.unit, last.value) : null;
  const siblingsView = isMonthly && isPrice
    ? pairsFirst((active?.siblings || []).map(sb => ({
      ...sb,
      short_name: sb.short_name || shortPriceName(sb.name, sb.unit),
      price_group: sb.price_group || guessPriceGroup(sb.name, sb.unit),
    })), displayName)
    : (active?.siblings || []);
  const rfLast = active?.russia_series?.[active.russia_series.length - 1];
  const mskSeries = moskvaMonthly.data?.series;
  const mskLast = mskSeries?.length ? mskSeries[mskSeries.length - 1] : null;
  const compareData = isMonthly
    ? {
      ...(active.compare || {}),
      russia: active.compare?.russia
        || (rfLast ? { value: rfLast.value, month: rfLast.year * 100 + rfLast.month } : null),
      moskva: active.compare?.moskva || (mskLast ? { value: mskLast.value, month: mskLast.year * 100 + mskLast.month } : null),
    }
    : null;
  const lastMonthLabel = isMonthly
    ? (ymLabel(pickField(active, 'last_month'), locale) || lastLabel)
    : '';
  const compareList = isMonthly && !discontinued && last
    ? compareRows(compareData, slug, last.value)
    : [];
  const lastYm = last ? last.year * 100 + last.month : null;
  const monthlyExtremes = (() => {
    if (!isMonthly || activeSeries.length < 24) return null;
    let mx = activeSeries[0];
    let mn = activeSeries[0];
    for (const pt of activeSeries) {
      if (pt.value > mx.value) mx = pt;
      if (pt.value < mn.value) mn = pt;
    }
    return { mx, mn };
  })();
  const yoyByKey = isMonthly
    ? new Map(activeSeries.map((pt, i, arr) => {
      const prev = i >= 12 ? arr[i - 12] : null;
      const ok = prev && prev.value && (pt.year * 12 + pt.month) - (prev.year * 12 + prev.month) === 12;
      return [pt.year * 12 + pt.month, ok ? ((pt.value - prev.value) / Math.abs(prev.value)) * 100 : null];
    }))
    : null;
  const periodChanges = isMonthly
    ? [
      { key: 'z2.yearAgo', ch: changeOverMonths(activeSeries, 12) },
      { key: 'z2.fiveYearsAgo', ch: changeOverMonths(activeSeries, 60) },
    ].filter((x) => x.ch)
    : [];

  const yearSum = isPrice && last ? yearlyCost(last.value, active.indicator.unit) : null;
  const shareText = isPrice && last
    ? [
      t('r5a.share', { name: displayName, region: regionName, price: priceText(last.value, active.indicator.unit, locale), unit: priceSuffix, month: lastLabel }).replace(/\s+\./, '.'),
      compareList.length ? t('r5a.shareCmp', { russia: compareData?.russia ? priceText(compareData.russia.value, active.indicator.unit, locale) : '—', moskva: compareData?.moskva ? priceText(compareData.moskva.value, active.indicator.unit, locale) : '—' }) : '',
      t('r5a.shareSrc'),
      typeof window !== 'undefined' ? window.location.href.split('#')[0] : '',
    ].filter(Boolean).join(' ')
    : '';
  const chartMonths = isMonthly ? rangeM : 0;

  return (
    <div className="fe-data-page mx-auto w-full max-w-7xl px-4 pb-12 pt-24 sm:px-6 sm:pb-16">
      <Breadcrumbs
        items={regionIndicatorTrail(
          regionName || '…',
          slug,
          displayName || '…',
          code,
        )}
      />

      {isError && !cardReady && (
        <ApiRetryBanner onRetry={refetch} isFetching={isFetching} className="mb-6">
          {t('pgui.regions.indError')}
        </ApiRetryBanner>
      )}
      {!cardReady && !isError && (
        <div role="status" aria-busy="true" aria-label={t('common.loading')}>
          <LoadingNote onRefresh={() => refetch()} className="mb-4" />
          <SkeletonBox className="mb-2 mt-6 h-4 w-40" />
          <SkeletonBox className="mb-5 h-8 w-full max-w-2xl sm:h-9" />
          <SkeletonBox className="mb-6 h-9 w-64 sm:h-10" />
          <SkeletonBox className="mb-4 h-[392px] rounded-xl sm:h-[398px]" />
          <div className="mb-6 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {[0, 1, 2, 3].map((i) => <SkeletonBox key={i} className="h-[64px] rounded-xl" />)}
          </div>
        </div>
      )}

      {cardReady && active && !last && (
        <div className="rounded-2xl p-6 text-center text-sm text-text-secondary fe-glass-lite">
          {t('pgui.regions.indNoData')}
        </div>
      )}

      {cardReady && active && last && (
        <>
          <div className="fe-data-header">
            <div className="mb-2 flex min-w-0 flex-wrap items-center gap-x-2 gap-y-0.5 text-sm">
              <span className="font-medium text-champagne-ink">{regionName}</span>
              {active.indicator.section_name && (
                <span className={`min-w-0 pl-2 text-text-secondary${isMonthly ? ' max-sm:hidden' : ''}`}>{active.indicator.section_name}</span>
              )}
              <CabinetActionsSlot subject={regionIndicatorSubject(slug, code, indName, regionName)} renderActions={renderActions} />
            </div>
            <h1 lang={locale} className="fe-title-wrap mb-5 w-full font-display text-[1.35rem] font-bold leading-tight text-text-primary sm:text-2xl">
              {!isMonthly && titleParts ? (
                <>
                  {titleParts[0]}
                  <span className="r6c-title-sub">{`— ${titleParts[1]}`}</span>
                </>
              ) : displayName}
            </h1>
            {shortName && shortName !== indName && (
              <p className="z2p-caption" lang={locale}>{indName}</p>
            )}
            {abortion && (
              <p className="mt-1 text-xs text-text-secondary">
                {t('regions.ind.abortionLead')}
                {' '}
                <Link
                  to={regionIndicatorPath(slug, abortion.code)}
                  className="text-champagne-ink hover:underline"
                >
                  {t(abortion.labelKey)}
                </Link>
                .
              </p>
            )}

            <div className="mt-4 flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <span className={`fe-num whitespace-nowrap text-3xl font-bold ${discontinued ? 'z2p-hero-dead' : 'text-text-primary'}`}>
                {isPrice && priceSuffix ? priceText(last.value, active.indicator.unit, locale) : formatRegionWithUnit(last.value, active.indicator.unit, locale)}
              </span>
              {priceSuffix && <span className="z2p-hero-unit">{priceSuffix}</span>}
              {!isMonthly && !unitLabel(active.indicator.unit, locale) && active.indicator.unit && (
                <span className="r6c-unit-note" lang={locale}>{active.indicator.unit}</span>
              )}
              {!isPrice && <span className="text-sm text-text-secondary">{lastLabel}</span>}
              {delta && !discontinued && (
                <DeltaBadge
                  delta={delta.up || delta.down ? delta.pct : 0}
                  polarity={indicatorPolarity(indName)}
                  className="text-sm"
                >
                  {absDelta ? `${absDelta.text} ${t('regions.ind.deltaYoYAbs')}` : isMonthly && Math.abs(delta.pct) < 0.05 ? t('r5a.flatMonth') : t(isMonthly ? 'regions.ind.deltaMoM' : 'regions.ind.deltaYoY', {
                    pct: `${delta.up ? '+' : delta.down ? '\u2212' : ''}${Math.abs(delta.pct).toFixed(1).replace('.', locale === 'en' ? '.' : ',')}`,
                  }).replace('%', `${NBSP}%`)}
                </DeltaBadge>
              )}
            </div>
            {perUnit && (
              <p className="z2p-per-unit fe-num">
                {t('z2.perUnit', { price: `${formatRegionNumber(perUnit.value, active.indicator.unit, locale)}${NBSP}₽`, word: perUnit.word })}
              </p>
            )}
            {isPrice && !discontinued && <AreaCalc value={last.value} unit={active.indicator.unit} />}
            {isPrice && <p className="r5a-hero-month">{t('r5a.dataFor', { month: lastLabel })}</p>}
            {yearSum && !discontinued && <p className="r5a-year fe-num">{t('r5a.perYear', { sum: bigRub(yearSum, locale) })}</p>}
            {!isMonthly && active.russia_series?.length > 0 && (
              <R6RussiaLine value={last.value} year={last.year} series={active.russia_series} unit={active.indicator.unit} locale={locale} t={t} />
            )}
            {discontinued && <DiscontinuedNote />}
            <CompareLines rows={compareList} unit={active.indicator.unit} lastMonth={lastYm} />
            {isPrice && !discontinued && <CopyForClient text={shareText} />}
          </div>

          {isPrice && !discontinued && (
            <PairSwitch siblings={siblingsView} currentName={displayName} currentValue={last.value} unit={active.indicator.unit} slug={slug} />
          )}

          <div id="chart" data-block="region-chart" className="fe-panel mb-4 w-full min-w-0 max-w-full scroll-mt-24 rounded-3xl p-3 sm:p-4" ref={chartRef}>
            <div className="flex flex-col gap-2 mb-2 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
              <div className="text-sm text-text-secondary">
                {isMonthly
                  ? t('w4.ind.rangeMonthly', { from: (sliceMonths(activeSeries, chartMonths)[0] || first).year, to: last.year, unit: rubCaption || unitLabel(active.indicator.unit, locale) || active.indicator.unit })
                  : `${first.year}–${last.year}, ${showYoY ? t('w4.ind.yoyUnit') : (unitLabel(active.indicator.unit, locale) || active.indicator.unit)}`}
              </div>
              <div className="flex flex-wrap items-center gap-1.5" data-no-export="true">
                {isMonthly && <RangeChips value={rangeM} onChange={setRangeM} total={activeSeries.length} />}
                <label
                  className={`fe-tap inline-flex w-full min-w-0 max-w-full items-center gap-1.5 rounded-xl fe-glass-2 px-3 py-1 text-sm transition-colors sm:w-auto ${
                    compareSlug
                      ? 'text-[#5B7DA8]'
                      : 'text-text-secondary hover:text-text-secondary'
                  }`}
                >
                  <GitCompare size={12} className="shrink-0 opacity-70" aria-hidden />
                  <select
                    value={compareSlug}
                    onChange={(e) => {
                      setCompareSlug(e.target.value);
                      if (e.target.value) track(events.REGION_COMPARE_ADD, { region: slug, compare: e.target.value, indicator: code });
                    }}
                    aria-label={t('regions.ind.compareOther')}
                    className="min-w-0 flex-1 cursor-pointer appearance-auto border-0 bg-transparent p-0 pr-0.5 text-sm text-inherit focus:outline-none"
                  >
                    <option value="">{t('regions.ind.comparePlaceholder')}</option>
                    {regionOptions.map(r => (
                      <option key={r.slug} value={r.slug}>{r.name}</option>
                    ))}
                  </select>
                </label>
                {active.russia_series?.length > 0 && (
                  <Chip active={showRussia} onClick={() => setShowRussia(v => !v)}>
                    {isMonthly
                      ? (
                        <span className="z2p-russia-chip">
                          {showRussia && <Check size={13} aria-hidden="true" />}
                          {t('z2.russiaLine')}
                        </span>
                      )
                      : (showRussia ? t('regions.ind.vsRussia') : t('regions.ind.addRussia'))}
                  </Chip>
                )}
                {!isMonthly && data.series.length > 2 && !isNegativeCapable(data.series) && (
                  <Chip active={showYoY} onClick={() => setShowYoY(v => !v)} title={t('regions.ind.yoyTitle')}>
                    {t('w4.ind.yoyBtn')}
                  </Chip>
                )}
                <DownloadMenu
                  disabled={exporting}
                  items={[
                    { key: 'csv', label: 'CSV', hint: t('x4.download.csvHint'), icon: Download, onSelect: () => handleExportTable('csv') },
                    { key: 'xlsx', label: 'Excel', hint: t('x4.download.xlsxHint'), icon: Download, onSelect: () => handleExportTable('xlsx') },
                    { key: 'png', label: t('x4.download.png'), hint: t('x4.download.pngHint'), icon: ImageIcon, onSelect: handleExportPng },
                  ]}
                />
              </div>
            </div>
            <RegionAnnualChart
              frequency={isMonthly ? 'monthly' : 'annual'}
              series={isMonthly ? sliceMonths(activeSeries, chartMonths) : (showYoY ? toYoYSeries(data.series) : data.series)}
              russiaSeries={showRussia
                ? (isMonthly
                  ? sliceMonths(active.russia_series, chartMonths)
                  : (showYoY ? toYoYSeries(data.russia_series) : data.russia_series))
                : null}
              compareSeries={compareSlug
                ? (isMonthly
                  ? (sliceMonths(compareMonthly.data?.series, chartMonths) || null)
                  : (showYoY ? toYoYSeries(compare.data?.series) : (compare.data?.series || null)))
                : null}
              compareName={compareSlug ? (compare.data?.region?.name || '') : ''}
              unit={showYoY ? t('w4.ind.yoyShort') : (unitLabel(active.indicator.unit, locale) || active.indicator.unit)}
              regionName={regionName}
              axisUnit={isMonthly ? (rubCaption || unitLabel(active.indicator.unit, locale) || active.indicator.unit) : ''}
              yearTicks={isMonthly}
              height={300}
            />
            {compareSlug && isMonthly && compareMonthly.data && (
              <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-text-secondary px-1" data-no-export="true">
                <span className="inline-flex items-center gap-1.5">
                  <span className="inline-block w-4 h-0.5 rounded bg-champagne" />
                  {regionName}
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="inline-block w-4 h-0.5 rounded" style={{ backgroundColor: '#5B7DA8' }} />
                  {compareMonthly.data.region.name}
                </span>
                <button onClick={() => setCompareSlug('')} className="fe-tap-inline text-text-secondary underline hover:text-text-primary">
                  {t('regions.ind.removeCompare')}
                </button>
              </div>
            )}
            {compareSlug && !isMonthly && compare.data && (
              <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-text-secondary px-1" data-no-export="true">
                <span className="inline-flex items-center gap-1.5">
                  <span className="inline-block w-4 h-0.5 rounded bg-champagne" />
                  {regionName}
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="inline-block w-4 h-0.5 rounded" style={{ backgroundColor: '#5B7DA8' }} />
                  {compare.data.region.name}
                </span>
                <button onClick={() => setCompareSlug('')} className="fe-tap-inline text-text-secondary underline hover:text-text-primary">
                  {t('regions.ind.removeCompare')}
                </button>
              </div>
            )}
            {!isMonthly && <R6StaleNote lastYear={last.year} t={t} />}
            {isPrice && !discontinued && (
              <p className="z2p-source" lang={locale}>{t('r2z2.source', { month: lastMonthLabel })}</p>
            )}
            </div>

          <div className="mb-6 grid grid-cols-2 gap-2.5 sm:grid-cols-4">
            {active.rank?.position && (
              <StatCell label={
                t(
                  active.rank.rank_as_achievement
                    ? 'regions.ind.rankAchieve'
                    : 'regions.ind.rankNeutral',
                  { year: active.rank.year },
                )
              }
              >
                <span className="inline-flex items-center gap-1.5">
                  {/* Кубок только у тройки лидеров: у последнего места он выглядел насмешкой. */}
                  {active.rank.rank_as_achievement && active.rank.position <= 3 && (
                    <Trophy size={14} className="text-champagne-ink" />
                  )}
                  {active.rank.position}
                  {' '}
                  {t('regions.ind.of')}
                  {' '}
                  {active.rank.total}
                </span>
                <R6RankCaption position={active.rank.position} total={active.rank.total} t={t} />
              </StatCell>
            )}
            {isMonthly && periodChanges.map(({ key, ch }) => (
              <StatCell key={key} label={t(key, { month: ymLabelFrom(ch.from.year * 100 + ch.from.month, locale) })}>
                {signedPct(ch.pct, locale)}
                {isPrice && <span className="r5a-stat-was">{t('r5a.was', { value: priceText(roundBig(ch.from.value), active.indicator.unit, locale) })}</span>}
              </StatCell>
            ))}
            {stats && !isMonthly && (
              <>
                <StatCell label={t(extremeKeys.max, { year: stats.maxAt })}>
                  {formatRegionWithUnit(statValue(stats.max, stats), active.indicator.unit, locale)}
                </StatCell>
                <StatCell label={t(extremeKeys.min, { year: stats.minAt })}>
                  {formatRegionWithUnit(statValue(stats.min, stats), active.indicator.unit, locale)}
                </StatCell>
              </>
            )}
            {monthlyExtremes && (
              <>
                <StatCell label={t(monthlyExtremes.mx === last || (monthlyExtremes.mx.year === last.year && monthlyExtremes.mx.month === last.month) ? 'r5a.record' : 'r2z2.statMax', { month: ymLabel(monthlyExtremes.mx.year * 100 + monthlyExtremes.mx.month, locale) })}>
                  {isPrice ? priceText(roundBig(monthlyExtremes.mx.value), active.indicator.unit, locale) : formatRegionWithUnit(monthlyExtremes.mx.value, active.indicator.unit, locale)}
                </StatCell>
                <StatCell label={t('r2z2.statMin', { month: ymLabel(monthlyExtremes.mn.year * 100 + monthlyExtremes.mn.month, locale) })}>
                  {isPrice ? priceText(roundBig(monthlyExtremes.mn.value), active.indicator.unit, locale) : formatRegionWithUnit(monthlyExtremes.mn.value, active.indicator.unit, locale)}
                </StatCell>
              </>
            )}
            {!monthlyExtremes && !isMonthly && first.year !== last.year && (
              <StatCell label={t('r6c.sinceStart', { year: first.year })}>
                <R6SinceStart first={first} last={last} unit={active.indicator.unit} locale={locale} t={t} />
              </StatCell>
            )}
            {!monthlyExtremes && (isMonthly || first.year === last.year) && (
              <StatCell label={t('regions.ind.period')} wide={isMonthly}>
                {first.year}–{last.year}
              </StatCell>
            )}
          </div>

          {active.rank?.top?.length > 0 && (
            <div data-block="region-rating" className="mb-6 rounded-3xl p-4 fe-glass-lite">
              <h2 className="text-sm font-semibold text-text-primary mb-3">
                {t(
                  active.rank.rank_as_achievement
                    ? 'regions.ind.topAchieve'
                    : 'regions.ind.topNeutral',
                  { year: active.rank.year },
                )}
              </h2>
              <ol className="space-y-0.5">
                {active.rank.top.map((r, i) => (
                  <li key={r.slug}>
                    <Link
                      to={regionIndicatorPath(r.slug, code)}
                      className={`fe-tap flex items-center justify-between gap-2 text-[13px] rounded-lg px-2 py-1.5 -mx-2 hover:bg-surface-hover transition-colors ${r.slug === slug ? 'bg-champagne/5' : ''}`}
                    >
                      <span className="flex items-center gap-2 min-w-0">
                        <span className="fe-num w-4 shrink-0 text-right text-text-secondary">{i + 1}</span>
                        <span className={`min-w-0 break-words leading-snug ${r.slug === slug ? 'text-champagne-ink font-medium' : 'text-text-primary'}`}>{r.name}</span>
                      </span>
                      <span className="fe-num shrink-0 whitespace-nowrap font-medium text-text-primary">{formatRegionWithUnit(r.value, active.indicator.unit, locale)}</span>
                    </Link>
                  </li>
                ))}
              </ol>
              <Link
                to={regionRatingPath(code)}
                className="fe-tap-inline mt-3 text-xs font-medium text-champagne-ink hover:underline"
              >
                {t('regions.ind.fullRanking')}
              </Link>
              <R6RatingExtras rank={active.rank} slug={slug} code={code} unit={active.indicator.unit} locale={locale} russiaSeries={active.russia_series} t={t} />
            </div>
          )}

          <div className="mb-6 overflow-hidden rounded-3xl fe-glass-lite">
            <button
              onClick={() => setShowTable(v => !v)}
              className="w-full flex items-center justify-between px-4 py-3.5 hover:bg-surface-hover transition-colors"
              aria-expanded={showTable}
            >
              <span className="flex items-center gap-2 text-sm font-medium text-text-primary">
                <Table2 size={15} className="text-text-secondary" />
                {t(isMonthly ? 'z2.tableMonths' : 'regions.ind.tableToggle')}
              </span>
              <ChevronDown size={16} className={`text-text-secondary transition-transform ${showTable ? 'rotate-180' : ''}`} />
            </button>
            {showTable && (
              <div className="max-h-96 overflow-auto">
                <table className="w-full min-w-[18rem] text-[13px]">
                  <thead className="sticky top-0 bg-surface">
                    <tr className="text-left text-text-secondary">
                      <th className="px-3 py-2 font-medium sm:px-4">
                        {isMonthly ? t('regions.ind.colMonth') : t('regions.ind.colYear')}
                      </th>
                      <th className="px-3 py-2 text-right font-medium sm:px-4">{regionName}</th>
                      {active.russia_series?.length > 0 && (
                        <th className="px-3 py-2 text-right font-medium sm:px-4">{t('regions.ind.russia')}</th>
                      )}
                      {isMonthly && <th className="px-3 py-2 text-right font-medium sm:px-4">{t('r2z2.colYoy')}</th>}
                      {!isMonthly && active.russia_series?.length > 0 && (
                        <th className="px-3 py-2 text-right font-medium sm:px-4">{t('r6c.colGap')}</th>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {tableRows.map(p => {
                      const pKey = isMonthly ? p.label : p.year;
                      const rf = active.russia_series?.find(r => (isMonthly ? r.label === p.label : r.year === p.year));
                      return (
                        <tr key={pKey} className="border-t border-border-subtle">
                          <td className="fe-num px-3 py-1.5 text-text-secondary sm:px-4">
                            {isMonthly ? `${monthName(p.month, locale)} ${p.year}` : p.year}
                          </td>
                          <td className="fe-num px-3 py-1.5 text-right text-text-primary sm:px-4">{formatRegionNumber(p.value, active.indicator.unit, locale)}</td>
                          {active.russia_series?.length > 0 && (
                            <td className="fe-num px-3 py-1.5 text-right text-text-secondary sm:px-4">
                              {rf ? formatRegionNumber(rf.value, active.indicator.unit, locale) : '—'}
                            </td>
                          )}
                          {!isMonthly && active.russia_series?.length > 0 && (
                            <td className="fe-num r6c-diff-col px-3 py-1.5 text-right text-text-secondary sm:px-4">
                              {rf ? (gapText(p.value, rf.value, active.indicator.unit, locale)?.text ?? '—') : '—'}
                            </td>
                          )}
                          {isMonthly && (
                            <td className="fe-num px-3 py-1.5 text-right text-text-secondary sm:px-4">
                              {yoyByKey.get(p.year * 12 + p.month) != null ? signedPct(yoyByKey.get(p.year * 12 + p.month), locale) : '\u2014'}
                            </td>
                          )}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {active.indicator.macro_code && (
            <div className="mb-6 rounded-3xl p-4 fe-glass-lite">
              <h2 className="text-sm font-semibold text-text-primary mb-2">
                {t('regions.ind.macroTitle')}
              </h2>
              <p className="text-[13px] text-text-secondary leading-relaxed mb-3">
                {t('regions.ind.macroBody')}
              </p>
              <div className="flex flex-wrap gap-2">
                <Link
                  to={russiaIndicatorPath(active.indicator.macro_code)}
                  onClick={() => track(events.REGION_CROSSLINK_CLICK, { from: `region:${slug}:${code}`, to: active.indicator.macro_code })}
                  className="fe-tap-inline gap-1 px-3 py-1.5 rounded-full bg-champagne/10 text-champagne-ink text-[13px] font-medium hover:bg-champagne/20 transition-colors"
                >
                  {t('regions.ind.openRussia')} <ArrowUpRight size={13} />
                </Link>
                <Link
                  to={`/compare?codes=${active.indicator.macro_code},r:${slug}:${code}`}
                  onClick={() => track(events.REGION_CROSSLINK_CLICK, { from: `region:${slug}:${code}`, to: 'compare' })}
                  className="fe-tap-inline gap-1 px-3 py-1.5 rounded-full text-text-secondary text-[13px] font-medium hover:text-champagne-ink transition-colors fe-glass-2"
                >
                  <GitCompare size={13} /> {t('regions.ind.compareRussia')}
                </Link>
              </div>
            </div>
          )}

          {isMonthly && siblingsView.some(s => s.price_group) && (
            <GroupedSiblings
              siblings={siblingsView}
              currentGroup={priceGroup}
              slug={slug}
              section={active.indicator.section_name}
              regionName={regionName}
            />
          )}
          {active.siblings?.length > 0 && !(isMonthly && siblingsView.some(s => s.price_group)) && (
            <div>
              <h2 className="text-sm font-semibold text-text-primary mb-3">
                {t('regions.ind.moreInSection', { section: active.indicator.section_name })}
              </h2>
              <ul className="grid gap-2 sm:grid-cols-2">
                {annualSibs.slice(0, sibsOpen || isMonthly ? undefined : R6_SIBS_FIRST).map(s => (
                  <li key={s.code} className="min-w-0">
                    <Link
                      to={regionIndicatorPath(slug, s.code)}
                      className="fe-tap fe-press flex h-full items-center justify-between gap-3 rounded-2xl px-3.5 py-2.5 text-sm leading-snug text-text-primary transition-colors hover:text-champagne-ink fe-glass-lite fe-float"
                    >
                      <span className="min-w-0 break-words">{glueNumbers((isMonthly && s.short_name) || s.name)}</span>
                      <ArrowUpRight size={14} className="shrink-0 text-text-secondary" aria-hidden="true" />
                    </Link>
                  </li>
                ))}
              </ul>
              {!isMonthly && annualSibs.length > R6_SIBS_FIRST && (
                <button type="button" onClick={() => setSibsOpen(v => !v)} className="fe-tap r6c-more" aria-expanded={sibsOpen}>
                  {sibsOpen ? t('r6c.sibsLess') : t('r6c.sibsMore', { n: annualSibs.length - R6_SIBS_FIRST })}
                </button>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
