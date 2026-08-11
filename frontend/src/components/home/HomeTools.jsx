import { createElement } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, BarChart3, CalendarRange, Globe2, MapPin } from 'lucide-react';

const TOOLS = [
  {
    to: '/compare',
    title: 'Сравнение',
    desc: 'Россия, регионы и страны на одном графике',
    icon: BarChart3,
  },
  {
    to: '/calendar',
    title: 'Календарь',
    desc: 'Официальные даты публикаций статистики',
    icon: CalendarRange,
  },
  {
    to: '/regions',
    title: 'Регионы',
    desc: '489 показателей по 85 субъектам РФ',
    icon: MapPin,
  },
  {
    to: '/world',
    title: 'Страны',
    desc: 'Европейское покрытие и каталог стран',
    icon: Globe2,
  },
];

export default function HomeTools() {
  return (
    <section data-block="home-tools" className="mb-10 md:mb-12" aria-labelledby="home-tools-title">
      <div className="mb-4 flex items-center gap-4">
        <h2 id="home-tools-title" className="text-xs font-semibold uppercase tracking-[0.2em] text-text-secondary">
          Инструменты
        </h2>
        <div className="h-px flex-1 bg-border-subtle" />
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {TOOLS.map(({ to, title, desc, icon }) => (
          <Link
            key={to}
            to={to}
            className="group flex items-start gap-3 rounded-xl border border-border-subtle bg-surface px-4 py-3.5 transition-all hover:border-border-champagne hover:shadow-sm"
          >
            <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-champagne/10 text-champagne">
              {createElement(icon, { size: 15 })}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1 text-sm font-semibold text-text-primary group-hover:text-champagne">
                {title}
                <ArrowRight size={12} className="opacity-0 transition-opacity group-hover:opacity-100" />
              </div>
              <p className="mt-0.5 text-[12px] leading-snug text-text-secondary">{desc}</p>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}
