import { useMemo } from 'react';
import { useIndicatorData } from './hooks';

const CPI_CODES = ['cpi', 'cpi-food', 'cpi-nonfood', 'cpi-services'];

function computeCumulative(points, fromDate, toDate) {
  let product = 1;
  const series = [];
  let monthIdx = 0;

  for (const p of points) {
    if (p.date < fromDate || p.date > toDate) continue;
    product *= p.value / 100;
    monthIdx++;
    series.push({ date: p.date, product, monthIdx });
  }

  return { product, series, months: monthIdx };
}

function buildPurchasingPowerSeries(amount, cpiPoints, fromDate, toDate) {
  const series = [];
  let cumProduct = 1;
  let prevYear = null;

  for (const p of cpiPoints) {
    if (p.date < fromDate || p.date > toDate) continue;
    cumProduct *= p.value / 100;
    const year = new Date(p.date).getUTCFullYear();

    series.push({
      date: p.date,
      purchasing: Math.round(amount / cumProduct),
      equivalent: Math.round(amount * cumProduct),
      year,
      isJanuary: prevYear !== year,
    });
    prevYear = year;
  }

  return series;
}

function toDateStr(year, month = 1) {
  return `${year}-${String(month).padStart(2, '0')}-01`;
}

export default function useInflationCalc(amount, fromYear, toYear) {
  const queries = CPI_CODES.map(code =>
    useIndicatorData(code, { limit: 5000 })
  );

  const isLoading = queries.some(q => q.isLoading);
  const isError = queries.some(q => q.isError);
  const allData = queries.map(q => q.data?.data || []);

  const cpiAll = allData[0];
  const cpiFood = allData[1];
  const cpiNonfood = allData[2];
  const cpiServices = allData[3];

  const lastAvailableDate = useMemo(() => {
    if (!cpiAll.length) return null;
    return cpiAll[cpiAll.length - 1].date;
  }, [cpiAll]);

  const lastAvailableYear = useMemo(() => {
    if (!lastAvailableDate) return new Date().getFullYear();
    return new Date(lastAvailableDate).getUTCFullYear();
  }, [lastAvailableDate]);

  const minYear = useMemo(() => {
    if (!cpiAll.length) return 1991;
    return new Date(cpiAll[0].date).getUTCFullYear();
  }, [cpiAll]);

  return useMemo(() => {
    const base = { isLoading, isError, lastAvailableYear, minYear, lastAvailableDate };

    if (isLoading || isError || !cpiAll.length || !amount || amount <= 0) {
      return { ...base, result: null };
    }

    const effectiveFrom = Math.max(fromYear, minYear);
    const effectiveTo = Math.min(toYear, lastAvailableYear);
    if (effectiveFrom >= effectiveTo) {
      return {
        ...base,
        result: {
          equivalent: amount,
          purchasing: amount,
          totalInflation: 0,
          avgAnnual: 0,
          multiplier: 1,
          series: [],
          months: 0,
          food: 0,
          nonfood: 0,
          services: 0,
        },
      };
    }

    const fromDate = toDateStr(effectiveFrom, 2);
    const toDate = lastAvailableDate && effectiveTo === lastAvailableYear
      ? lastAvailableDate
      : toDateStr(effectiveTo, 12);

    const { product, months } = computeCumulative(cpiAll, fromDate, toDate);
    const series = buildPurchasingPowerSeries(amount, cpiAll, fromDate, toDate);

    const totalInflation = (product - 1) * 100;
    const years = months / 12;
    const avgAnnual = years > 0 ? (Math.pow(product, 1 / years) - 1) * 100 : 0;

    const foodCum = computeCumulative(cpiFood, fromDate, toDate);
    const nonfoodCum = computeCumulative(cpiNonfood, fromDate, toDate);
    const servicesCum = computeCumulative(cpiServices, fromDate, toDate);

    return {
      ...base,
      result: {
        equivalent: Math.round(amount * product),
        purchasing: Math.round(amount / product),
        totalInflation,
        avgAnnual,
        multiplier: product,
        series,
        months,
        food: (foodCum.product - 1) * 100,
        nonfood: (nonfoodCum.product - 1) * 100,
        services: (servicesCum.product - 1) * 100,
      },
    };
  }, [amount, fromYear, toYear, cpiAll, cpiFood, cpiNonfood, cpiServices, isLoading, isError, lastAvailableYear, minYear, lastAvailableDate]);
}
