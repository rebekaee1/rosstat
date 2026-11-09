// Круг 9 (R9-A): живые цены на главной. Раньше карточка «Цены в вашем регионе» была текстом «яйца, молоко… и ещё сотни товаров»:
// новичок из Google не видел ни одной цены. Теперь шесть ходовых позиций с числом, изменением за год и ссылкой сразу на цену
// выбранного региона (одно касание от главной до своей цены), под ними чипы групп с числом позиций.
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Minus, TrendingDown, TrendingUp } from 'lucide-react';
import { useHomePriceSummary } from '../../lib/homePriceSummary';
import { formatValue } from '../../lib/format';
import { enMoney, enPerLabel, enTileName } from '../../lib/r10aUnits';
import { regionIndicatorPath, regionPath } from '../../lib/sitePaths';
import { track, events } from '../../lib/track';
import { useLocale, useT } from '../../i18n';
import '../../styles/r9a-home.css';

const SHOWN = 6;

function unitParts(unit) {
  const m = String(unit || '').match(/^(?:рублей|рубля|рубль|roubles|rubles)\s*(.*)$/i);
  if (!m) return { sign: '', per: String(unit || '') };
  const per = m[1]
    .replace(/килограмм(?![\p{L}])/iu, 'кг')
    .replace(/штук(?![\p{L}])/iu, 'шт.')
    .replace(/литр(?![\p{L}])/iu, 'л');
  return { sign: '\u00a0₽', per };
}

function Trend({ pct, locale, label }) {
  if (pct == null) return <span className="r9a-tile__trend" aria-hidden="true">{'\u00a0'}</span>;
  const flat = Math.abs(pct) < 0.05;
  const Icon = flat ? Minus : pct > 0 ? TrendingUp : TrendingDown;
  const body = flat ? '0\u00a0%' : `${pct > 0 ? '+' : '−'}${formatValue(Math.abs(pct), Math.abs(pct) < 10 ? 1 : 0, locale)}\u00a0%`;
  return (
    <span className={`r9a-tile__trend${flat ? '' : pct > 0 ? ' is-up' : ' is-down'}`}>
      <Icon size={13} aria-hidden="true" />
      {body}
      <span className="r9a-tile__trend-l">{label}</span>
    </span>
  );
}

export default function HomeRegionPriceTiles({ region, regionName }) {
  const t = useT();
  const { locale } = useLocale();
  const { data, isLoading } = useHomePriceSummary();
  const items = Array.isArray(data?.items) ? data.items.slice(0, SHOWN) : [];
  const groups = Array.isArray(data?.groups) ? data.groups.filter((g) => g?.count > 0).slice(0, 6) : [];
  if (isLoading) {
    return (
      <ul className="r9a-tiles" aria-hidden="true">
        {Array.from({ length: SHOWN }).map((_, i) => <li key={i}><span className="r9a-tile r9a-tile--ghost" /></li>)}
      </ul>
    );
  }
  if (!items.length) return null;
  return (
    <div className="r9a-prices" data-block="home-price-tiles">
      <p className="r9a-prices__cap">{t('r9a.tiles.cap', { period: items[0].period_label || '' })}</p>
      <ul className="r9a-tiles">
        {items.map((it) => {
          const en = locale === 'en';
          const { sign, per: perRu } = unitParts(it.unit);
          const per = en ? enPerLabel(it.unit) : perRu;
          const digits = it.value >= 1000 ? 0 : 2;
          const valText = formatValue(it.value, digits, locale);
          return (
            <li key={it.code}>
              <Link
                to={regionIndicatorPath(region || 'russia', it.code)}
                className="r9a-tile fe-press"
                onClick={() => track(events.HOME_CATEGORY_CLICK, { category: 'price-tile', surface: 'home-r9a', code: it.code, region })}
              >
                <span className="r9a-tile__name">{en ? enTileName(it) : (it.short_name || it.name)}</span>
                <span className="r9a-tile__val">{en ? enMoney(valText) : `${valText}${sign}`}</span>
                <span className="r9a-tile__per">{per}</span>
                <Trend pct={it.yoy_pct} locale={locale} label={t('r9a.tiles.year')} />
              </Link>
            </li>
          );
        })}
      </ul>
      <p className="r9a-prices__note">{t('r9a.tiles.note', { name: regionName || '' })}</p>
      {groups.length ? (
        <ul className="r9a-groups scrollbar-hide" aria-label={t('r9a.groups.aria')}>
          {groups.map((g) => (
            <li key={g.group}>
              <Link to={regionPath(region || 'russia')} className="r9a-group fe-press">
                {g.label || g.group}
                <span className="r9a-group__n">{g.count}</span>
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function savedRegion() {
  try { return window.localStorage.getItem('fe-home-region') || 'moskva'; } catch { return 'moskva'; }
}

/**
 * Лента цен в первом экране телефона (R9-A): хлеб, молоко, яйца, бензин с числом сразу под выбором региона, чтобы человек из поиска
 * «цены на продукты» видел цены, не доскролливая до карточки ниже. Плитка ведёт на цену выбранного региона. На компьютере не показывается.
 */
export function HomePriceStrip() {
  const t = useT();
  const { locale } = useLocale();
  const { data } = useHomePriceSummary();
  const [region, setRegion] = useState(savedRegion);
  useEffect(() => {
    const on = (e) => setRegion(e?.detail || savedRegion());
    window.addEventListener('fe:home-region', on);
    return () => window.removeEventListener('fe:home-region', on);
  }, []);
  const items = Array.isArray(data?.items) ? data.items.slice(0, 8) : [];
  if (!items.length) return null;
  return (
    <>
    <p className="r9a-strip__cap">{t('r9a.tiles.cap', { period: items[0].period_label || '' })}</p>
    <ul className="r9a-strip scrollbar-hide fe-fade-x" data-block="home-price-strip" aria-label={t('r9a.strip.aria')}>
      {items.map((it) => {
        const en = locale === 'en';
        const { sign, per: perRu } = unitParts(it.unit);
        const per = en ? enPerLabel(it.unit) : perRu;
        const valText = formatValue(it.value, it.value >= 1000 ? 0 : 2, locale);
        return (
          <li key={it.code}>
            <Link
              to={regionIndicatorPath(region || 'russia', it.code)}
              className="r9a-chip fe-press"
              onClick={() => track(events.HOME_CATEGORY_CLICK, { category: 'price-strip', surface: 'home-r9a', code: it.code, region })}
            >
              <span className="r9a-chip__name">{en ? enTileName(it) : (it.short_name || it.name)}</span>
              <span className="r9a-chip__val">{en ? enMoney(valText) : `${valText}${sign}`}</span>
              <span className="r9a-chip__per">{per}</span>
            </Link>
          </li>
        );
      })}
    </ul>
    </>
  );
}
