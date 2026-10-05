// «Все показатели по темам» под чипами карты: свёрнутый список аккордеонов вместо стены кнопок.
// Для США — восемь понятных тем (usCatalogTopics), внутри них разделы; для остальных — разделы каталога.
import { ChevronDown } from 'lucide-react';
import { useLocale } from '../../i18n';
import { buildTopicGroups } from '../../lib/mapMetricPicks';
import '../../styles/regions-w4.css';

export default function MapMetricTopics({ indicators, sections, usTopics = false, activeCode, onPick }) {
  const { t, locale } = useLocale();
  const groups = buildTopicGroups({ indicators, sections, usTopics, locale, fallbackName: t('y1.map.topicOther') });
  if (!groups.length) return null;
  return (
    <details className="fe-acc mb-3 rounded-2xl border border-border-subtle bg-surface" data-block="map-metric-topics">
      <summary className="flex min-h-11 items-center justify-between gap-2 px-4 text-sm font-medium text-text-primary">
        <span>{t('y1.map.allByTopic')}</span>
        <ChevronDown size={16} className="fe-acc__chev shrink-0 text-text-secondary" aria-hidden="true" />
      </summary>
      <div className="space-y-1 border-t border-border-subtle p-2">
        {groups.map((group) => {
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
              <div className="max-h-80 overflow-y-auto px-1 pb-2">
                {group.blocks.map((block) => (
                  <div key={block.title || 'all'} className="mt-1">
                    {block.title ? (
                      <div className="px-3 pb-0.5 pt-2 text-xs font-medium text-text-secondary">{block.title}</div>
                    ) : null}
                    <ul>
                      {block.items.map((i) => {
                        const active = i.code === activeCode;
                        return (
                          <li key={i.code}>
                            <button
                              type="button"
                              onClick={() => onPick(i)}
                              aria-current={active ? 'true' : undefined}
                              className={`fe-tap w-full rounded-lg px-3 py-2.5 text-left text-sm leading-snug transition-colors ${
                                active ? 'bg-champagne/15 font-medium text-champagne-ink' : 'text-text-primary hover:bg-surface-hover'
                              }`}
                            >
                              {i.name}
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                ))}
              </div>
            </details>
          );
        })}
      </div>
    </details>
  );
}
