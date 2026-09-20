import { Link } from 'react-router-dom';
import { Activity, TrendingUp } from 'lucide-react';
import { CATEGORIES } from '../lib/categories';
import { cn } from '../lib/format';
import { FOCUS_RING } from '../lib/uiTokens';
import { track, trackOutbound, events } from '../lib/track';
import { openConsentSettings } from '../lib/consent';
import {
  comparePath,
  russiaCategoriesPath,
  russiaCategoryPath,
} from '../lib/sitePaths';
import { WORLD_RATING_TO } from '../lib/navItems';
import { footerCatalogColumn, footerHomeCountryColumn, footerSourceLinks } from '../lib/footerNav';
import { useT, useLocale } from '../i18n';

const footLink = cn(
  FOCUS_RING,
  'rounded-sm lift-hover inline-block hover:text-text-primary transition-colors'
);

export default function Footer() {
  const t = useT();
  const { locale } = useLocale();
  const categoryLabel = (c) => (locale === 'en' && c.nameEn ? c.nameEn : c.name);
  const sourceLinks = footerSourceLinks(locale);
  const homeCountry = footerHomeCountryColumn(locale);
  const catalog = footerCatalogColumn(locale);

  return (
    <footer className="mt-auto bg-obsidian-light rounded-t-[3rem] border-t border-border-subtle">
      <div className="max-w-6xl mx-auto px-6 py-10">
        <div className="grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          <div>
            <div className="flex items-center gap-2 mb-3">
              <TrendingUp className="w-5 h-5 text-champagne" />
              <span className="text-base font-bold">Forecast Economy</span>
            </div>
            <p className="text-sm text-text-secondary leading-relaxed">
              {t('footer.tagline')}
            </p>
            <h4 className="mt-5 text-xs uppercase tracking-wider text-text-tertiary mb-2 font-medium">
              {t('footer.sources')}
            </h4>
            <ul className="space-y-2 text-sm text-text-secondary">
              {sourceLinks.map((item) => (
                <li key={item.href}>
                  <a
                    href={item.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={footLink}
                    onClick={() => trackOutbound(item.href)}
                  >
                    {t(item.key)}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          {catalog.kind === 'countries' ? (
            <div>
              <h4 className="text-xs uppercase tracking-wider text-text-tertiary mb-3 font-medium">
                <Link to={catalog.headingTo} className={footLink}>
                  {t(catalog.headingKey)}
                </Link>
              </h4>
              <ul className="space-y-2 text-sm text-text-secondary">
                {catalog.links.map((item) => (
                  <li key={item.key}>
                    <Link to={item.to} className={footLink}>
                      {item.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <div>
              <h4 className="text-xs uppercase tracking-wider text-text-tertiary mb-3 font-medium">
                <Link to={russiaCategoriesPath()} className={footLink}>
                  {t('footer.categories')}
                </Link>
              </h4>
              <ul className="space-y-2 text-sm text-text-secondary">
                {CATEGORIES.filter((c) => c.apiCategory).map((c) => (
                  <li key={c.slug}>
                    <Link to={russiaCategoryPath(c.slug)} className={footLink}>
                      {categoryLabel(c)}
                    </Link>
                  </li>
                ))}
                {CATEGORIES.filter((c) => !c.apiCategory).map((c) => (
                  <li key={c.slug} className="text-text-tertiary/80">
                    {categoryLabel(c)} <span className="text-[10px] uppercase">{t('common.soon')}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div>
            <h4 className="text-xs uppercase tracking-wider text-text-tertiary mb-3 font-medium">
              {t('footer.section.world')}
            </h4>
            <ul className="space-y-2 text-sm text-text-secondary">
              <li>
                <Link to="/#countries" className={footLink}>
                  {t('footer.countries')}
                </Link>
              </li>
              <li>
                <Link to={WORLD_RATING_TO} className={footLink}>
                  {t('footer.worldRating')}
                </Link>
              </li>
              <li>
                <Link to={comparePath()} className={footLink}>
                  {t('footer.compare')}
                </Link>
              </li>
            </ul>
          </div>

          <div>
            <h4 className="text-xs uppercase tracking-wider text-text-tertiary mb-3 font-medium">
              {t(homeCountry.sectionKey)}
            </h4>
            <ul className="space-y-2 text-sm text-text-secondary">
              {homeCountry.links.map((item) => (
                <li key={item.key}>
                  <Link to={item.to} className={footLink}>
                    {t(item.key)}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h4 className="text-xs uppercase tracking-wider text-text-tertiary mb-3 font-medium">
              {t('footer.tools')}
            </h4>
            <ul className="space-y-2 text-sm text-text-secondary">
              <li>
                <Link to={comparePath()} className={footLink}>
                  {t('footer.compare')}
                </Link>
              </li>
              <li>
                <Link to="/calculator" className={footLink}>
                  {t('footer.calcInflation')}
                </Link>
              </li>
              <li>
                <Link to="/calculator/mortgage" className={footLink}>
                  {t('footer.calcMortgage')}
                </Link>
              </li>
              <li>
                <Link to="/calculator/compound" className={footLink}>
                  {t('footer.calcCompound')}
                </Link>
              </li>
            </ul>
          </div>

          <div>
            <h4 className="text-xs uppercase tracking-wider text-text-tertiary mb-3 font-medium">
              {t('footer.info')}
            </h4>
            <ul className="space-y-2 text-sm text-text-secondary">
              <li>
                <Link to="/about" className={footLink}>
                  {t('footer.about')}
                </Link>
              </li>
              <li>
                <Link to="/methodology" className={footLink}>
                  {t('footer.methodology')}
                </Link>
              </li>
              <li>
                <Link to="/privacy" className={footLink}>
                  {t('footer.privacy')}
                </Link>
              </li>
              <li>
                <Link to="/terms" className={footLink}>
                  {t('footer.terms')}
                </Link>
              </li>
              <li>
                <button type="button" onClick={openConsentSettings} className={cn(footLink, 'text-left')}>
                  {t('footer.cookies')}
                </button>
              </li>
              <li>
                <a href="mailto:rebeka.ee@yandex.ru" className={footLink} onClick={() => track(events.CONTACT_EMAIL)}>
                  rebeka.ee@yandex.ru
                </a>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-8 pt-6 border-t border-border-subtle flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Activity className="w-3 h-3 text-positive pulse-dot" />
            <span className="text-xs font-mono text-text-tertiary">
              {t('footer.systemOk')}
            </span>
          </div>

          <div className="text-xs text-text-tertiary text-center md:text-right max-w-lg space-y-1">
            <p>
              &copy; {new Date().getFullYear()} Forecast Economy. {t('footer.disclaimer')}
            </p>
            <p>
              {t('footer.operator')}
            </p>
          </div>
        </div>
      </div>
    </footer>
  );
}
