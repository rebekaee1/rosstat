import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Link } from 'react-router-dom';
import { formatDate } from '../lib/format';
import { formatDeltaWithUnit } from '../lib/deltaText';
import { formatPercentChangeFine } from '../lib/indicatorSummary';
import { splitUnit } from '../lib/countryFlag';
import { relatedIndicatorCardCopy } from '../lib/indicatorVariants';
import { russiaIndicatorPath } from '../lib/sitePaths';
import { track, events } from '../lib/track';
import { useLocale, useT } from '../i18n';
import { glueDate } from '../lib/periodPhrase';
import DeltaBadge from './DeltaBadge';
import '../styles/r6b-pulse.css';

/**
 * R6-B. Полоса под названием на телефоне: изменение к прошлому значению (на компьютере его показывает
 * блок справа, на телефоне блок скрыт и число стояло без изменения) и быстрые переходы к связанным показателям.
 * Прогноз тут не показывается.
 */
export default function R6bPulseStrip({
  summary, polarity = 'neutral', deltaSuffix = '', dateFormat, related = [], code, category,
}) {
  const t = useT();
  const { locale } = useLocale();
  const sentinel = useRef(null);
  const [bar, setBar] = useState(null);
  // Когда главное число уходит за верх экрана, оно остаётся тонкой строкой под шапкой сайта: число видно при чтении таблицы и описания.
  useEffect(() => {
    if (!summary || typeof window === 'undefined') return undefined;
    let raf = 0;
    const update = () => {
      raf = 0;
      const el = sentinel.current;
      if (!el || window.innerWidth >= 768) { setBar((b) => (b === null ? b : null)); return; }
      const head = document.querySelector('nav.fe-navbar');
      const top = head ? Math.round(head.getBoundingClientRect().bottom) + 6 : 90;
      const gone = el.getBoundingClientRect().bottom < top - 6;
      setBar((b) => {
        if (!gone) return b === null ? b : null;
        return b === top ? b : top;
      });
    };
    const onScroll = () => { if (!raf) raf = window.requestAnimationFrame(update); };
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll);
    update();
    return () => {
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', onScroll);
      if (raf) window.cancelAnimationFrame(raf);
    };
  }, [summary]);
  const chips = (related || []).filter((r) => r?.code && r.code !== code).slice(0, 6);
  let delta = null;
  if (summary?.prev) {
    const { kind, shown, changeAbs, changePct, prev } = summary;
    const useAbs = kind === 'rate';
    const unitText = splitUnit(shown.unit).short;
    const abs = useAbs
      ? formatDeltaWithUnit(changeAbs, unitText.startsWith('%') ? '%' : unitText, { digits: shown.digits, locale })
      : null;
    const pctText = useAbs ? null : formatPercentChangeFine(changePct, locale);
    const known = useAbs ? changeAbs != null : changePct != null;
    if (known) {
      const flat = useAbs ? abs.flat : pctText == null;
      delta = flat ? (
        <p className="r6b-pulse__delta" data-testid="r6b-delta">
          <DeltaBadge delta={0}>{t('w6e.delta.flat')}</DeltaBadge>
          <span className="r6b-pulse__since">{t('r6b.flatSince', { date: formatDate(prev.date, dateFormat, locale) })}</span>
        </p>
      ) : (
        <p className="r6b-pulse__delta" data-testid="r6b-delta">
          <DeltaBadge delta={useAbs ? changeAbs : changePct} polarity={polarity}>
            {useAbs ? abs.text : pctText}
          </DeltaBadge>
          {deltaSuffix ? <span className="r6b-pulse__since">{deltaSuffix}</span> : null}
        </p>
      );
    }
  }
  if (!delta && !chips.length) return null;
  const unitShort = summary ? splitUnit(summary.shown.unit).short : '';
  return (
    <div className="r6b-pulse" ref={sentinel}>
      {summary && bar !== null ? createPortal(
        <button
          type="button"
          className="r6b-pulse__bar"
          style={{ top: bar }}
          data-testid="r6b-sticky"
          aria-label={t('r6b.toTop')}
          onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
        >
          <strong>{summary.shown.text}{unitShort && !/^(индекс|index)$/i.test(unitShort) ? ` ${unitShort}` : ''}</strong>
          <span className="r6b-pulse__bar-when">{glueDate(formatDate(summary.last.date, dateFormat, locale))}</span>
        </button>,
        document.body,
      ) : null}
      {delta}
      {chips.length ? (
        <nav className="r6b-pulse__chips" aria-label={t('r6b.related')}>
          {chips.map((rel) => (
            <Link
              key={rel.code}
              to={russiaIndicatorPath(rel.code)}
              className="r6b-pulse__chip fe-press"
              onClick={() => track(events.RELATED_INDICATOR_CLICK, {
                from: code, to: rel.code, indicatorCategory: category, surface: 'indicator-hero-chip',
              })}
            >
              {relatedIndicatorCardCopy(rel.code, rel.name, rel.unit).title}
            </Link>
          ))}
        </nav>
      ) : null}
    </div>
  );
}
