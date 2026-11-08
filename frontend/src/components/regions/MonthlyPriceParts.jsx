// Страница цены региона (месячный ряд): пометка о снятом ряде, сравнение цифрой, «Ещё в разделе» по группам.
// Поля short_name / price_group / is_discontinued / last_month / compare приходят от API; если их нет — блоки не рисуются.
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight, ChevronDown } from 'lucide-react';
import { useLocale } from '../../i18n';
import { formatRegionWithUnit, glueNumbers } from '../../lib/regionUi';
import { regionIndicatorPath, regionPath } from '../../lib/sitePaths';
import { groupSiblings, signedPct, ymLabel } from '../../lib/z2Price';
import '../../styles/z2-price.css';

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
export function DiscontinuedNote({ lastLabel }) {
  const { t } = useLocale();
  return (
    <p className="z2p-note" role="note">
      {t('z2.discontinued', { month: lastLabel })}
    </p>
  );
}

/** «Россия: 98,1 ₽ (здесь +6,3 %)» — цифрой под главной ценой. */
export function CompareLines({ rows, unit, lastMonth }) {
  const { t, locale } = useLocale();
  if (!rows.length) return null;
  return (
    <ul className="z2p-compare" aria-label={t('z2.compareAria')}>
      {rows.map((r) => {
        const sameMonth = !r.month || !lastMonth || String(r.month).replace(/\D/g, '') === String(lastMonth).replace(/\D/g, '');
        return (
          <li key={r.key}>
            <span className="z2p-compare__name">{t(r.key === 'russia' ? 'z2.russia' : 'z2.moskva')}</span>
            <span className="fe-num z2p-compare__val">{formatRegionWithUnit(r.value, unit, locale)}</span>
            <span className="fe-num z2p-compare__pct">{t('z2.here', { pct: signedPct(r.pct, locale) })}</span>
            {!sameMonth && <span className="z2p-compare__month">{ymLabel(r.month, locale)}</span>}
          </li>
        );
      })}
    </ul>
  );
}

function SiblingRow({ s, slug }) {
  const { t, locale } = useLocale();
  const value = s.value ?? s.last_value ?? null;
  const month = ymLabel(s.last_month ?? s.month, locale);
  const dead = !!s.is_discontinued;
  return (
    <li className="min-w-0">
      <Link
        to={regionIndicatorPath(slug, s.code)}
        className={`z2p-row fe-tap fe-press fe-glass-lite fe-float${dead ? ' is-dead' : ''}`}
      >
        <span className="z2p-row__name">{glueNumbers(s.short_name || s.name)}</span>
        <span className="z2p-row__meta">
          {value != null && <span className="fe-num z2p-row__val">{formatRegionWithUnit(value, s.unit, locale)}</span>}
          {month && (
            <span className="z2p-row__month">{dead ? t('z2.until', { month }) : month}</span>
          )}
        </span>
        <ArrowUpRight size={14} className="z2p-row__arrow" aria-hidden="true" />
      </Link>
    </li>
  );
}

function Group({ label, items, slug, open, onToggle }) {
  const { t } = useLocale();
  const shown = open ? items : items.slice(0, PER_GROUP);
  return (
    <section className="z2p-group">
      <h3 className="z2p-group__title">{label}<span className="z2p-group__count fe-num">{items.length}</span></h3>
      <ul className="grid gap-2 sm:grid-cols-2">
        {shown.map((s) => <SiblingRow key={s.code} s={s} slug={slug} />)}
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
export default function GroupedSiblings({ siblings, currentGroup, slug, section, regionName }) {
  const { t } = useLocale();
  const [openGroups, setOpenGroups] = useState({});
  const groups = groupSiblings(siblings, currentGroup);
  if (!groups) return null;
  return (
    <div className="z2p-siblings">
      <div className="z2p-siblings__head">
        <h2 className="text-sm font-semibold text-text-primary">{t('regions.ind.moreInSection', { section })}</h2>
        <Link to={regionPath(slug)} className="z2p-all fe-tap-inline">
          {t('z2.allPrices', { region: regionName })}
          <ArrowUpRight size={13} aria-hidden="true" />
        </Link>
      </div>
      {groups.map((g) => (
        <Group
          key={g.group}
          label={GROUP_KEYS[g.group] ? t(GROUP_KEYS[g.group]) : g.group}
          items={g.items}
          slug={slug}
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
