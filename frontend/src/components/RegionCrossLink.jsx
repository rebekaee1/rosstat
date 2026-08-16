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
      <div className="rounded-2xl border border-border-subtle bg-surface p-5">
        <div className="flex items-center gap-2 text-champagne text-xs font-mono uppercase tracking-widest mb-2">
          <MapPin size={13} />
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
            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full bg-champagne/10 text-champagne text-[13px] font-medium hover:bg-champagne/20 transition-colors"
          >
            {t('indicator.regionCross.map')} <ArrowUpRight size={13} />
          </Link>
          <Link
            to={regionRatingPath(regionInd.code)}
            onClick={() => track(events.REGION_CROSSLINK_CLICK, { from: macroCode, to: `rating:${regionInd.code}` })}
            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full border border-border-subtle text-text-secondary text-[13px] font-medium hover:text-champagne hover:border-border-champagne transition-colors"
          >
            {t('indicator.regionCross.rating')} <ArrowUpRight size={13} />
          </Link>
          <Link
            to={regionIndicatorPath('moskva', regionInd.code)}
            onClick={() => track(events.REGION_CROSSLINK_CLICK, { from: macroCode, to: `region:moskva:${regionInd.code}` })}
            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full border border-border-subtle text-text-secondary text-[13px] font-medium hover:text-champagne hover:border-border-champagne transition-colors"
          >
            {t('indicator.regionCross.example')} <ArrowUpRight size={13} />
          </Link>
          <Link
            to={`/compare?codes=${macroCode},r:moskva:${regionInd.code}`}
            onClick={() => track(events.REGION_CROSSLINK_CLICK, { from: macroCode, to: 'compare-macro-region' })}
            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full border border-border-subtle text-text-secondary text-[13px] font-medium hover:text-champagne hover:border-border-champagne transition-colors"
          >
            {t('indicator.regionCross.compare')} <ArrowUpRight size={13} />
          </Link>
        </div>
      </div>
    </section>
  );
}
