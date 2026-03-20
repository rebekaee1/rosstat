import { Link } from 'react-router-dom';
import { Activity, TrendingUp } from 'lucide-react';
import { CATEGORIES } from '../lib/categories';

export default function Footer() {
  return (
    <footer className="mt-auto bg-obsidian-light rounded-t-[3rem] border-t border-border-subtle">
      <div className="max-w-6xl mx-auto px-6 py-10">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-8">
          <div className="sm:col-span-2 lg:col-span-1">
            <div className="flex items-center gap-2 mb-3">
              <TrendingUp className="w-5 h-5 text-champagne" />
              <span className="text-base font-bold">Forecast Economy</span>
            </div>
            <p className="text-sm text-text-secondary leading-relaxed max-w-xs">
              Бесплатная аналитическая платформа экономических данных России. Официальные источники,
              графики и прогнозы.
            </p>
          </div>

          <div>
            <h4 className="text-xs uppercase tracking-wider text-text-tertiary mb-3 font-medium">
              Категории
            </h4>
            <ul className="space-y-2 text-sm text-text-secondary">
              {CATEGORIES.filter((c) => c.apiCategory).map((c) => (
                <li key={c.slug}>
                  <Link
                    to={`/category/${c.slug}`}
                    className="lift-hover inline-block hover:text-text-primary transition-colors"
                  >
                    {c.name}
                  </Link>
                </li>
              ))}
              {CATEGORIES.filter((c) => !c.apiCategory).map((c) => (
                <li key={c.slug} className="text-text-tertiary/80">
                  {c.name} <span className="text-[10px] uppercase">скоро</span>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h4 className="text-xs uppercase tracking-wider text-text-tertiary mb-3 font-medium">
              ИПЦ (Росстат)
            </h4>
            <ul className="space-y-2 text-sm text-text-secondary">
              <li><Link to="/indicator/cpi" className="lift-hover inline-block hover:text-text-primary transition-colors">Общий ИПЦ</Link></li>
              <li><Link to="/indicator/cpi-food" className="lift-hover inline-block hover:text-text-primary transition-colors">Продовольствие</Link></li>
              <li><Link to="/indicator/cpi-nonfood" className="lift-hover inline-block hover:text-text-primary transition-colors">Непродтовары</Link></li>
              <li><Link to="/indicator/cpi-services" className="lift-hover inline-block hover:text-text-primary transition-colors">Услуги</Link></li>
            </ul>
          </div>

          <div>
            <h4 className="text-xs uppercase tracking-wider text-text-tertiary mb-3 font-medium">
              Источники
            </h4>
            <ul className="space-y-2 text-sm text-text-secondary">
              <li>
                <a href="https://rosstat.gov.ru" target="_blank" rel="noopener noreferrer"
                   className="lift-hover inline-block hover:text-text-primary transition-colors">
                  Росстат
                </a>
              </li>
              <li>
                <a href="https://cbr.ru" target="_blank" rel="noopener noreferrer"
                   className="lift-hover inline-block hover:text-text-primary transition-colors">
                  Банк России
                </a>
              </li>
            </ul>
          </div>

          <div>
            <h4 className="text-xs uppercase tracking-wider text-text-tertiary mb-3 font-medium">
              Информация
            </h4>
            <ul className="space-y-2 text-sm text-text-secondary">
              <li>
                <Link to="/about" className="lift-hover inline-block hover:text-text-primary transition-colors">
                  О проекте
                </Link>
              </li>
              <li>
                <Link to="/privacy" className="lift-hover inline-block hover:text-text-primary transition-colors">
                  Политика конфиденциальности
                </Link>
              </li>
              <li>
                <a href="mailto:contact@forecasteconomy.com" className="lift-hover inline-block hover:text-text-primary transition-colors">
                  contact@forecasteconomy.com
                </a>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-8 pt-6 border-t border-border-subtle flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Activity className="w-3 h-3 text-positive pulse-dot" />
            <span className="text-xs font-mono text-text-tertiary">
              Система работает
            </span>
          </div>

          <p className="text-xs text-text-tertiary text-center md:text-right max-w-md">
            &copy; {new Date().getFullYear()} Forecast Economy. Материалы носят информационный характер и не являются инвестиционной рекомендацией.
          </p>
        </div>
      </div>
    </footer>
  );
}
