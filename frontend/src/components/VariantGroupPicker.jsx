import { Link, useSearchParams } from 'react-router-dom';
import { cn } from '../lib/format';

/**
 * Внутрисемейный переключатель карточек («Все товары»/«Продовольственные»/...).
 *
 * `?mode=` берём из текущего URL (источник правды), чтобы при переходе на sibling
 * сохранялся выбранный «Режим инфляции» (месячная, недельная, …).
 *
 * `basePath` — префикс URL без кода: `/indicator` (дефолт) или `/world/{slug}`.
 */
export default function VariantGroupPicker({
  group,
  currentCode,
  embedded = false,
  basePath = '/indicator',
}) {
  const [searchParams] = useSearchParams();
  if (!group) return null;
  const modeParam = searchParams.get('mode');
  const suffix = modeParam ? `?mode=${encodeURIComponent(modeParam)}` : '';
  const root = (basePath || '/indicator').replace(/\/$/, '');

  const body = (
    <>
      <p className="mb-3 text-[10px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
        {group.label}
      </p>
      <div className="flex flex-wrap gap-2">
        {group.codes.map((item) => (
          <Link
            key={item.code}
            to={`${root}/${item.code}${suffix}`}
            preventScrollReset
            className={cn(
              'rounded-xl px-3 py-2 text-xs font-medium transition-colors',
              item.code === currentCode
                ? 'bg-champagne/15 text-champagne'
                : 'bg-obsidian-lighter text-text-secondary hover:text-champagne',
            )}
          >
            {item.label}
          </Link>
        ))}
      </div>
    </>
  );

  if (embedded) return body;

  return (
    <section className="mb-8 rounded-[1.5rem] border border-border-subtle bg-surface p-4 shadow-sm">
      {body}
    </section>
  );
}
