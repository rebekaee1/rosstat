// Значок свежести данных у числа (круг 11, F): «Данные до августа 2026» или «Устарело: данные до марта 2025».
// Заменяет надпись про давность внизу страницы. Форма значка (заполненный круг, половина, кольцо) несёт смысл вместе с цветом.
import { useMemo } from 'react';
import { formatDate } from '../lib/format';
import { glueDate } from '../lib/periodPhrase';
import { dataFreshness, freshnessDateFormat } from '../lib/dataFreshness';
import { useLocale, useT } from '../i18n';
import '../styles/z4-indicator.css';

export default function FreshnessBadge({
  lastDate, frequency, now = undefined, className = '',
}) {
  const t = useT();
  const { locale } = useLocale();
  const state = useMemo(
    () => dataFreshness(lastDate, frequency, now),
    [lastDate, frequency, now],
  );
  if (!state) return null;
  const period = glueDate(formatDate(lastDate, freshnessDateFormat(frequency), locale));
  const text = state.level === 'stale'
    ? t('c11f.fresh.stale', { date: period })
    : t('c11f.fresh.upTo', { date: period });
  const hint = t(`c11f.fresh.hint.${state.level}`);
  return (
    <span
      className={`z4-fresh${className ? ` ${className}` : ''}`}
      data-level={state.level}
      title={hint}
      data-testid="data-freshness"
    >
      <span className="z4-fresh__mark" aria-hidden="true" />
      <span>{text}</span>
    </span>
  );
}
