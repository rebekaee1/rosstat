import { Link } from 'react-router-dom';
import { ArrowLeft, Activity } from 'lucide-react';
import { CATEGORIES } from '../lib/categories';
import { SkeletonBox } from './Skeleton';

const FREQ_MAP = {
  monthly: 'Помесячно',
  quarterly: 'Ежеквартально',
  annual: 'Ежегодно',
  weekly: 'Еженедельно',
  irregular: 'Нерегулярно',
  daily: 'По дням',
};

/**
 * Хедер страницы карточки индикатора:
 *   хлебные крошки (Главная → Категория) + бейдж периодичности +
 *   название + английское название.
 *
 * `headerRef` пробрасывается из родителя для GSAP-анимации появления
 * (родитель ищет внутри элементы с `data-animate`).
 *
 * `displayFrequency` — override родительской `indicator.frequency`
 * для пиллки. Используется в view-mode family режимах, когда активный
 * sibling имеет другую частоту (например, wages-nominal?mode=annual →
 * wages-nominal-annual с frequency=annual). `indicator.name` остаётся
 * родительским, чтобы H1/breadcrumbs не дёргались. Если override не
 * задан — fallback на `indicator.frequency`.
 */
export default function IndicatorDetailHeader({
  indicator,
  code,
  loading,
  headerRef,
  displayFrequency,
}) {
  const effectiveFrequency = displayFrequency ?? indicator?.frequency;
  const category = indicator?.category
    ? CATEGORIES.find((c) => c.apiCategory === indicator.category)
    : null;

  return (
    <div ref={headerRef} className="mb-12 md:mb-16 max-w-4xl">
      <nav data-animate className="flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-text-tertiary mb-8">
        <Link
          to="/"
          className="hover:text-champagne transition-colors lift-hover inline-flex items-center gap-1.5 group"
        >
          <ArrowLeft className="w-3.5 h-3.5 group-hover:-translate-x-0.5 transition-transform" />
          Главная
        </Link>
        {category && (
          <>
            <span className="text-text-tertiary/40">/</span>
            <Link to={`/category/${category.slug}`} className="hover:text-champagne transition-colors">
              {category.name}
            </Link>
          </>
        )}
      </nav>

      {loading ? (
        <div className="space-y-4">
          <SkeletonBox className="h-4 w-24" />
          <SkeletonBox className="h-14 w-3/4" />
          <SkeletonBox className="h-6 w-1/2" />
        </div>
      ) : (
        <>
          <div data-animate className="flex items-center gap-3 mb-4">
            <span className="px-3 py-1 rounded-full border border-border-subtle bg-obsidian-light text-[10px] font-mono uppercase tracking-widest text-text-secondary flex items-center gap-2">
              <Activity className="w-3 h-3 text-champagne" />
              {FREQ_MAP[effectiveFrequency] || effectiveFrequency}
            </span>
            {indicator?.category && (
              <span className="text-xs font-mono text-text-tertiary">
                {indicator.category}
              </span>
            )}
          </div>

          <h1 data-animate className="text-4xl md:text-5xl lg:text-6xl font-display font-bold tracking-tight mb-4 leading-tight">
            {indicator?.name || code}
          </h1>

          {indicator?.name_en && (
            <p data-animate className="text-sm md:text-base font-mono text-text-tertiary">
              {indicator.name_en}
            </p>
          )}
        </>
      )}
    </div>
  );
}
