import { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Copy, Check, Share2 } from 'lucide-react';
import { formatValue } from '../lib/format';
import { splitPriceUnit, signed, money, quoteLine } from '../lib/r9bPrice';
import { regionIndicatorPath } from '../lib/sitePaths';
import { track, events } from '../lib/track';
import { useLocale, useT } from '../i18n';
import '../styles/r9b-movers.css';

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    try {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand('copy');
      document.body.removeChild(ta);
      return ok;
    } catch {
      return false;
    }
  }
}

export default function R9PriceMovers({ movers, surface = 'category', headingLevel = 3 }) {
  const t = useT();
  const { locale } = useLocale();
  const [tab, setTab] = useState('up');
  const [open, setOpen] = useState(false);
  const [done, setDone] = useState('');
  const timer = useRef(null);

  const up = movers?.up || [];
  const down = movers?.down || [];
  if (up.length + down.length === 0) return null;
  const active = (tab === 'down' && down.length) || !up.length ? 'down' : 'up';
  const list = active === 'down' ? down : up;
  const FOLD = 5;
  const rows = open ? list : list.slice(0, FOLD);
  const maxAbs = Math.max(...list.map((r) => Math.abs(r.yoy_pct)), 1);
  const H = `h${headingLevel}`;
  const month = movers.period_label || '';

  const flash = (key) => {
    setDone(key);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setDone(''), 2200);
  };
  const copyOne = async (it) => {
    track(events.RELATED_LINK_CLICK, { from: 'r9b-copy', to: it.code, surface });
    if (await copyText(quoteLine(it, t, locale))) flash(it.code);
  };
  const header = t(active === 'up' ? 'r9b.copyHeadUp' : 'r9b.copyHeadDown', { month });
  const allText = () => `${header}\n${list.map((it) => `• ${quoteLine(it, t, locale)}`).join('\n')}\n${t('r9b.source')}`;
  const copyAll = async () => {
    track(events.RELATED_LINK_CLICK, { from: 'r9b-copy-all', to: active, surface });
    if (await copyText(allText())) flash('all');
  };
  const canShare = typeof navigator !== 'undefined' && typeof navigator.share === 'function';
  const share = async () => {
    track(events.RELATED_LINK_CLICK, { from: 'r9b-share', to: active, surface });
    try {
      await navigator.share({ title: header, text: allText(), url: `${window.location.href.split('#')[0]}#price-movers` });
    } catch { /* окно закрыли */ }
  };

  return (
    <div className="r9b-movers" id="price-movers" data-block="russia-price-movers">
      <div className="r9b-movers__head">
        <H className="r9b-movers__title">{t('r9b.title')}</H>
        <div className="r9b-seg" role="tablist" aria-label={t('r9b.title')}>
          {[['up', t('r9b.up'), up.length], ['down', t('r9b.down'), down.length]].map(([k, label, n]) => (
            <button
              key={k}
              type="button"
              role="tab"
              aria-selected={active === k}
              disabled={n === 0}
              className={`r9b-seg__b fe-press${active === k ? ' is-on' : ''}`}
              onClick={() => { setTab(k); setOpen(false); }}
            >{label}</button>
          ))}
        </div>
      </div>
      <p className="r9b-movers__sub">{t('r9b.sub', { month, n: movers.count || '' })}</p>
      <ol className="r9b-list">
        {rows.map((it, i) => {
          const { per } = splitPriceUnit(it.unit);
          const w = Math.max(6, Math.round((Math.abs(it.yoy_pct) / maxAbs) * 100));
          return (
            <li key={it.code} className={`r9b-row r9b-row--${active}`}>
              <span className="r9b-row__rank" aria-hidden="true">{i + 1}</span>
              <Link
                to={regionIndicatorPath('russia', it.code)}
                className="r9b-row__main fe-press"
                onClick={() => track(events.RELATED_LINK_CLICK, { from: 'r9b-mover', to: it.code, surface })}
              >
                <span className="r9b-row__name">{it.short_name || it.name}</span>
                <span className="r9b-row__was">
                  {t('r9b.was', { then: formatValue(it.year_ago_value, it.year_ago_value >= 1000 ? 0 : 2, locale), now: money(it.value, it.unit, locale) })}
                  {per ? <span className="r9b-row__per">{` · ${per}`}</span> : null}
                </span>
                <span className="r9b-row__bar" aria-hidden="true"><i style={{ width: `${w}%` }} /></span>
              </Link>
              <span className="r9b-row__pct">{signed(it.yoy_pct, locale)}</span>
              <button
                type="button"
                className="r9b-copy fe-press"
                aria-label={t('r9b.copyOne', { name: it.short_name || it.name })}
                onClick={() => copyOne(it)}
              >
                {done === it.code ? <Check size={16} aria-hidden="true" /> : <Copy size={16} aria-hidden="true" />}
              </button>
            </li>
          );
        })}
      </ol>
      {list.length > FOLD && (
        <button type="button" className="r9b-more fe-press" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
          {open ? t('r7d.less') : t('r9b.more', { n: list.length - FOLD })}
        </button>
      )}
      <div className="r9b-foot">
        <p className="r9b-foot__src">
          {t('r9b.sourceLead')}{' '}
          <a href="https://www.fedstat.ru" target="_blank" rel="noopener noreferrer">{t('r9b.sourceName')}</a>
          {month ? `, ${month}` : ''}. {t('r9b.method')}
        </p>
        <div className="r9b-foot__act">
          <button type="button" className="r9b-act fe-press" onClick={copyAll}>
            {done === 'all' ? <Check size={15} aria-hidden="true" /> : <Copy size={15} aria-hidden="true" />}
            {done === 'all' ? t('r9b.copied') : t('r9b.copyAll')}
          </button>
          {canShare && (
            <button type="button" className="r9b-act fe-press" onClick={share}>
              <Share2 size={15} aria-hidden="true" />{t('r9b.share')}
            </button>
          )}
        </div>
      </div>
      <span className="r9b-sr" role="status" aria-live="polite">{done ? t('r9b.copied') : ''}</span>
    </div>
  );
}
