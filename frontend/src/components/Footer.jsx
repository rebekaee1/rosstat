import { useId, useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronDown } from 'lucide-react';
import Brand from './Brand';
import { CATEGORIES } from '../lib/categories';
import { cn } from '../lib/format';
import { FOCUS_RING } from '../lib/uiTokens';
import { track, events } from '../lib/track';
import { openConsentSettings } from '../lib/consent';
import useMediaQuery from '../lib/useMediaQuery';
import {
  comparePath,
  russiaCategoriesPath,
  russiaCategoryPath,
} from '../lib/sitePaths';
import SourceLink from './SourceLink';
import {
  footerCatalogColumn,
  footerHomeCountryColumn,
  footerSourceLinks,
  footerWorldLinks,
} from '../lib/footerNav';
import { useT, useLocale } from '../i18n';
import '../styles/shell.css';

const footLink = cn(
  FOCUS_RING,
  'rounded-sm lift-hover inline-block hover:text-text-primary transition-colors',
  // Сенсорный экран: строка ссылки не меньше 44 px, вид на компьютере не меняется.
  'pointer-coarse:inline-flex pointer-coarse:min-h-11 pointer-coarse:items-center'
);

/**
 * Группа ссылок подвала. На телефоне — аккордеон (заголовок-кнопка раскрывает список), чтобы подвал не занимал
 * три экрана; от 640 px — обычная колонка с заголовком. Все заголовки одного стиля, регистр обычный.
 */
function FooterGroup({ title, hubTo, hubLabel, desktop, children }) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const expanded = desktop || open;
  return (
    <section className="fe-foot-group">
      <h3 className="fe-foot-title">
        {desktop ? (
          hubTo ? <Link to={hubTo} className={footLink}>{title}</Link> : title
        ) : (
          <button
            type="button"
            className={cn(FOCUS_RING, 'fe-foot-toggle fe-press')}
            aria-expanded={open}
            aria-controls={panelId}
            onClick={() => setOpen((v) => !v)}
          >
            {title}
            <ChevronDown size={18} aria-hidden="true" className="fe-foot-toggle__chevron" />
          </button>
        )}
      </h3>
      <div id={panelId} className="fe-foot-panel" data-open={expanded} inert={!expanded}>
        <div className="fe-foot-panel__inner">
          <ul className="space-y-2 text-sm text-text-secondary pointer-coarse:space-y-0">
            {!desktop && hubTo && hubLabel ? (
              <li>
                <Link to={hubTo} className={footLink}>{hubLabel}</Link>
              </li>
            ) : null}
            {children}
          </ul>
        </div>
      </div>
    </section>
  );
}

export default function Footer() {
  const t = useT();
  const { locale } = useLocale();
  const desktop = useMediaQuery('(min-width: 640px)');
  const categoryLabel = (c) => (locale === 'en' && c.nameEn ? c.nameEn : c.name);
  const sourceLinks = footerSourceLinks(locale);
  const homeCountry = footerHomeCountryColumn(locale);
  const catalog = footerCatalogColumn(locale);
  const worldLinks = footerWorldLinks(locale);

  return (
    <footer className="fe-footer mt-auto border-t border-border-subtle">
      <div className="fe-page-shell fe-foot-wrap py-10 md:py-16">
        <div className="fe-footer-grid grid grid-cols-1 gap-x-8 gap-y-0 sm:grid-cols-2 sm:gap-y-8 lg:grid-cols-3">
          <div>
            <Link to="/" className={cn(FOCUS_RING, 'mb-4 inline-flex rounded-lg')} aria-label={t('nav.homeAria')}>
              <Brand />
            </Link>
            <p className="mb-2 text-sm text-text-secondary leading-relaxed sm:mb-5">
              {t('footer.tagline')}
            </p>
            <FooterGroup title={t('footer.sources')} desktop={desktop}>
              {sourceLinks.map((item) => (
                <li key={item.key}>
                  <SourceLink href={item.href} className={footLink}>
                    {t(item.key)}
                  </SourceLink>
                </li>
              ))}
            </FooterGroup>
          </div>

          {catalog.kind === 'countries' ? (
            <FooterGroup
              title={t(catalog.headingKey)}
              hubTo={catalog.headingTo}
              desktop={desktop}
            >
              {catalog.links.map((item) => (
                <li key={item.key}>
                  <Link to={item.to} className={footLink}>
                    {item.label}
                  </Link>
                </li>
              ))}
            </FooterGroup>
          ) : (
            <FooterGroup
              title={t('footer.categories')}
              hubTo={russiaCategoriesPath()}
              hubLabel={t('shell.footer.allCategories')}
              desktop={desktop}
            >
              {CATEGORIES.filter((c) => c.apiCategory).map((c) => (
                <li key={c.slug}>
                  <Link to={russiaCategoryPath(c.slug)} className={footLink}>
                    {categoryLabel(c)}
                  </Link>
                </li>
              ))}
              {CATEGORIES.filter((c) => !c.apiCategory).map((c) => (
                <li key={c.slug} className="text-text-tertiary">
                  {categoryLabel(c)} <span className="text-xs">{t('common.soon')}</span>
                </li>
              ))}
            </FooterGroup>
          )}

          <FooterGroup title={t('footer.section.world')} desktop={desktop}>
            {worldLinks.map((item) => (
              <li key={item.key}>
                <Link to={item.to} className={footLink}>
                  {t(item.key)}
                </Link>
              </li>
            ))}
          </FooterGroup>

          <FooterGroup title={t(homeCountry.sectionKey)} desktop={desktop}>
            {homeCountry.links.map((item) => (
              <li key={item.key}>
                <Link to={item.to} className={footLink}>
                  {t(item.key)}
                </Link>
              </li>
            ))}
          </FooterGroup>

          <FooterGroup title={t('footer.tools')} desktop={desktop}>
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
          </FooterGroup>

          <FooterGroup title={t('footer.info')} desktop={desktop}>
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
              <Link to="/about#credits" className={footLink}>
                {t('footer.credits')}
              </Link>
            </li>
            <li>
              <button type="button" onClick={openConsentSettings} className={cn(footLink, 'text-left')}>
                {t('footer.cookies')}
              </button>
            </li>
            <li>
              <a
                href="mailto:rebeka.ee@yandex.ru"
                className={footLink}
                title="rebeka.ee@yandex.ru"
                onClick={() => track(events.CONTACT_EMAIL)}
              >
                {t('shell.footer.contact')}
              </a>
            </li>
          </FooterGroup>
        </div>

        <div className="fe-foot-bottom">
          <p className="fe-foot-updates">
            <span className="fe-foot-updates__dot" aria-hidden="true" />
            {t('shell.footer.updates')}
          </p>

          <div className="fe-foot-legal">
            <p>
              &copy; {new Date().getFullYear()} Forecast Economy. {t('footer.disclaimer')}
            </p>
            {desktop ? (
              <p>{t('footer.operator')}</p>
            ) : (
              <details className="fe-foot-requisites">
                <summary className={cn(FOCUS_RING, 'fe-foot-requisites__summary')}>
                  {t('shell.footer.requisites')}
                </summary>
                <p>{t('footer.operator')}</p>
              </details>
            )}
          </div>
        </div>
      </div>
    </footer>
  );
}
