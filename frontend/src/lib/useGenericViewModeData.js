import { useMemo } from 'react';
import { useIndicatorData, useForecast } from './hooks';
import { resolveViewMode } from './viewModeEngine';

/**
 * Config-driven data-слой карточки индикатора.
 *
 * По (family, urlMode) разрешает режим в backend-код (нативный source для
 * уровня, derived sibling для агрегаций/приростов), тянет его ряд и прогноз,
 * пересчитывает телеметрию по подменённому ряду и собирает effectiveIndicator
 * (unit/frequency/имя режима) для downstream-секций.
 *
 * Заменяет ветвление useIndicatorViewModeData для всех generic-семей: один
 * путь данных вместо ~20 family-специфичных.
 */
function statsFromPoints(points) {
  if (!points?.length) return null;
  const current = points[points.length - 1];
  const previous = points.length > 1 ? points[points.length - 2] : null;
  const highest = points.reduce((max, p) => (p.value > max.value ? p : max), points[0]);
  const lowest = points.reduce((min, p) => (p.value < min.value ? p : min), points[0]);
  const avg = points.reduce((sum, p) => sum + p.value, 0) / points.length;
  return {
    currentValue: current.value,
    currentDate: current.date,
    previousValue: previous?.value,
    previousDate: previous?.date,
    change: previous ? current.value - previous.value : null,
    highest: { value: highest.value, date: highest.date },
    lowest: { value: lowest.value, date: lowest.date },
    average: avg,
    dataCount: points.length,
  };
}

function modeSuffix(family, meta) {
  if (!meta || meta.mode === family.defaultMode) return null;
  const group = family.groups.find((g) => g.id === meta.group);
  if (!group) return meta.label;
  if (group.leaf) return group.label;
  return `${group.label}, ${meta.label.toLowerCase()}`;
}

export default function useGenericViewModeData({ family, urlMode, indicator, enabled = true }) {
  const resolved = useMemo(
    () => (family ? resolveViewMode(family, urlMode) : null),
    [family, urlMode],
  );

  const code = resolved?.code ?? null;
  const { data: dataResp, isLoading, isError, refetch } = useIndicatorData(
    code,
    undefined,
    { enabled: enabled && !!code },
  );
  const { data: forecastResp, refetch: refetchForecast } = useForecast(
    code,
    { enabled: enabled && !!code && !!resolved?.forecastable },
  );

  const dataPoints = useMemo(() => dataResp?.data ?? [], [dataResp]);
  const viewStats = useMemo(() => statsFromPoints(dataPoints), [dataPoints]);

  const effectiveIndicator = useMemo(() => {
    if (!indicator || !resolved) return indicator;
    const suffix = modeSuffix(family, resolved);
    return {
      ...indicator,
      unit: resolved.unit ?? indicator.unit,
      frequency: resolved.frequency ?? indicator.frequency,
      name: suffix ? `${indicator.name} — ${suffix}` : indicator.name,
    };
  }, [indicator, resolved, family]);

  const forecastValues = forecastResp?.forecast?.values;
  const hasForecast = Array.isArray(forecastValues) && forecastValues.length > 0;
  const forecastEnabled = !!resolved?.forecastable && hasForecast;

  return {
    resolved,
    dataPoints,
    viewStats,
    effectiveIndicator,
    forecastResp,
    forecastEnabled,
    hasForecast,
    isLoading,
    isError,
    refetch,
    refetchForecast,
  };
}
