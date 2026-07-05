import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { ChevronRight, ArrowRight } from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import { useIndicator, useIndicatorData } from '../lib/hooks';
import { TODAY_CODES, TODAY_SPECS } from '../lib/todaySpecs';
import { formatValue, formatDate, formatChange } from '../lib/format';
import ApiRetryBanner from '../components/ApiRetryBanner';
import { SkeletonBox } from '../components/Skeleton';

const MONTHS_GEN = [
  'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
  'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря',
];

function ruDate(d = new Date()) {
  return `${d.getDate()} ${MONTHS_GEN[d.getMonth()]} ${d.getFullYear()} года`;
}

function TodayCard({ code }) {
  const spec = TODAY_SPECS[code];
  const seriesCode = spec.series || code;
  const { data: indicator } = useIndicator(seriesCode);
  const { data: rows, isLoading, isError } = useIndicatorData(seriesCode, { limit: 2 });

  const last = rows?.data?.[rows.data.length - 1];
  const prev = rows?.data?.length > 1 ? rows.data[rows.data.length - 2] : null;
  const change = last && prev ? last.value - prev.value : null;

  return (
    <Link
      to={`/today/${code}`}
      className="group bg-surface border border-border-subtle rounded-xl p-4 hover:border-border-champagne hover:shadow-sm transition-all flex flex-col gap-2"
    >
      <div className="text-[11px] text-text-tertiary uppercase tracking-wide font-mono">
        {spec.query} сегодня
      </div>
      {isLoading ? (
        <SkeletonBox className="h-8 w-32" />
      ) : isError || !last ? (
        <span className="text-sm text-text-tertiary">Нет данных</span>
      ) : (
        <>
          <div className="font-mono text-2xl font-bold text-text-primary leading-none">
            {formatValue(last.value)}
            <span className="ml-1.5 text-sm font-normal text-text-secondary">
              {indicator?.unit || ''}
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-[11px] text-text-tertiary">
            {change != null && Math.abs(change) >= 1e-12 && (
              <span className={change > 0 ? 'text-positive' : 'text-negative'}>
                {formatChange(change, indicator?.unit)}
              </span>
            )}
            <span>{formatDate(last.date, indicator?.frequency === 'daily' ? 'full' : 'monthly')}</span>
          </div>
        </>
      )}
      <span className="text-xs text-champagne group-hover:underline mt-auto inline-flex items-center gap-1">
        Подробнее <ArrowRight size={12} />
      </span>
    </Link>
  );
}

export default function TodayHub() {
  const today = ruDate();
  useDocumentMeta({
    title: `Экономика России сегодня, ${today}: курсы, ставка, инфляция, цены`,
    description:
      'Ключевые экономические показатели России на сегодня: курс доллара, евро и юаня, '
      + 'ключевая ставка ЦБ, инфляция, цена золота и топлива, индекс МосБиржи. '
      + 'Официальные данные, обновление ежедневно.',
    path: '/today',
  });

  return (
    <div className="max-w-5xl mx-auto px-4 pt-24 pb-20">
      <nav className="flex items-center gap-1.5 text-xs text-text-tertiary mb-4" aria-label="Хлебные крошки">
        <Link to="/" className="hover:text-champagne transition-colors">Главная</Link>
        <ChevronRight size={12} />
        <span className="text-text-secondary">Сегодня</span>
      </nav>

      <p className="text-champagne text-xs font-mono uppercase tracking-widest mb-2">
        Сводка на {today}
      </p>
      <h1 className="font-display text-3xl sm:text-4xl font-bold text-text-primary mb-3">
        Экономика России сегодня
      </h1>
      <p className="text-text-secondary max-w-2xl mb-8">
        Актуальные значения ключевых показателей. Каждая карточка — последнее значение,
        график и таблица; полная история и прогноз — на карточках индикаторов.
      </p>

      <section className="mb-10">
        <h2 className="font-display text-lg font-semibold text-text-primary mb-4">
          Показатели на сегодня
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {TODAY_CODES.map((code) => (
            <TodayCard key={code} code={code} />
          ))}
        </div>
      </section>

      <section className="bg-surface border border-border-subtle rounded-xl p-5">
        <h2 className="font-display text-base font-semibold text-text-primary mb-2">Больше данных</h2>
        <p className="text-sm text-text-secondary">
          Более 100 макроэкономических индикаторов — на{' '}
          <Link to="/" className="text-champagne hover:underline">главной странице</Link>
          ; региональная статистика — в разделе{' '}
          <Link to="/regions" className="text-champagne hover:underline">Регионы России</Link>
          ; даты публикаций — в{' '}
          <Link to="/calendar" className="text-champagne hover:underline">календаре статистики</Link>.
        </p>
      </section>
    </div>
  );
}
