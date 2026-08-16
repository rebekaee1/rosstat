import { createElement } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, BarChart3, Globe2, MapPin } from 'lucide-react';
import {
  regionHubPath,
  worldHubPath,
} from '../../lib/sitePaths';
import { useT } from '../../i18n';

const TOOLS = [
  {
    to: '/compare',
    titleKey: 'home.tools.compare.title',
    descKey: 'home.tools.compare.desc',
    icon: BarChart3,
  },
  {
    to: regionHubPath(),
    titleKey: 'home.tools.regions.title',
    descKey: 'home.tools.regions.desc',
    icon: MapPin,
  },
  {
    to: worldHubPath(),
    titleKey: 'home.tools.countries.title',
    descKey: 'home.tools.countries.desc',
    icon: Globe2,
  },
];

export default function HomeTools() {
  const t = useT();
  return (
    <section data-block="home-tools" className="mb-10 md:mb-12" aria-labelledby="home-tools-title">
      <div className="mb-4 flex items-center gap-4">
        <h2 id="home-tools-title" className="text-xs font-semibold uppercase tracking-[0.2em] text-text-secondary">
          {t('home.tools.title')}
        </h2>
        <div className="h-px flex-1 bg-border-subtle" />
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {TOOLS.map(({ to, titleKey, descKey, icon }) => (
          <Link
            key={to}
            to={to}
            className="group flex items-start gap-3 rounded-xl border border-border-subtle bg-surface px-4 py-3.5 transition-all hover:border-border-champagne hover:shadow-sm"
          >
            <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-champagne/10 text-champagne">
              {createElement(icon, { size: 15 })}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1 text-sm font-semibold text-text-primary group-hover:text-champagne">
                {t(titleKey)}
                <ArrowRight size={12} className="opacity-0 transition-opacity group-hover:opacity-100" />
              </div>
              <p className="mt-0.5 text-[12px] leading-snug text-text-secondary">{t(descKey)}</p>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}
