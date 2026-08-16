import { useEffect, useMemo } from 'react';
import FaqAccordion from './FaqAccordion';
import { track, events } from '../lib/track';
import { useT } from '../i18n';

/**
 * SEO-блоки на странице индикатора (правка D2 из звонка 2026-05-21).
 *
 * Источник — `indicator.seo_blocks` (JSON list `[{title, body}]`), который
 * приходит из БД-колонки `indicators.seo_blocks` и backfill-ится из
 * `backend/app/data/indicator_seo.py::INDICATOR_SEO_BLOCKS`. Те же блоки
 * вставляются в SSR-HTML через `seo_renderer.py` — это даёт Google длинный
 * читаемый контент на странице индикатора, помимо короткой `description`
 * и сухой `methodology`.
 *
 * UI — аккордеон как на странице калькулятора; ответы остаются в DOM при
 * свёрнутом состоянии (см. FaqAccordion). Для rich results — FAQPage JSON-LD.
 */
export default function IndicatorSeoBlocks({ blocks, indicatorCode }) {
  const t = useT();
  const items = useMemo(
    () => (Array.isArray(blocks) ? blocks.filter((b) => b?.title && b?.body) : []),
    [blocks],
  );

  const faqJsonLd = useMemo(
    () => ({
      '@context': 'https://schema.org',
      '@type': 'FAQPage',
      mainEntity: items.map((b) => ({
        '@type': 'Question',
        name: b.title,
        acceptedAnswer: { '@type': 'Answer', text: b.body },
      })),
    }),
    [items],
  );

  useEffect(() => {
    if (items.length === 0) return undefined;
    const id = `indicator-faq-ld-${indicatorCode || 'default'}`;
    let script = document.getElementById(id);
    if (!script) {
      script = document.createElement('script');
      script.id = id;
      script.type = 'application/ld+json';
      document.head.appendChild(script);
    }
    script.textContent = JSON.stringify(faqJsonLd);
    return () => {
      document.getElementById(id)?.remove();
    };
  }, [faqJsonLd, indicatorCode, items.length]);

  if (items.length === 0) return null;

  return (
    <section data-block="about" className="mt-16 mb-12 w-full">
      <div className="flex items-center gap-4 mb-8">
        <h2 className="text-xs uppercase tracking-[0.2em] text-text-secondary font-semibold">
          {t('indicator.about')}
        </h2>
        <div className="h-[1px] flex-1 bg-border-subtle" />
      </div>
      <FaqAccordion
        items={items}
        onToggle={({ title, open }) => {
          if (open) track(events.FAQ_TOGGLE, { question: title, indicator: indicatorCode });
        }}
      />
    </section>
  );
}
