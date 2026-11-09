// Страница цены региона (месячный ряд): пометка о снятом ряде, сравнение цифрой, «Ещё в разделе» по группам.
// Поля short_name / price_group / is_discontinued / last_month / compare приходят от API; если их нет — блоки не рисуются.
import { useState } from 'react';
import { Check, Copy } from 'lucide-react';
import { NBSP } from '../../lib/regionUi';
import { Link } from 'react-router-dom';
import { ArrowUpRight, ChevronDown } from 'lucide-react';
import { useLocale } from '../../i18n';
import { glueNumbers } from '../../lib/regionUi';
import { regionIndicatorPath, regionPath } from '../../lib/sitePaths';
import { compareFill, groupSiblings, pairLabel, pairSiblings, perAreaUnit, priceText, roundBig, signedPct, ymLabel } from '../../lib/z2Price';
import { GOODS_GROUP, splitGoods } from './RegionPricesSubgroups';
import '../../styles/z2-price.css';
import '../../styles/r5a-price.css';
import '../../styles/r8c-price.css';

const GROUP_KEYS = {
  'Продукты': 'z2.group.food',
  'ЖКХ': 'z2.group.utilities',
  'Транспорт': 'z2.group.transport',
  'Связь': 'z2.group.telecom',
  'Жильё': 'z2.group.housing',
  'Услуги': 'z2.group.services',
  'Лекарства': 'z2.group.medicine',
  'Одежда и товары': 'z2.group.goods',
  'Отдых': 'z2.group.leisure',
  'Топливо': 'z2.group.fuel',
  'Прочее': 'z2.group.other',
};
const PER_GROUP = 6;

/** Спокойная пометка: Росстат ряд больше не публикует. */
export function DiscontinuedNote() {
  const { t } = useLocale();
  return (
    <p className="z2p-note" role="note">
      {t('r2z2.discNote')}
    </p>
  );
}

