import { Database, Globe2, Landmark, Network } from 'lucide-react';
import { useT } from '../../i18n';

const SCOPE_STATS = [
  { key: 'macro', icon: Landmark },
  { key: 'world', icon: Globe2 },
  { key: 'countries', icon: Network },
  { key: 'pages', icon: Database },
];

/**
 * Правая колонка hero главной: состав платформы в цифрах.
 * Официальная витрина масштаба: макроиндикаторы России, мировые показатели,
 * страны мира, объём страниц. Источники и режим обновления — снизу, как
 * гарантия достоверности, без маркетинговых оценок.
 */
export default function HomeDataScope() {
  const t = useT();

  return (
    <aside
      data-block="home-data-scope"
      className="relative overflow-hidden rounded-2xl border border-border-subtle bg-surface p-5 shadow-[0_22px_70px_rgba(35,30,16,0.06)] sm:p-6"
      aria-labelledby="home-data-scope-title"
    >
      <div className="pointer-events-none absolute -right-14 -top-16 h-48 w-48 rounded-full bg-champagne/10 blur-3xl" />

      <div className="relative">
        <div className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.2em] text-champagne">
          <Database size={12} className="shrink-0" />
          <h2 id="home-data-scope-title" className="font-semibold">
            {t('home.scope.title')}
          </h2>
        </div>

        <dl className="mt-5 grid grid-cols-2 gap-x-4 gap-y-5">
          {SCOPE_STATS.map(({ key, icon: Icon }) => (
            <div key={key} className="min-w-0">
              <dt className="flex items-center gap-1.5 text-[9px] font-medium uppercase tracking-[0.16em] text-text-tertiary">
                <Icon size={12} className="shrink-0 text-champagne/70" aria-hidden="true" />
                <span className="line-clamp-2 leading-snug">{t(`home.scope.stat.${key}.label`)}</span>
              </dt>
              <dd className="mt-1.5 font-mono text-xl font-bold tabular-nums tracking-tight text-text-primary sm:text-[1.55rem]">
                {t(`home.scope.stat.${key}.value`)}
              </dd>
            </div>
          ))}
        </dl>

        <div className="mt-6 border-t border-border-subtle pt-4">
          <p className="text-[9px] font-medium uppercase tracking-[0.16em] text-text-tertiary">
            {t('home.scope.sources.label')}
          </p>
          <p className="mt-1.5 text-[13px] font-medium leading-relaxed text-text-secondary">
            {t('home.scope.sources.list')}
          </p>
          <p className="mt-3 flex items-center gap-1.5 text-[11px] leading-snug text-text-tertiary">
            <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-champagne" aria-hidden="true" />
            {t('home.scope.update')}
          </p>
        </div>
      </div>
    </aside>
  );
}
