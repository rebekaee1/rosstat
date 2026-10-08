// «Сравнить с другим регионом»: выбор второго региона на странице региона. После выбора открывается
// готовое сравнение двух регионов (/russia/region-vs/…), без дополнительных шагов.
import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronDown, GitCompare } from 'lucide-react';
import { useRegionsLanding } from '../../lib/regionsApi';
import { regionVsPath } from '../../lib/sitePaths';
import { useLocale } from '../../i18n';
import '../../styles/regions-w4.css';

export default function RegionComparePick({ slug }) {
  const { t, locale } = useLocale();
  const navigate = useNavigate();
  const { data } = useRegionsLanding();

  const options = useMemo(() => {
    const all = [];
    (data?.districts || []).forEach((d) => d.regions.forEach((r) => {
      if (r.slug && r.slug !== slug) all.push({ slug: r.slug, name: r.name });
    }));
    const collator = new Intl.Collator(locale === 'en' ? 'en' : 'ru');
    return all.sort((a, b) => collator.compare(a.name, b.name));
  }, [data, slug, locale]);

  if (options.length === 0) return null;
  return (
    <label className="fe-reg-pick" data-testid="region-compare-pick">
      <GitCompare size={14} className="fe-reg-pick__icon" aria-hidden="true" />
      <span className="sr-only">{t('c9e.reg.compareWith')}</span>
      <select
        className="fe-reg-pick__select"
        value=""
        aria-label={t('c9e.reg.compareWith')}
        onChange={(e) => { if (e.target.value) navigate(regionVsPath(slug, e.target.value)); }}
      >
        <option value="">{t('c9e.reg.compareWith')}</option>
        {options.map((o) => <option key={o.slug} value={o.slug}>{o.name}</option>)}
      </select>
      <ChevronDown size={14} className="fe-reg-pick__chev" aria-hidden="true" />
    </label>
  );
}
