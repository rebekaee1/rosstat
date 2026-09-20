import { useMemo, useState } from 'react';
import { useQueries } from '@tanstack/react-query';
import {
  fetchWorldAverageSeries,
  fetchWorldCompareSeries,
  fetchWorldIndicatorMode,
  useWorldCompareCatalog,
} from './worldApi';
import { rebaseWorldComparison } from './worldComparison';
import {
  WORLD_RANKING_AVERAGE_CONCEPTS,
  WORLD_RANKING_MEDIAN_CONCEPTS,
} from './homeWorkbench';
import { useLocale, useT } from '../i18n';

export const COMPARISON_COLORS = ['#397C8C', '#7856A8', '#C86B5B', '#4D8A64'];
export const MAX_COMPARISONS = COMPARISON_COLORS.length;
const EMPTY_LIST = [];

function isAbsoluteLevel(unit, modeMeta) {
  const normalized = (unit || '').toLowerCase();
  return modeMeta?.type === 'level'
    && !normalized.includes('%')
    && !normalized.includes('индекс')
    && !normalized.includes('index')
    && !normalized.includes('п.п.');
}

function averageCountryLabel(conceptSlug, t) {
  if (WORLD_RANKING_MEDIAN_CONCEPTS.has(conceptSlug)) {
    return t('world.chart.medianCountries');
  }
  return t('world.chart.averageCountries');
}

function scalePoints(points, scale, adjust) {
  if (!points?.length) return [];
  const factor = Number(scale);
  const needScale = Number.isFinite(factor) && factor !== 1;
  if (!needScale && adjust !== 'minus_100') return points;
  return points.map((point) => {
    let value = Number(point.value);
    if (!Number.isFinite(value)) return point;
    if (adjust === 'minus_100') value -= 100;
    if (needScale) value *= factor;
    return { ...point, value };
  });
}

/**
 * Общий хук сравнения стран: мировая карточка и российская с концептом.
 *
 * surface=world — текущий mode карточки + compare/series для России.
 * surface=russia — peer_mode из меты (сопоставимые единицы), Россия = база.
 */
