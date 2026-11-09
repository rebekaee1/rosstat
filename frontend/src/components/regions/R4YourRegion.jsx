/* eslint-disable react-refresh/only-export-components -- medianOf — малый чистый помощник */
// R4-A: «Ваш регион» на странице рейтинга: выбрал своё место жизни и сразу видишь, как его значение
// соотносится с типичным по стране. Без мест в рейтинге: только значения и разница в процентах.
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { GitCompare } from 'lucide-react';
import { formatRegionWithUnit } from '../../lib/regionUi';
import { regionVsPath } from '../../lib/sitePaths';
import { useLocale } from '../../i18n';
import '../../styles/r4a-compare-prices.css';

const KEY = 'r4a-my-region';

function readSaved() {
  try { return window.localStorage.getItem(KEY) || ''; } catch { return ''; }
}

/** Медиана значений — «типичный» регион, не искажённый столицами. */
export function medianOf(values) {
  const v = values.filter((x) => Number.isFinite(x)).sort((a, b) => a - b);
  if (!v.length) return null;
  const m = Math.floor(v.length / 2);
  return v.length % 2 ? v[m] : (v[m - 1] + v[m]) / 2;
}

export default function R4YourRegion({ rows, unit, cheapestSlug }) {
  const { t, locale } = useLocale();
  const [slug, setSlug] = useState(() => readSaved());
  const options = [...rows].sort((x, y) => String(x.name).localeCompare(String(y.name), locale === 'en' ? 'en' : 'ru'));
  const mine = rows.find((r) => r.slug === slug);
  const val = (r) => Number(r.raw ?? r.value);
  const med = medianOf(rows.map(val));
  const diff = mine && med ? ((val(mine) - med) / med) * 100 : null;
  const pick = (v) => {
    setSlug(v);
    try { window.localStorage.setItem(KEY, v); } catch { /* память недоступна — не страшно */ }
  };
  const pct = diff == null ? '' : Math.abs(diff).toLocaleString(locale === 'en' ? 'en-US' : 'ru-RU', { maximumFractionDigits: 1 });
  return (
    <section className="fe-panel r4a-your" data-testid="r4a-your-region">
      <label className="r4a-your__field">
        <span className="r4a-your__label">{t('r4a.your.label')}</span>
        <select className="r3b-pair__select" value={mine ? slug : ''} onChange={(e) => pick(e.target.value)}>
          <option value="">{t('r4a.your.pick')}</option>
          {options.map((o) => <option key={o.slug} value={o.slug}>{o.name}</option>)}
        </select>
      </label>
      {mine && med != null && (
        <>
          <p className="r4a-your__text" data-testid="r4a-your-text">
            {t('r4a.your.value', { name: mine.name, value: formatRegionWithUnit(val(mine), unit, locale) })}
            {' '}
            {Math.abs(diff) < 0.5
              ? t('r4a.your.typical')
              : t(diff > 0 ? 'r4a.your.more' : 'r4a.your.less', { pct, typical: formatRegionWithUnit(med, unit, locale) })}
          </p>
          {cheapestSlug && cheapestSlug !== slug && (
            <Link to={regionVsPath(slug, cheapestSlug)} className="r3b-vs-link fe-tap-inline">
              <GitCompare size={14} aria-hidden="true" />
              {t('r4a.your.compare')}
            </Link>
          )}
        </>
      )}
    </section>
  );
}
