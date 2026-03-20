import { useState, useMemo, useEffect, useRef } from 'react';
import gsap from 'gsap';
import { ChevronDown, ChevronUp, Search } from 'lucide-react';
import { formatDate, formatValue, cn } from '../lib/format';

const PAGE_SIZE = 20;

export default function DataTable({ data, title = 'Исторические данные' }) {
  const ref = useRef(null);
  const [page, setPage] = useState(0);
  const [sortAsc, setSortAsc] = useState(false);
  const [search, setSearch] = useState('');

  useEffect(() => {
    if (!ref.current) return;
    gsap.fromTo(ref.current,
      { y: 20, opacity: 0 },
      { y: 0, opacity: 1, duration: 0.6, ease: 'power3.out', delay: 0.7 }
    );
  }, []);

  const filtered = useMemo(() => {
    let rows = [...(data || [])];
    if (search) {
      const q = search.toLowerCase();
      rows = rows.filter(r =>
        formatDate(r.date, 'full').toLowerCase().includes(q) ||
        String(r.value).includes(q)
      );
    }
    rows.sort((a, b) => sortAsc
      ? new Date(a.date) - new Date(b.date)
      : new Date(b.date) - new Date(a.date)
    );
    return rows;
  }, [data, search, sortAsc]);

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  const pageData = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  return (
    <div ref={ref} className="rounded-[2rem] bg-surface border border-border-subtle overflow-hidden">
      <div className="p-5 flex items-center justify-between flex-wrap gap-3">
        <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">
          {title}
          <span className="ml-2 text-text-tertiary font-mono text-xs">
            ({filtered.length})
          </span>
        </h3>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-tertiary" />
          <input
            type="text"
            placeholder="Поиск..."
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(0); }}
            className="pl-8 pr-3 py-1.5 text-sm bg-obsidian-lighter border border-border-subtle rounded-lg text-text-primary placeholder:text-text-tertiary focus:outline-none focus:border-champagne/30 w-40"
          />
        </div>
      </div>

      <div className="overflow-x-auto scrollbar-hide">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-t border-border-subtle">
              <th
                className="text-left px-5 py-3 text-xs font-medium text-text-tertiary uppercase tracking-wider cursor-pointer hover:text-text-secondary transition-colors select-none"
                onClick={() => setSortAsc(!sortAsc)}
              >
                <span className="inline-flex items-center gap-1">
                  Дата
                  {sortAsc ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                </span>
              </th>
              <th className="text-right px-5 py-3 text-xs font-medium text-text-tertiary uppercase tracking-wider">
                Значение (%)
              </th>
            </tr>
          </thead>
          <tbody>
            {pageData.map((row) => (
              <tr
                key={row.date}
                className={cn(
                  'border-t border-border-subtle transition-colors',
                  'hover:bg-surface-hover'
                )}
              >
                <td className="px-5 py-2.5 text-text-secondary font-mono text-xs">
                  {formatDate(row.date, 'full')}
                </td>
                <td className="px-5 py-2.5 text-right font-mono text-sm font-medium text-text-primary">
                  {formatValue(row.value)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="p-4 border-t border-border-subtle flex items-center justify-between">
          <button
            onClick={() => setPage(p => Math.max(0, p - 1))}
            disabled={page === 0}
            className="px-3 py-1.5 text-xs font-medium text-text-secondary hover:text-text-primary disabled:text-text-tertiary disabled:cursor-not-allowed rounded-lg bg-obsidian-lighter border border-border-subtle transition-colors magnetic-btn"
          >
            Назад
          </button>
          <span className="text-xs text-text-tertiary font-mono">
            {page + 1} / {totalPages}
          </span>
          <button
            onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
            className="px-3 py-1.5 text-xs font-medium text-text-secondary hover:text-text-primary disabled:text-text-tertiary disabled:cursor-not-allowed rounded-lg bg-obsidian-lighter border border-border-subtle transition-colors magnetic-btn"
          >
            Вперёд
          </button>
        </div>
      )}
    </div>
  );
}
