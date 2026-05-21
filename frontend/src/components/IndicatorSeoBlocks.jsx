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
 * Если у индикатора нет seo_blocks — компонент возвращает `null` и пустых
 * секций на странице не создаёт.
 */
export default function IndicatorSeoBlocks({ blocks }) {
  if (!Array.isArray(blocks) || blocks.length === 0) return null;

  return (
    <section className="mt-16 mb-12 max-w-3xl">
      <div className="flex items-center gap-4 mb-8">
        <h2 className="text-xs uppercase tracking-[0.2em] text-text-secondary font-semibold">
          О показателе
        </h2>
        <div className="h-[1px] flex-1 bg-border-subtle" />
      </div>
      <div className="space-y-8">
        {blocks.map((b, i) => {
          if (!b?.body) return null;
          return (
            <article key={i} className="space-y-2">
              {b.title && (
                <h3 className="text-lg md:text-xl font-display font-semibold text-text-primary">
                  {b.title}
                </h3>
              )}
              <p className="text-sm md:text-base text-text-secondary leading-relaxed whitespace-pre-line">
                {b.body}
              </p>
            </article>
          );
        })}
      </div>
    </section>
  );
}
