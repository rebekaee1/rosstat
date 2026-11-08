// Круг 3 (R3-A): «Цены и курсы под рукой». Главная была про мир; здесь человек из поиска «цены на продукты по регионам» или «курс сума»
// находит свой регион и курсы ЦБ за одно касание. Данные уже загружены главной (список показателей) или лёгкие (список регионов).
import { useId, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Coins, ShoppingBasket } from 'lucide-react';
import { useIndicators } from '../../lib/hooks';
import { useRegionsLanding } from '../../lib/regionsApi';
import { TRAVEL_UNITS, buildEdges, convert, formatConverted, unitWord } from '../../lib/currencyRates';
import { regionPath, russiaIndicatorPath } from '../../lib/sitePaths';
import { RATES_TO } from '../../lib/navItems';
import { track, events } from '../../lib/track';
import { useLocale, useT } from '../../i18n';
import '../../styles/z3-home.css';
import '../../styles/r3a-home.css';

const STORE_KEY = 'fe-home-region';

function readSaved() {
  try { return window.localStorage.getItem(STORE_KEY) || ''; } catch { return ''; }
}

function RegionPrices() {
  const t = useT();
  const { locale } = useLocale();
  const id = useId();
  const landing = useRegionsLanding();
  const regions = useMemo(() => {
    const collator = new Intl.Collator(locale === 'en' ? 'en' : 'ru');
    const list = (landing.data?.districts || []).flatMap((d) => d.regions || []);
    return list
      .map((r) => ({ slug: r.slug, name: (locale === 'en' ? r.name_en : r.name_ru) || r.name }))
      .sort((a, b) => collator.compare(a.name, b.name));
  }, [landing.data, locale]);
  const [picked, setPicked] = useState(readSaved);
  const value = regions.some((r) => r.slug === picked) ? picked : (regions.find((r) => r.slug === 'moskva') || regions[0])?.slug || '';
  const total = landing.data?.totals?.regions || 85;
  const onPick = (slug) => {
    setPicked(slug);
    try { window.localStorage.setItem(STORE_KEY, slug); } catch { /* память браузера необязательна */ }
  };
  return (
    <article className="fe-tool fe-reveal fe-r3a-card">
      <header className="fe-tool__head">
        <span className="fe-tool__icon" aria-hidden="true"><ShoppingBasket size={18} /></span>
        <div className="min-w-0">
          <h3 className="fe-tool__title">{t('r3a.prices.title')}</h3>
          <p className="fe-tool__lead">{t('r3a.prices.lead', { n: total })}</p>
        </div>
      </header>
      <div className="fe-tool__body">
        <label className="fe-tool__field fe-tool__field--wide" htmlFor={`${id}-region`}>
          <span className="fe-tool__label">{t('r3a.prices.pick')}</span>
          <select id={`${id}-region`} className="fe-tool__input" value={value} onChange={(e) => onPick(e.target.value)} disabled={!regions.length}>
            {regions.length ? regions.map((r) => <option key={r.slug} value={r.slug}>{r.name}</option>) : <option value="">…</option>}
          </select>
        </label>
        <ul className="fe-r3a-goods" aria-hidden="true">
          {['eggs', 'milk', 'fuel', 'bread', 'meds'].map((k) => <li key={k}>{t(`r3a.prices.g.${k}`)}</li>)}
        </ul>
      </div>
      {value ? (
        <Link
          to={regionPath(value)}
          onClick={() => track(events.HOME_CATEGORY_CLICK, { category: 'region-prices', surface: 'home-r3a' })}
          className="fe-r3a-cta fe-press"
        >
          {t('r3a.prices.go')}
          <ArrowRight size={16} aria-hidden="true" />
        </Link>
      ) : null}
    </article>
  );
}

function RateTiles() {
  const t = useT();
  const { locale } = useLocale();
  const indicators = useIndicators();
  const edges = useMemo(() => buildEdges(indicators.data || []), [indicators.data]);
  const tiles = useMemo(() => TRAVEL_UNITS.map((unit) => {
    const edge = edges.find((e) => e.from === unit && e.to === 'RUB');
    const res = edge ? convert(1000, 'RUB', unit, edges) : null;
    if (!edge || !res) return null;
    const rounded = Math.round(res.value);
    return { unit, to: russiaIndicatorPath(edge.code), num: formatConverted(res.value, locale), word: unitWord(rounded, unit, locale) };
  }).filter(Boolean).slice(0, 6), [edges, locale]);
  return (
    <article className="fe-tool fe-reveal fe-r3a-card">
      <header className="fe-tool__head">
        <span className="fe-tool__icon" aria-hidden="true"><Coins size={18} /></span>
        <div className="min-w-0">
          <h3 className="fe-tool__title">{t('r3a.rates.title')}</h3>
          <p className="fe-tool__lead">{t('r3a.rates.lead', { n: edges.length || 54 })}</p>
        </div>
      </header>
      <div className="fe-tool__body">
        {tiles.length ? (
          <ul className="fe-r3a-rates">
            {tiles.map((tile) => (
              <li key={tile.unit}>
                <Link to={tile.to} className="fe-r3a-rate fe-press" onClick={() => track(events.HOME_CATEGORY_CLICK, { category: 'rate-tile', surface: 'home-r3a', unit: tile.unit })}>
                  <span className="fe-r3a-rate__from">{t('r3a.rates.for')}</span>
                  <span className="fe-r3a-rate__num">{tile.num}</span>
                  <span className="fe-r3a-rate__word">{tile.word}</span>
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <ul className="fe-r3a-rates" aria-hidden="true">
            {TRAVEL_UNITS.slice(0, 6).map((u) => <li key={u}><span className="fe-r3a-rate fe-r3a-rate--ghost" /></li>)}
          </ul>
        )}
      </div>
      <Link to={RATES_TO} className="fe-r3a-cta fe-press">
        {t('r3a.rates.go')}
        <ArrowRight size={16} aria-hidden="true" />
      </Link>
    </article>
  );
}

export default function HomePricesRates() {
  const t = useT();
  const { locale } = useLocale();
  return (
    <section data-block="home-prices-rates" className="fe-tools fe-r3a" aria-labelledby="home-r3a-title">
      <div className="fe-tools__head">
        <h2 id="home-r3a-title" className="fe-tools__title">{t('r3a.title')}</h2>
        <p className="fe-tools__sub">{t('r3a.sub')}</p>
      </div>
      <div className="fe-tools__grid fe-r3a-grid">
        <RegionPrices key={`p-${locale}`} />
        <RateTiles key={`r-${locale}`} />
      </div>
    </section>
  );
}
