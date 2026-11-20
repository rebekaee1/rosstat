import { useEffect, useMemo } from 'react';
import FaqAccordion from './FaqAccordion';
import { track, events } from '../lib/track';
import { useT } from '../i18n';
import { mountJsonLd } from '../lib/jsonLd';

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
 * свёрнутом состоянии (см. FaqAccordion). FAQPage JSON-LD описывает
 * видимые ответы; Google показывает FAQ rich results только ограниченному кругу сайтов.
 */
const REPEATS_METHODOLOGY = /^(что\s+(показывает|такое)|откуда|источник|методолог)/i;

export default function IndicatorSeoBlocks({ blocks, indicatorCode }) {
  const t = useT();
  // Вопросы про «что показывает» и «откуда данные» повторяют «Методологию» и «Источник» рядом: их не дублируем (круг наблюдателей, №35).
  // Остальные вопросы и разметка FAQPage остаются, блок свёрнут.
  const items = useMemo(
    () => (Array.isArray(blocks)
      ? blocks.filter((b) => b?.title && b?.body && !REPEATS_METHODOLOGY.test(b.title))
      : []),
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
    if (items.length < 2) return undefined;
    return mountJsonLd(faqJsonLd);
  }, [faqJsonLd, items.length]);

  if (items.length === 0) return null;

  return (
    <section data-block="about" className="mt-16 mb-12 w-full">
      <details className="fe-more" data-testid="about-details">
        <summary className="fe-more__summary text-xs uppercase tracking-[0.2em] text-text-secondary font-semibold">
          {t('indicator.about')}
        </summary>
        <div className="fe-more__body mt-4">
          <FaqAccordion
            items={items}
            onToggle={({ title, open }) => {
              if (open) track(events.FAQ_TOGGLE, { question: title, indicator: indicatorCode });
            }}
          />
        </div>
      </details>
    </section>
  );
}
