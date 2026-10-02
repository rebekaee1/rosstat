import { useMemo } from 'react';
import { CalendarRange, Database, Globe2, Landmark, MapPinned, Network } from 'lucide-react';
import { homeScopeCountriesCount } from '../../lib/homeWorkbench';
import { useWorldCountries } from '../../lib/worldApi';
import { useLocale, useT } from '../../i18n';

const SCOPE_STATS_RU = [
  { key: 'world', icon: Globe2 },
  { key: 'countries', icon: Network },
  { key: 'macro', icon: Landmark },
  { key: 'regions', icon: MapPinned },
];

const SCOPE_STATS_EN = [
  { key: 'world', icon: Globe2 },
  { key: 'countries', icon: Network },
];

/**
 * Правая колонка hero главной: состав платформы в цифрах.
 * Страны — динамически с `/world/countries` (фоллбэк i18n); региональные
 * Counts come from the same public catalogue response as the country cards.
 */
export default function HomeDataScope() {
  const t = useT();
  const { locale } = useLocale();
  const scopeStats = locale === 'en' ? SCOPE_STATS_EN : SCOPE_STATS_RU;
  const countriesQ = useWorldCountries();
  const countriesValue = useMemo(() => {
    const n = homeScopeCountriesCount(countriesQ.data);
    return n != null ? String(n) : t('home.scope.stat.countries.value');
  }, [countriesQ.data, t]);

  const countValue = (key, count) => {
    if (!Number.isFinite(count) || count <= 0) return t(`home.scope.stat.${key}.value`);
    return new Intl.NumberFormat(locale === 'en' ? 'en-US' : 'ru-RU').format(count);
  };

  const ruRegionalCount = (() => {
    const direct = Number(countriesQ.data?.russia_regional_indicators_count);
    if (Number.isFinite(direct) && direct > 0) return direct;
    // An older cached country response can lack the dedicated field.
    const russia = countriesQ.data?.countries?.find((country) =>
      country.code === 'RU' || country.slug === 'russia');
    const total = Number(russia?.indicators_count);
    const macro = Number(countriesQ.data?.russia_macro_indicators_count);
    return Number.isFinite(total) && Number.isFinite(macro) && total >= macro
      ? total - macro
      : NaN;
  })();

  const valueFor = (key) => {
    if (key === 'countries') return countriesValue;
    if (key === 'regions') return countValue(key, ruRegionalCount);
    const fields = {
      world: 'world_indicators_count',
      macro: 'russia_macro_indicators_count',
    };
    return countValue(key, Number(countriesQ.data?.[fields[key]]));
  };
  const usIndicators = Number(countriesQ.data?.us_state_indicators_count);
  const usStates = Number(countriesQ.data?.us_states_count);

  return (
    <aside
      data-block="home-data-scope"
      className="relative z-30 overflow-hidden rounded-2xl border border-border-subtle bg-surface p-4 shadow-[0_18px_48px_rgba(35,30,16,0.05)] sm:p-5"
      aria-labelledby="home-data-scope-title"
    >
      <div className="pointer-events-none absolute -right-12 -top-14 h-36 w-36 rounded-full bg-champagne/10 blur-3xl" />

      <div className="relative">
        <div className="flex items-center gap-2 font-mono text-xs uppercase tracking-[0.16em] text-champagne sm:text-sm">
          <Database size={12} className="shrink-0" />
          <h2 id="home-data-scope-title" className="font-semibold">
            {t('home.scope.title')}
          </h2>
        </div>

        <dl className="mt-3.5 grid grid-cols-2 gap-x-3 gap-y-3.5">
          {scopeStats.map(({ key, icon: Icon }) => (
            // Число стоит над подписью: значения в строке выровнены, даже если
            // соседняя подпись занимает две строки.
            <div key={key} className="flex min-w-0 flex-col-reverse justify-end gap-1">
              <dt className="flex items-start gap-1.5 text-[11px] font-medium uppercase tracking-[0.08em] text-text-tertiary sm:text-xs">
                <Icon size={11} className="mt-[3px] shrink-0 text-champagne/70" aria-hidden="true" />
                <span className="leading-snug [overflow-wrap:anywhere]">{t(`home.scope.stat.${key}.label`)}</span>
              </dt>
              <dd className="font-mono text-lg font-bold tabular-nums tracking-tight text-text-primary sm:text-xl">
                {valueFor(key)}
              </dd>
            </div>
          ))}
          <div className="col-span-2 flex min-w-0 flex-col-reverse gap-1 border-t border-border-subtle pt-3">
            <dt className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-[0.08em] text-text-tertiary sm:text-xs">
              <CalendarRange size={11} className="shrink-0 text-champagne/70" aria-hidden="true" />
              <span className="leading-snug">{t('home.scope.period.label')}</span>
            </dt>
            <dd className="font-mono text-lg font-bold tabular-nums tracking-tight text-text-primary sm:text-xl">
              {t('home.scope.period.value')}
            </dd>
          </div>
        </dl>

        <div className="mt-3.5 border-t border-border-subtle pt-3">
          {locale === 'en' && usIndicators > 0 && usStates > 0 && (
            <p className="mb-2 text-[11px] leading-snug text-text-secondary">
              {t('home.scope.usStates', {
                indicators: new Intl.NumberFormat(locale === 'en' ? 'en-US' : 'ru-RU').format(usIndicators),
                states: usStates,
              })}
            </p>
          )}
          <p className="text-[11px] font-medium uppercase tracking-[0.1em] text-text-tertiary sm:text-xs">
            {t('home.scope.sources.label')}
          </p>
          <p className="mt-1 text-xs font-medium leading-snug text-text-secondary">
            {t('home.scope.sources.list')}
          </p>
          <p className="mt-2 flex items-center gap-1.5 text-[10px] leading-snug text-text-tertiary">
            <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-champagne" aria-hidden="true" />
            {t('home.scope.update')}
          </p>
        </div>
      </div>
    </aside>
  );
}
