import { Link } from 'react-router-dom';
import { Activity, BarChart3 } from 'lucide-react';

export default function Footer() {
  return (
    <footer className="mt-auto bg-obsidian-light rounded-t-[3rem] border-t border-border-subtle">
      <div className="max-w-6xl mx-auto px-6 py-10">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div>
            <div className="flex items-center gap-2 mb-3">
              <BarChart3 className="w-5 h-5 text-champagne" />
              <span className="text-base font-bold">RuStats</span>
            </div>
            <p className="text-sm text-text-secondary leading-relaxed max-w-xs">
              Аналитическая платформа экономических индикаторов России.
              Данные Росстата, OLS прогнозирование.
            </p>
          </div>

          <div>
            <h4 className="text-xs uppercase tracking-wider text-text-tertiary mb-3 font-medium">
              Индикаторы
            </h4>
            <ul className="space-y-2 text-sm text-text-secondary">
              <li><Link to="/indicator/cpi" className="lift-hover inline-block hover:text-text-primary transition-colors">Индекс потребительских цен</Link></li>
              <li><Link to="/indicator/cpi-food" className="lift-hover inline-block hover:text-text-primary transition-colors">ИПЦ — продовольствие</Link></li>
              <li><Link to="/indicator/cpi-nonfood" className="lift-hover inline-block hover:text-text-primary transition-colors">ИПЦ — непродовольственные товары</Link></li>
              <li><Link to="/indicator/cpi-services" className="lift-hover inline-block hover:text-text-primary transition-colors">ИПЦ — услуги</Link></li>
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
                  Центральный банк РФ
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

          <p className="text-xs text-text-tertiary">
            &copy; {new Date().getFullYear()} RuStats. Данные предоставлены Росстатом.
          </p>
        </div>
      </div>
    </footer>
  );
}
