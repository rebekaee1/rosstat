import { useMemo } from 'react';
import { CalendarRange, Database, Globe2, Landmark, MapPinned, Network } from 'lucide-react';
import { homeScopeCountriesCount } from '../../lib/homeWorkbench';
import { useWorldCountries } from '../../lib/worldApi';
import { useT } from '../../i18n';

const SCOPE_STATS = [
  { key: 'world', icon: Globe2 },
  { key: 'countries', icon: Network },
  { key: 'macro', icon: Landmark },
  { key: 'regions', icon: MapPinned },
];

/**
 * Правая колонка hero главной: состав платформы в цифрах.
 * Страны — динамически с `/world/countries` (фоллбэк i18n); региональные
 * показатели РФ — число индикаторов (495), без произведения на субъекты.
 */
export default function HomeDataScope() {
  const t = useT();
  const countriesQ = useWorldCountries();
  const countriesValue = useMemo(() => {
    const n = homeScopeCountriesCount(countriesQ.data);
    return n != null ? String(n) : t('home.scope.stat.countries.value');
  }, [countriesQ.data, t]);

  const valueFor = (key) => (
    key === 'countries' ? countriesValue : t(`home.scope.stat.${key}.value`)
  );

  return (
    <aside
      data-block="home-data-scope"
      className="relative z-30 overflow-hidden rounded-2xl border border-border-subtle bg-surface p-4 shadow-[0_18px_48px_rgba(35,30,16,0.05)] sm:p-5"
      aria-labelledby="home-data-scope-title"
    >
      <div className="pointer-events-none absolute -right-12 -top-14 h-36 w-36 rounded-full bg-champagne/10 blur-3xl" />

      <div className="relative">
        <div className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.2em] text-champagne">
          <Database size={12} className="shrink-0" />
          <h2 id="home-data-scope-title" className="font-semibold">
            {t('home.scope.title')}
          </h2>
        </div>

        <dl className="mt-3.5 grid grid-cols-2 gap-x-3 gap-y-3.5">
          {SCOPE_STATS.map(({ key, icon: Icon }) => (
            <div key={key} className="min-w-0">
              <dt className="flex items-center gap-1.5 text-[9px] font-medium uppercase tracking-[0.14em] text-text-tertiary">
                <Icon size={11} className="shrink-0 text-champagne/70" aria-hidden="true" />
                <span className="line-clamp-2 leading-snug">{t(`home.scope.stat.${key}.label`)}</span>
              </dt>
              <dd className="mt-1 font-mono text-lg font-bold tabular-nums tracking-tight text-text-primary sm:text-xl">
                {valueFor(key)}
              </dd>
            </div>
          ))}
          <div className="col-span-2 min-w-0 border-t border-border-subtle pt-3">
            <dt className="flex items-center gap-1.5 text-[9px] font-medium uppercase tracking-[0.14em] text-text-tertiary">
              <CalendarRange size={11} className="shrink-0 text-champagne/70" aria-hidden="true" />
              <span className="leading-snug">{t('home.scope.period.label')}</span>
            </dt>
            <dd className="mt-1 font-mono text-lg font-bold tabular-nums tracking-tight text-text-primary sm:text-xl">
              {t('home.scope.period.value')}
            </dd>
          </div>
        </dl>

        <div className="mt-3.5 border-t border-border-subtle pt-3">
          <p className="text-[9px] font-medium uppercase tracking-[0.14em] text-text-tertiary">
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
