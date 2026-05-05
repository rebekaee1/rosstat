import { Link } from 'react-router-dom';
import { cn } from '../lib/format';

export default function VariantGroupPicker({ group, currentCode }) {
  if (!group) return null;
  return (
    <section className="mb-8 rounded-[1.5rem] border border-border-subtle bg-surface p-4 shadow-sm">
      <p className="mb-3 text-[10px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
        {group.label}
      </p>
      <div className="flex flex-wrap gap-2">
        {group.codes.map((item) => (
          <Link
            key={item.code}
            to={`/indicator/${item.code}`}
            className={cn(
              'rounded-xl px-3 py-2 text-xs font-medium transition-colors',
              item.code === currentCode
                ? 'bg-champagne/15 text-champagne'
                : 'bg-obsidian-lighter text-text-secondary hover:text-champagne'
            )}
          >
            {item.label}
          </Link>
        ))}
      </div>
    </section>
  );
}
