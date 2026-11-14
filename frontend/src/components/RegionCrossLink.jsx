// Мост «макро → регионы» на карточке индикатора: если у общероссийского
// показателя есть региональный аналог в сборнике «Регионы России», показываем
// блок со ссылками на карту и разрез по регионам. Маппинг живёт на бэкенде
// (MACRO_BY_TABLE в seo_regional.py) и приходит в каталоге регионов.
import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { MapPin, ArrowUpRight } from 'lucide-react';
import { useRegionsCatalog } from '../lib/regionsApi';
import { track, events } from '../lib/track';
import {
  regionIndicatorPath,
  regionMapPath,
  regionRatingPath,
} from '../lib/sitePaths';
import { useT } from '../i18n';

export default function RegionCrossLink({ macroCode }) {
  const t = useT();
  const { data } = useRegionsCatalog(!!macroCode);

  const regionInd = useMemo(() => {
    if (!data) return null;
    for (const sec of data.sections) {
      const hit = sec.indicators.find(i => i.macro_code === macroCode);
      if (hit) return hit;
    }
    return null;
  }, [data, macroCode]);

  if (!regionInd) return null;

  return (
    <section className="mt-12">
      <div className="rounded-2xl p-5 fe-glass-lite">
        <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-text-secondary">
          <MapPin size={13} className="text-champagne-ink" aria-hidden="true" />
          {t('indicator.regionCross.eyebrow')}
        </div>
        <p className="text-sm text-text-secondary leading-relaxed mb-3 max-w-2xl">
          {t('indicator.regionCross.body', {
            name: regionInd.name,
            year: regionInd.year_min,
          })}
        </p>
        <div className="flex flex-wrap gap-2">
          <Link
            to={regionMapPath(regionInd.code)}
            onClick={() => track(events.REGION_CROSSLINK_CLICK, { from: macroCode, to: 'regions-map' })}
            className="inline-flex min-h-9 items-center gap-1 px-3.5 py-1.5 rounded-full text-text-primary text-[13px] font-semibold transition-colors fe-glass-2 fe-press"
          >
            {t('indicator.regionCross.map')} <ArrowUpRight size={13} />
          </Link>
          <Link
            to={regionRatingPath(regionInd.code)}
            onClick={() => track(events.REGION_CROSSLINK_CLICK, { from: macroCode, to: `rating:${regionInd.code}` })}
            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-text-secondary text-[13px] font-medium hover:text-champagne transition-colors fe-glass-2"
          >
            {t('indicator.regionCross.rating')} <ArrowUpRight size={13} />
          </Link>
          <Link
            to={regionIndicatorPath('moskva', regionInd.code)}
            onClick={() => track(events.REGION_CROSSLINK_CLICK, { from: macroCode, to: `region:moskva:${regionInd.code}` })}
            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-text-secondary text-[13px] font-medium hover:text-champagne transition-colors fe-glass-2"
          >
            {t('indicator.regionCross.example')} <ArrowUpRight size={13} />
          </Link>
          <Link
            to={`/compare?codes=${macroCode},r:moskva:${regionInd.code}`}
            onClick={() => track(events.REGION_CROSSLINK_CLICK, { from: macroCode, to: 'compare-macro-region' })}
            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-text-secondary text-[13px] font-medium hover:text-champagne transition-colors fe-glass-2"
          >
            {t('indicator.regionCross.compare')} <ArrowUpRight size={13} />
          </Link>
        </div>
      </div>
    </section>
  );
}
