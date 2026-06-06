import { useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { cn } from '../lib/format';
import { FOCUS_RING } from '../lib/uiTokens';

/**
 * Раскрывающиеся блоки вопрос–ответ (калькулятор, «О показателе» на индикаторе).
 * Текст ответа всегда в DOM (скрыт CSS), чтобы контент был доступен без клика
 * и для краулеров после гидрации; полный дубль — в SSR через seo_renderer.
 */
export default function FaqAccordion({ items, onToggle }) {
  const [open, setOpen] = useState(null);

  if (!Array.isArray(items) || items.length === 0) return null;

  return (
    <div className="divide-y divide-border-subtle border-t border-b border-border-subtle">
      {items.map((item, i) => {
        const title = item.title ?? item.q;
        const body = item.body ?? item.a;
        if (!title || !body) return null;
        const isOpen = open === i;

        return (
          <div key={i}>
            <button
              type="button"
              onClick={() => {
                const next = isOpen ? null : i;
                setOpen(next);
                onToggle?.({ index: i, title, open: next === i });
              }}
              className={cn(FOCUS_RING, 'w-full flex items-center justify-between gap-4 py-5 text-left rounded-sm')}
              aria-expanded={isOpen}
            >
              <span className="text-sm font-medium text-text-primary">{title}</span>
              <ChevronDown
                className={cn(
                  'w-4 h-4 text-text-tertiary shrink-0 transition-transform duration-200',
                  isOpen && 'rotate-180',
                )}
              />
            </button>
            <div
              className={cn(
                'grid transition-[grid-template-rows] duration-200 ease-out',
                isOpen ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]',
              )}
              aria-hidden={!isOpen}
            >
              <div className="overflow-hidden min-h-0">
                <p className="pb-5 text-sm text-text-secondary leading-relaxed -mt-1 whitespace-pre-line">
                  {body}
                </p>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
