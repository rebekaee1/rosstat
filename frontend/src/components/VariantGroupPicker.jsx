import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { cn } from '../lib/format';
import MobileNavSelect from './MobileNavSelect';

/**
 * Внутрисемейный переключатель карточек («Все товары»/«Продовольственные»/...).
 *
 * `?mode=` берём из текущего URL (источник правды), чтобы при переходе на sibling
 * сохранялся выбранный «Режим инфляции» (месячная, недельная, …).
 *
 * `basePath` — префикс URL без кода: `/indicator` (дефолт) или `/world/{slug}`.
 * На &lt;lg при 3+ срезах — нативный select (как темы у страны/региона).
 */
export default function VariantGroupPicker({
  group,
  currentCode,
  embedded = false,
  basePath = '/indicator',
}) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  if (!group) return null;
  const modeParam = searchParams.get('mode');
  const suffix = modeParam ? `?mode=${encodeURIComponent(modeParam)}` : '';
  const root = (basePath || '/indicator').replace(/\/$/, '');
  const useMobileSelect = group.codes.length >= 3;

  const body = (
    <>
      {useMobileSelect ? (
        <MobileNavSelect
          label={group.label}
          value={currentCode}
          options={group.codes.map((item) => ({
            value: item.code,
            label: item.label,
          }))}
          onChange={(code) => {
            navigate(`${root}/${code}${suffix}`, { preventScrollReset: true });
          }}
          className="mb-0"
        />
      ) : (
        <p className="mb-3 text-[10px] font-mono uppercase tracking-[0.2em] text-text-tertiary lg:hidden">
          {group.label}
        </p>
      )}

      <div className={useMobileSelect ? 'hidden lg:block' : undefined}>
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
      </div>
    </>
  );

  if (embedded) return body;

  return (
    <section className="mb-6 min-w-0 rounded-[1.25rem] border border-border-subtle bg-surface p-3.5 shadow-sm sm:mb-8 sm:rounded-[1.5rem] sm:p-4">
      {body}
    </section>
  );
}
