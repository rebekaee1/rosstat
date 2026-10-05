// «Все показатели по темам» под чипами карты: одна кнопка, а список открывается в шторке (внизу на телефоне,
// сбоку на компьютере) с поиском по теме. Раньше список разворачивался прямо в странице и растягивал её на
// несколько экранов. Для США — восемь понятных тем (usCatalogTopics), внутри них разделы; для остальных —
// разделы каталога. Коды отраслей не показываются в названиях: они лежат в подсказке «i».
import { useEffect, useMemo, useRef, useState } from 'react';
import { ChevronDown, Info, ListTree, Search, X } from 'lucide-react';
import { useLocale } from '../../i18n';
import { buildTopicGroups } from '../../lib/mapMetricPicks';
import { plainUsIndicatorName, plainUsSectionTitle } from '../../lib/usCatalogTopics';
import { filterSearchOptions } from '../../lib/searchSynonyms';
import '../../styles/regions-w4.css';
import '../../styles/w6f-pages.css';

function IndicatorRow({ item, active, onPick, locale }) {
  const { t } = useLocale();
  const plain = plainUsIndicatorName(item.name, locale);
  const [showHint, setShowHint] = useState(false);
  return (
    <li>
      <div className="fe-topic-row">
        <button
          type="button"
          onClick={() => onPick(item)}
          aria-current={active ? 'true' : undefined}
          className={`fe-tap fe-topic-row__main ${active ? 'is-active' : ''}`}
        >
          {plain.label}
        </button>
        {plain.hint && (
          <button
            type="button"
            className="fe-topic-row__info"
            aria-expanded={showHint}
            aria-label={t('w6f.us.codeInfo')}
            title={plain.hint}
            onClick={() => setShowHint((v) => !v)}
          >
            <Info size={15} aria-hidden="true" />
          </button>
        )}
      </div>
      {showHint && plain.hint && <p className="fe-topic-row__hint">{plain.hint}</p>}
    </li>
  );
}

export default function MapMetricTopics({ indicators, sections, usTopics = false, activeCode, onPick }) {
  const { t, locale } = useLocale();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const searchRef = useRef(null);
  const triggerRef = useRef(null);
  const groups = useMemo(
    () => buildTopicGroups({ indicators, sections, usTopics, locale, fallbackName: t('y1.map.topicOther') }),
    [indicators, sections, usTopics, locale, t],
  );

  // Поиск по теме: ищет и в названиях показателей, и в названиях тем; пустой запрос показывает всё по темам.
  const found = useMemo(() => {
    const q = query.trim();
    if (!q) return null;
    const all = groups.flatMap((g) => g.blocks.flatMap((b) => b.items.map((i) => ({
      ...i, section: [g.name, b.title].filter(Boolean).join(' / '),
    }))));
    return filterSearchOptions(all, q).slice(0, 60);
  }, [groups, query]);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('keydown', onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    searchRef.current?.focus();
    const trigger = triggerRef.current;
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prevOverflow;
      trigger?.focus();
    };
  }, [open]);

  if (!groups.length) return null;
  const total = groups.reduce((n, g) => n + g.count, 0);
  const pick = (item) => { onPick(item); setOpen(false); setQuery(''); };

  return (
    <div className="mb-3" data-block="map-metric-topics">
      <button
        ref={triggerRef}
        type="button"
        className="fe-topic-trigger fe-press"
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => setOpen(true)}
      >
        <ListTree size={16} aria-hidden="true" className="text-champagne-ink" />
        <span className="min-w-0 flex-1 text-left">{t('y1.map.allByTopic')}</span>
        <span className="fe-num text-xs text-text-secondary">{total}</span>
      </button>

      {open && (
        <div className="fe-sheet" role="presentation">
          <button type="button" className="fe-sheet__backdrop" aria-label={t('common.close')} onClick={() => setOpen(false)} tabIndex={-1} />
          <div className="fe-sheet__panel" role="dialog" aria-modal="true" aria-label={t('y1.map.allByTopic')}>
            <div className="fe-sheet__head">
              <h2 className="text-base font-semibold text-text-primary">{t('y1.map.allByTopic')}</h2>
              <button type="button" className="fe-sheet__close fe-press" onClick={() => setOpen(false)} aria-label={t('common.close')}>
                <X size={18} aria-hidden="true" />
              </button>
            </div>
            <div className="fe-sheet__search">
              <Search size={15} aria-hidden="true" className="shrink-0 text-text-secondary" />
              <input
                ref={searchRef}
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t('w6f.us.topicSearch')}
                aria-label={t('w6f.us.topicSearch')}
                className="min-w-0 flex-1 bg-transparent text-[16px] outline-none placeholder:text-text-tertiary"
              />
            </div>
            <div className="fe-sheet__body">
              {found ? (
                found.length === 0 ? (
                  <p className="px-3 py-4 text-sm text-text-secondary">{t('regions.home.nothingFound', { query })}</p>
                ) : (
                  <ul>
                    {found.map((i) => (
                      <li key={i.code}>
                        <button
                          type="button"
                          onClick={() => pick(i)}
                          className="fe-tap w-full rounded-lg px-3 py-2.5 text-left transition-colors hover:bg-surface-hover"
                        >
                          <span className="block text-sm leading-snug text-text-primary">{plainUsIndicatorName(i.name, locale).label}</span>
                          <span className="block text-xs text-text-secondary">{i.section}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )
              ) : (
                groups.map((group) => {
                  const hasActive = group.blocks.some((b) => b.items.some((i) => i.code === activeCode));
                  return (
                    <details key={group.id} className="fe-acc rounded-xl" open={hasActive || undefined}>
                      <summary className="flex min-h-11 items-center justify-between gap-2 rounded-xl px-3 text-sm text-text-primary hover:bg-surface-hover">
                        <span className="min-w-0 break-words font-medium">{group.name}</span>
                        <span className="flex shrink-0 items-center gap-2 text-text-secondary">
                          <span className="fe-num text-xs">{group.count}</span>
                          <ChevronDown size={14} className="fe-acc__chev" aria-hidden="true" />
                        </span>
                      </summary>
                      <div className="px-1 pb-2">
                        {group.blocks.map((block) => (
                          <div key={block.title || 'all'} className="mt-1">
                            {block.title ? (
                              <div className="px-3 pb-0.5 pt-2 text-xs font-medium text-text-secondary">
                                {plainUsSectionTitle(block.title, locale)}
                              </div>
                            ) : null}
                            <ul>
                              {block.items.map((i) => (
                                <IndicatorRow key={i.code} item={i} active={i.code === activeCode} onPick={pick} locale={locale} />
                              ))}
                            </ul>
                          </div>
                        ))}
                      </div>
                    </details>
                  );
                })
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