/** «Россия: 98,1 ₽ (здесь +6,3 %)» — цифрой под главной ценой. */
export function CompareLines({ rows, unit, lastMonth, nation = false }) {
  const { t, locale } = useLocale();
  if (!rows.length) return null;
  return (
    <ul className="z2p-compare" aria-label={t('z2.compareAria')}>
      {rows.map((r) => {
        const sameMonth = !r.month || !lastMonth || String(r.month).replace(/\D/g, '') === String(lastMonth).replace(/\D/g, '');
        return (
          <li key={r.key}>
            <span className="z2p-compare__name">{t(r.key === 'russia' ? 'z2.russia' : 'z2.moskva')}</span>
            <span className="fe-num z2p-compare__val">{priceText(roundBig(r.value), unit, locale)}</span>
            <span className="fe-num z2p-compare__pct">{Math.abs(r.pct) < 0.05 ? t(nation ? 'r8c.natSame' : 'r2z2.hereSame') : t(r.pct > 0 ? (nation ? 'r8c.natHigher' : 'r2z2.hereHigher') : (nation ? 'r8c.natLower' : 'r2z2.hereLower'), { pct: signedPct(Math.abs(r.pct), locale).replace(/^[+−]/, '') })}</span>
            {!sameMonth && <span className="z2p-compare__month">{ymLabel(r.month, locale)}</span>}
            <span className="r5a-bar r8c-bar" aria-hidden="true">
              <i style={{ width: `${Math.round(compareFill(r.pct) * 100)}%` }} />
              {r.pct > 0.05 && <b style={{ left: `${Math.round(100 / (1 + r.pct / 100))}%` }} />}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

function SiblingRow({ s, slug, pageMonth }) {
  const { t, locale } = useLocale();
  const value = s.value ?? s.last_value ?? null;
  const month = ymLabel(s.last_month ?? s.month, locale);
  const dead = !!s.is_discontinued;
  const rawM = String(s.last_month ?? s.month ?? '').replace(/\D/g, '');
  const sameAsPage = !dead && !!pageMonth && rawM === String(pageMonth).replace(/\D/g, '');
  return (
    <li className="min-w-0">
      <Link
        to={regionIndicatorPath(slug, s.code)}
        className={`z2p-row fe-tap fe-press fe-glass-lite fe-float${dead ? ' is-dead' : ''}`}
      >
        <span className="z2p-row__name">{glueNumbers(s.short_name || s.name)}</span>
        <span className="z2p-row__meta">
          {value != null && <span className="fe-num z2p-row__val">{priceText(value, s.unit, locale)}</span>}
          {month && !sameAsPage && (
            <span className="z2p-row__month">{dead ? t('z2.until', { month }) : month}</span>
          )}
        </span>
        <ArrowUpRight size={14} className="z2p-row__arrow" aria-hidden="true" />
      </Link>
    </li>
  );
}

function Group({ label, items, slug, open, onToggle, pageMonth }) {
  const { t } = useLocale();
  const shown = open ? items : items.slice(0, PER_GROUP);
  return (
    <section className="z2p-group">
      <h3 className="z2p-group__title">{label}<span className="z2p-group__count fe-num">{items.length}</span></h3>
      <ul className="grid gap-2 sm:grid-cols-2">
        {shown.map((s) => <SiblingRow key={s.code} s={s} slug={slug} pageMonth={pageMonth} />)}
      </ul>
      {items.length > PER_GROUP && (
        <button type="button" className="z2p-more fe-tap-inline" onClick={onToggle} aria-expanded={open}>
          {open ? t('z2.less') : t('z2.more', { n: items.length - PER_GROUP })}
          <ChevronDown size={14} className={open ? 'is-open' : ''} aria-hidden="true" />
        </button>
      )}
    </section>
  );
}

/** «Ещё в разделе»: группы цен, группа текущей позиции первой, живые раньше снятых; ссылка «Все цены региона». */
export default function GroupedSiblings({ siblings, currentGroup, slug, section, regionName, pageMonth }) {
  const { t } = useLocale();
  const [openGroups, setOpenGroups] = useState({});
  const groups = groupSiblings(siblings, currentGroup);
  if (!groups) return null;
  // R8-E: самая длинная группа «Одежда и товары» делится на подгруппы (дом, техника, одежда…), как на странице региона.
  const parts = groups.flatMap((g) => (g.group === GOODS_GROUP && g.items.length > PER_GROUP * 2
    ? splitGoods(g.items).map((p) => ({ group: `${g.group}:${p.key}`, items: p.items, label: t(`r8b.sub.${p.key}`) }))
    : [g]));
  return (
    <div className="z2p-siblings">
      <div className="z2p-siblings__head">
        <h2 className="text-sm font-semibold text-text-primary">{t('regions.ind.moreInSection', { section })}</h2>
        <Link to={regionPath(slug)} className="z2p-all fe-tap-inline">
          {t('z2.allPrices', { region: regionName })}
          <ArrowUpRight size={13} aria-hidden="true" />
        </Link>
      </div>
      {parts.map((g) => (
        <Group
          key={g.group}
          label={g.label || (GROUP_KEYS[g.group] ? t(GROUP_KEYS[g.group]) : g.group)}
          items={g.items}
          slug={slug}
          pageMonth={pageMonth}
          open={!!openGroups[g.group]}
          onToggle={() => setOpenGroups((o) => ({ ...o, [g.group]: !o[g.group] }))}
        />
      ))}
      <Link to={regionPath(slug)} className="z2p-all-btn fe-tap fe-press">
        {t('z2.allPrices', { region: regionName })}
        <ArrowUpRight size={14} aria-hidden="true" />
      </Link>
    </div>
  );
}

/** R8-E: голое «92» ничего не говорит, поэтому перед числом стоит первое слово названия: «Бензин 92». Комнаты остаются «1 комн.». */
function variantLabel(name, locale) {
  const label = pairLabel(name, locale);
  if (/комн|room/i.test(label)) return label;
  const first = String(name || '').trim().split(/\s+/)[0] || '';
  if (!first || /\d/.test(first) || label.startsWith(first)) return label;
  return `${first}\u00a0${label}`;
}

/** Варианты одной цены (1 и 2 комнаты): переключатель с ценами рядом, чтобы показать клиенту обе сразу. */
export function PairSwitch({ siblings, currentName, currentValue, unit, slug }) {
  const { t, locale } = useLocale();
  const pairs = pairSiblings(siblings, currentName);
  if (!pairs.length) return null;
  const num = (name) => parseInt(/\d+/.exec(name || '')?.[0], 10) || 0;
  const items = [
    { code: null, label: variantLabel(currentName, locale), value: currentValue, unit, n: num(currentName) },
    ...pairs.map((s) => ({ code: s.code, label: variantLabel(s.short_name || s.name, locale), value: s.value ?? s.last_value, unit: s.unit, n: num(s.short_name || s.name) })),
  ].sort((a, b) => a.n - b.n);
  return (
    <nav className="r5a-pair" aria-label={t('r5a.pairAria')}>
      {items.map((it) => {
        const body = (
          <>
            <span className="r5a-pair__label">{it.label}</span>
            <span className="fe-num r5a-pair__val">{priceText(it.value, it.unit, locale)}</span>
            {it.code != null && currentValue > 0 && Math.abs(it.value / currentValue - 1) >= 0.0005 && (
              <span className="fe-num r5a-pair__diff">
                {t(it.value > currentValue ? 'r5a.pairHigher' : 'r5a.pairLower', { pct: signedPct(Math.abs((it.value / currentValue - 1) * 100), locale, 0).replace(/^[+−]/, '') })}
              </span>
            )}
          </>
        );
        return it.code == null
          ? <span key="cur" className="r5a-pair__item is-current" aria-current="page">{body}</span>
          : <Link key={it.code} to={regionIndicatorPath(slug, it.code)} className="r5a-pair__item fe-tap fe-press">{body}</Link>;
      })}
    </nav>
  );
}

/** «Скопировать для клиента»: одна строка с ценой, месяцем и сравнением — в буфер. */
export function CopyForClient({ text }) {
  const { t } = useLocale();
  const [done, setDone] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const ta = document.createElement('textarea');
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand('copy'); } catch { /* буфер недоступен */ }
      document.body.removeChild(ta);
    }
    setDone(true);
    setTimeout(() => setDone(false), 2200);
  };
  return (
    <button type="button" className="r5a-copy fe-tap fe-press" onClick={copy} data-no-export="true" aria-live="polite">
      {done ? <Check size={14} aria-hidden="true" /> : <Copy size={14} aria-hidden="true" />}
      {done ? t('r5a.copied') : t('r5a.copy')}
    </button>
  );
}

/** Окно графика: 2 года / 5 лет / 10 лет / всё. */
export function RangeChips({ value, onChange, total }) {
  const { t } = useLocale();
  const opts = [[24, 'r5a.r2'], [60, 'r5a.r5'], [120, 'r5a.r10'], [0, 'r5a.rAll']].filter(([m]) => m === 0 || total > m);
  if (opts.length < 3) return null;
  return (
    <div className="r5a-range" role="group" aria-label={t('r5a.rangeAria')} data-no-export="true">
      {opts.map(([m, key]) => (
        <button key={m} type="button" className={`r5a-range__b fe-tap-inline${value === m ? ' is-on' : ''}`} aria-pressed={value === m} onClick={() => onChange(m)}>
          {t(key)}
        </button>
      ))}
    </div>
  );
}

const AREAS = [30, 45, 60, 80];

/** «Квартира 45 м²: ≈ 1 450 ₽ в месяц»: для цен «за м²» — сумма на типовую площадь (простое умножение). */
export function AreaCalc({ value, unit }) {
  const { t, locale } = useLocale();
  const [area, setArea] = useState(45);
  if (!perAreaUnit(unit) || !(value > 0)) return null;
  return (
    <div className="r5a-area" data-no-export="true">
      <p className="r5a-area__sum fe-num">
        {t('r5a.areaSum', { area: `${area}${NBSP}${locale === 'en' ? 'm²' : 'м²'}`, sum: `${Math.round(value * area).toLocaleString(locale === 'en' ? 'en-US' : 'ru-RU').replace(/[\u00a0\u202f]/g, NBSP)}${NBSP}₽` })}
      </p>
      <div className="r5a-range" role="group" aria-label={t('r5a.areaAria')}>
        {AREAS.map((a) => (
          <button key={a} type="button" className={`r5a-range__b fe-tap-inline${area === a ? ' is-on' : ''}`} aria-pressed={area === a} onClick={() => setArea(a)}>
            {a}{NBSP}{locale === 'en' ? 'm²' : 'м²'}
          </button>
        ))}
      </div>
    </div>
  );
}
