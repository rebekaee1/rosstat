import { useMemo } from 'react';
import { useIndicatorData } from './hooks';
import { useWorldCompareCatalog, useWorldCompareSeries, useWorldIndicator } from './worldApi';
import { useLocale } from '../i18n';
import {
  annualYoyFromIndexPoints,
  buildRussiaResult,
  buildWorldResult,
  defaultCountrySlug,
  inflationCountriesFromCatalog,
  isRussiaCountry,
  RUSSIA_SOURCE,
  RUSSIA_SLUG,
  HICP_CONCEPT,
  yearOf,
} from './inflationCalc';

const CPI_QUERY_PARAMS = { limit: 5000 };

/** Слаг страны калькулятора. Пустой/неизвестный слаг → дефолт локали. */
export function resolveCalcCountrySlug(countrySlug, locale, { knownSlugs = null, catalogLoading = false } = {}) {
  const fallback = defaultCountrySlug(locale);
  const slug = String(countrySlug || '').trim().toLowerCase();
  if (!slug) return fallback;
  if (isRussiaCountry(slug)) return RUSSIA_SLUG;
  if (catalogLoading || !knownSlugs?.length) return slug;
  return knownSlugs.includes(slug) ? slug : fallback;
}

export default function useInflationCalc(amount, fromYear, toYear, countrySlug = 'russia') {
  const { locale } = useLocale();

  const catalogQ = useWorldCompareCatalog();
  const countries = useMemo(
    () => inflationCountriesFromCatalog(catalogQ.data, { locale }),
    [catalogQ.data, locale],
  );
  const knownSlugs = useMemo(() => countries.map((c) => c.slug), [countries]);
  const resolvedSlug = useMemo(
    () => resolveCalcCountrySlug(countrySlug, locale, {
      knownSlugs,
      catalogLoading: catalogQ.isLoading,
    }),
    [countrySlug, locale, knownSlugs, catalogQ.isLoading],
  );
  const isRussia = isRussiaCountry(resolvedSlug);

  const qCpi = useIndicatorData('cpi', CPI_QUERY_PARAMS, { enabled: isRussia });
  const qFood = useIndicatorData('cpi-food', CPI_QUERY_PARAMS, { enabled: isRussia });
  const qNonfood = useIndicatorData('cpi-nonfood', CPI_QUERY_PARAMS, { enabled: isRussia });
  const qServices = useIndicatorData('cpi-services', CPI_QUERY_PARAMS, { enabled: isRussia });

  const seriesQ = useWorldCompareSeries(
    isRussia ? null : resolvedSlug,
    HICP_CONCEPT,
    { enabled: !isRussia && !!resolvedSlug },
  );
  const indicatorCode = seriesQ.data?.meta?.indicator_code;
  const metaQ = useWorldIndicator(
    isRussia ? null : resolvedSlug,
    indicatorCode,
  );

  const cpiAllRaw = qCpi.data?.data;
  const cpiFoodRaw = qFood.data?.data;
  const cpiNonfoodRaw = qNonfood.data?.data;
  const cpiServicesRaw = qServices.data?.data;

  const cpiAll = useMemo(() => cpiAllRaw || [], [cpiAllRaw]);
  const cpiFood = useMemo(() => cpiFoodRaw || [], [cpiFoodRaw]);
  const cpiNonfood = useMemo(() => cpiNonfoodRaw || [], [cpiNonfoodRaw]);
  const cpiServices = useMemo(() => cpiServicesRaw || [], [cpiServicesRaw]);

  const worldPoints = useMemo(
    () => seriesQ.data?.data || [],
    [seriesQ.data],
  );

  const worldYoy = useMemo(
    () => annualYoyFromIndexPoints(worldPoints),
    [worldPoints],
  );

  const lastAvailableDate = useMemo(() => {
    if (isRussia) {
      if (!cpiAll.length) return null;
      return cpiAll[cpiAll.length - 1].date;
    }
    if (worldYoy.length) return worldYoy[worldYoy.length - 1].date;
    if (!worldPoints.length) return null;
    return worldPoints[worldPoints.length - 1].date;
  }, [isRussia, cpiAll, worldYoy, worldPoints]);

  const lastAvailableYear = useMemo(() => {
    if (!lastAvailableDate) return new Date().getFullYear();
    return yearOf(lastAvailableDate);
  }, [lastAvailableDate]);

  const minYear = useMemo(() => {
    if (isRussia) {
      if (!cpiAll.length) return 1991;
      return yearOf(cpiAll[0].date);
    }
    if (worldYoy.length) return worldYoy[0].year;
    if (!worldPoints.length) return fromYear;
    return yearOf(worldPoints[0].date);
  }, [isRussia, cpiAll, worldYoy, worldPoints, fromYear]);

  const seriesStartYear = useMemo(() => {
    if (isRussia || !worldPoints.length) return null;
    return yearOf(worldPoints[0].date);
  }, [isRussia, worldPoints]);

  const source = isRussia
    ? RUSSIA_SOURCE
    : (metaQ.data?.indicator?.source || '');

  /** Прямая ссылка на источник ряда (мировая ветка); у России ведём на карточку ИПЦ. */
  const sourceUrl = isRussia ? null : (metaQ.data?.indicator?.source_url || null);

  const countryName = isRussia
    ? null
    : (seriesQ.data?.meta?.country_name
      || countries.find((c) => c.slug === countrySlug)?.name
      || countrySlug);

  const isLoading = isRussia
    ? (qCpi.isLoading || qFood.isLoading || qNonfood.isLoading || qServices.isLoading)
    : (seriesQ.isLoading || (Boolean(indicatorCode) && metaQ.isLoading));
  const isError = isRussia
    ? (qCpi.isError || qFood.isError || qNonfood.isError || qServices.isError)
    : seriesQ.isError;

  const countriesLoading = catalogQ.isLoading;

  return useMemo(() => {
    const base = {
      isLoading,
      isError,
      lastAvailableYear,
      minYear,
      lastAvailableDate,
      countries,
      countriesLoading,
      /** Слаг после валидации каталога — пикер и share-ссылка держатся его, а не сырого URL-параметра. */
      resolvedCountrySlug: resolvedSlug,
      source,
      sourceUrl,
      countryName,
      seriesStartYear,
      isRussia,
    };

    if (isLoading || isError || !amount || amount <= 0) {
      return { ...base, result: null };
    }

    if (isRussia) {
      if (!cpiAll.length) return { ...base, result: null };
      return {
        ...base,
        result: buildRussiaResult({
          amount,
          fromYear,
          toYear,
          cpiAll,
          cpiFood,
          cpiNonfood,
          cpiServices,
          minYear,
          lastAvailableYear,
          lastAvailableDate,
        }),
      };
    }

    if (!worldPoints.length) return { ...base, result: null };

    return {
      ...base,
      result: buildWorldResult({
        amount,
        fromYear,
        toYear,
        indexPoints: worldPoints,
        seriesStartYear,
      }),
    };
  }, [
    amount, fromYear, toYear, cpiAll, cpiFood, cpiNonfood, cpiServices,
    worldPoints, isLoading, isError, lastAvailableYear, minYear, lastAvailableDate,
    countries, countriesLoading, source, sourceUrl, countryName, seriesStartYear,
    isRussia, resolvedSlug,
  ]);
}