export function useCountryComparison({
  surface = 'world',
  peers = EMPTY_LIST,
  conceptSlug,
  countrySlug,
  dataPoints,
  unit,
  title,
  modeMeta,
  peerMode,
  peerValueScale = 1,
} = {}) {
  const { locale } = useLocale();
  const t = useT();
  const [comparisonPickerActive, setComparisonPickerActive] = useState(false);
  const compareCatalog = useWorldCompareCatalog({
    enabled: comparisonPickerActive,
  });
  const [comparisonIds, setComparisonIds] = useState([]);
  const [comparisonScale, setComparisonScale] = useState('values');

  const comparisonOptions = useMemo(() => {
    const bySlug = new Map();
    const add = (item) => {
      if (!item?.country_slug || item.country_slug === countrySlug) return;
      if (!bySlug.has(item.country_slug)) bySlug.set(item.country_slug, item);
    };
    (peers || []).forEach((item) => add({
      ...item,
      country_name: locale === 'en'
        ? (item.country_name_en || item.country_name)
        : item.country_name,
      code: item.code || `peer:${item.country_slug}:${item.indicator_code}`,
    }));
    (compareCatalog.data?.items || [])
      .filter((item) => item.concept_slug === conceptSlug)
      .forEach((item) => add({
        ...item,
        country_name: locale === 'en'
          ? (item.country_name_en || item.country_name)
          : item.country_name,
      }));
    const sorted = [...bySlug.values()].sort((a, b) => (
      String(a.country_name || a.country_slug || '').localeCompare(
        String(b.country_name || b.country_slug || ''),
        locale === 'en' ? 'en' : 'ru',
      )
    ));
    return sorted.length ? sorted : EMPTY_LIST;
  }, [peers, compareCatalog.data, conceptSlug, countrySlug, locale]);

  const pickerOptions = useMemo(() => {
    if (!WORLD_RANKING_AVERAGE_CONCEPTS.has(conceptSlug)) return comparisonOptions;
    return [
      { code: 'average', country_name: averageCountryLabel(conceptSlug, t) },
      ...comparisonOptions,
    ];
  }, [comparisonOptions, conceptSlug, t]);

  const activeComparisonIds = comparisonIds.filter((id) => (
    pickerOptions.some((option) => option.code === id)
  ));

  const comparisonQueries = useQueries({
    queries: activeComparisonIds.map((id) => ({
      queryKey: [
        'world-card-comparison',
        surface,
        id,
        conceptSlug,
        modeMeta?.id,
        peerMode,
        locale,
      ],
      queryFn: async ({ signal }) => {
        if (id === 'average') {
          const mode = surface === 'russia' ? peerMode : modeMeta?.id;
          const payload = await fetchWorldAverageSeries(conceptSlug, mode, { signal });
          const points = payload?.points || payload?.data || [];
          const mapped = surface === 'russia'
            ? scalePoints(points, peerValueScale)
            : points;
          return { ...payload, points: mapped, data: mapped };
        }
        const option = comparisonOptions.find((item) => item.code === id);
        if (!option) return null;
        if (surface === 'world' && option.country_slug === 'russia') {
          return fetchWorldCompareSeries('russia', conceptSlug, { signal });
        }
        if (surface === 'world') {
          return fetchWorldIndicatorMode(
            option.country_slug,
            option.indicator_code,
            modeMeta?.id,
            { signal },
          );
        }
        const mode = option.peer_mode || peerMode;
        const payload = await fetchWorldIndicatorMode(
          option.country_slug,
          option.indicator_code,
          mode,
          { signal },
        );
        const points = payload?.points || payload?.data || [];
        const mapped = scalePoints(
          points,
          option.peer_value_scale ?? peerValueScale,
          option.value_adjust,
        );
        return { ...payload, points: mapped, data: mapped };
      },
      enabled: !!id && (surface === 'russia' ? !!peerMode : !!modeMeta?.id),
      staleTime: 10 * 60 * 1000,
    })),
  });

  const comparisonIdsKey = activeComparisonIds.join('|');
  const queryData = [
    comparisonQueries[0]?.data,
    comparisonQueries[1]?.data,
    comparisonQueries[2]?.data,
    comparisonQueries[3]?.data,
  ];
  const selectedComparisons = useMemo(
    () => {
      if (!activeComparisonIds.length) return EMPTY_LIST;
      return activeComparisonIds.map((id, index) => {
      const option = pickerOptions.find((item) => item.code === id);
      const payload = queryData[index];
      return {
        id,
        option,
        label: payload?.meta?.country_name
          || option?.country_name
          || t('chart.compareSeries'),
        color: COMPARISON_COLORS[index],
        data: payload?.points || payload?.data || [],
      };
    });
    },
    // Query payload objects are stable in TanStack Query; fixed slots keep the
    // resulting series stable and prevent chart → onFullData render loops.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [comparisonIdsKey, pickerOptions, locale, queryData[0], queryData[1], queryData[2], queryData[3]],
  );
  const loadedComparisonSeries = useMemo(() => {
    const loaded = selectedComparisons.filter((item) => item.data.length > 0);
    return loaded.length ? loaded : EMPTY_LIST;
  }, [selectedComparisons]);
  const rebased = useMemo(
    () => (comparisonScale === 'index'
      ? rebaseWorldComparison(dataPoints || [], loadedComparisonSeries)
      : null),
    [comparisonScale, dataPoints, loadedComparisonSeries],
  );
  const displayedDataPoints = rebased?.base || dataPoints;
  const displayedComparisonSeries = rebased?.series || loadedComparisonSeries;
  const displayedUnit = rebased ? t('world.chart.rebasedUnit') : unit;
  const displayedTitle = rebased ? t('world.chart.rebasedTitle', { title }) : title;

  const toggleComparison = (id) => {
    const absolute = surface === 'russia'
      ? isAbsoluteLevel(unit, { type: 'level' })
      : isAbsoluteLevel(unit, modeMeta);
    if (
      !activeComparisonIds.includes(id)
      && activeComparisonIds.length === 0
      && absolute
    ) {
      setComparisonScale('index');
    }
    setComparisonIds((current) => {
      if (current.includes(id)) return current.filter((item) => item !== id);
      if (current.length >= MAX_COMPARISONS) return current;
      return [...current, id];
    });
  };

  const compareCodes = activeComparisonIds
    .filter((id) => id !== 'average')
    .map((id) => pickerOptions.find((item) => item.code === id))
    .filter((item) => item?.country_slug && conceptSlug)
    .map((item) => `w:${item.country_slug}:${conceptSlug}`);

  return {
    pickerOptions,
    activeComparisonIds,
    selectedComparisons,
    comparisonQueries,
    comparisonScale,
    setComparisonScale,
    toggleComparison,
    setComparisonPickerActive,
    compareCodes,
    rebased,
    loadedComparisonSeries,
    displayedDataPoints,
    displayedComparisonSeries,
    displayedUnit,
    displayedTitle,
  };
}
