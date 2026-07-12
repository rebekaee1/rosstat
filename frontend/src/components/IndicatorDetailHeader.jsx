import { Link } from 'react-router-dom';
import { ArrowLeft, Activity } from 'lucide-react';
import { CATEGORIES } from '../lib/categories';
import { indicatorDetailHeaderMobileLines } from '../lib/indicatorVariants';
import { SkeletonBox } from './Skeleton';

const FREQ_MAP = {
  monthly: 'Помесячно',
  quarterly: 'Ежеквартально',
  annual: 'Ежегодно',
  weekly: 'Еженедельно',
  irregular: 'Нерегулярно',
  daily: 'По дням',
};

function MobileTitle({ title }) {
  const lines = indicatorDetailHeaderMobileLines(title);
  if (!lines) {
    return <span className="md:hidden text-pretty">{title}</span>;
  }
  return (
    <span className="md:hidden flex flex-col gap-0.5">
      {lines.map((line) => (
        <span key={line} className="block">
          {line}
        </span>
      ))}
    </span>
  );
}

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
  const title = indicator?.name || code;

  return (
    <div ref={headerRef} className="mb-5 md:mb-16 max-w-4xl">
      <nav data-animate className="flex items-center gap-2 text-[11px] md:text-xs font-mono uppercase tracking-widest text-text-tertiary mb-3 md:mb-8">
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
            <Link to={`/category/${category.slug}`} className="hover:text-champagne transition-colors line-clamp-1">
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
          <div data-animate className="flex flex-wrap items-center gap-2 sm:gap-3 mb-2.5 md:mb-4">
            <span className="px-2.5 sm:px-3 py-1 rounded-full border border-border-subtle bg-obsidian-light text-[10px] font-mono uppercase tracking-widest text-text-secondary flex items-center gap-2">
              <Activity className="w-3 h-3 text-champagne" />
              {FREQ_MAP[effectiveFrequency] || effectiveFrequency}
            </span>
            {category ? (
              <Link
                to={`/category/${category.slug}`}
                className="hidden sm:inline text-xs font-mono text-text-tertiary hover:text-champagne transition-colors"
              >
                {indicator.category}
              </Link>
            ) : indicator?.category ? (
              <span className="hidden sm:inline text-xs font-mono text-text-tertiary">
                {indicator.category}
              </span>
            ) : null}
          </div>

          <h1
            data-animate
            className="text-[1.3rem] leading-[1.28] text-pretty sm:text-3xl md:text-5xl lg:text-6xl font-display font-bold tracking-tight mb-1.5 md:mb-4 md:leading-tight"
          >
            <MobileTitle title={title} />
            <span className="hidden md:inline">{title}</span>
          </h1>

          {indicator?.name_en && (
            <p
              data-animate
              className="text-[11px] sm:text-sm font-mono uppercase tracking-[0.12em] text-text-tertiary md:text-base md:normal-case md:tracking-normal"
            >
              {indicator.name_en}
            </p>
          )}
        </>
      )}
    </div>
  );
}
