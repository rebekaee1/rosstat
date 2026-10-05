import { useEffect, useRef, lazy, Suspense } from 'react';
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
  useParams,
  useLocation,
  Link,
} from 'react-router-dom';
import Navbar from './components/Navbar';
import YandexRSY from './components/YandexRSY';
import CookieConsent from './components/CookieConsent';
import Footer from './components/Footer';
import ScrollToAnchor from './components/ScrollToAnchor';
import ErrorBoundary from './components/ErrorBoundary';
import RegisterNudge from './components/RegisterNudge';
import DownloadLimitModal from './components/DownloadLimitModal';
import ApiInterestModal from './components/ApiInterestModal';
import PwaInstallPrompt from './components/PwaInstallPrompt';
import RouteFallback from './components/RouteFallback';
import PageProgress from './components/PageProgress';
import SkipLink from './components/SkipLink';
import { cleanPathWithSearch } from './lib/cleanUrl';
import { calculatorAliasTarget } from './lib/calculatorAlias';
import { behaviorInit, behaviorRouteChange } from './lib/behavior';
import { sessionReplayInit, replayRouteChange } from './lib/sessionReplay';
import { isVariantSiblingNavigation } from './lib/indicatorVariants';
import { AuthProvider } from './context/AuthProvider';
import { LocaleProvider, LocalePreviewBanner, LocalePreviewSync } from './i18n';
import Dashboard from './pages/Dashboard';
import NotFound from './pages/NotFound';
import {
  RUSSIA,
  calendarPath,
  countryPath,
  demographicsPath,
  indicatorPath,
  isReservedFirstSegment,
  regionHubPath,
  regionIndicatorPath,
  regionMapPath,
  regionPath,
  regionRatingPath,
  regionVsPath,
  russiaCategoryPath,
  russiaIndicatorPath,
  russiaIndicatorYearPath,
  todayPath,
  WORLD_RATING_DEFAULT_CONCEPT,
  worldRatingPath,
} from './lib/sitePaths';

const LiveTicker = lazy(() => import('./components/LiveTicker'));
const IndicatorDetail = lazy(() => import('./pages/IndicatorDetail'));
const About = lazy(() => import('./pages/About'));
const Methodology = lazy(() => import('./pages/Methodology'));
const Privacy = lazy(() => import('./pages/Privacy'));
const Terms = lazy(() => import('./pages/Terms'));
const CategoryPage = lazy(() => import('./pages/CategoryPage'));
const CategoriesHub = lazy(() => import('./pages/CategoriesHub'));
const RegionRatingsHub = lazy(() => import('./pages/RegionRatingsHub'));
const ComparePage = lazy(() => import('./pages/ComparePage'));
const ForecastsPage = lazy(() => import('./pages/ForecastsPage'));
const CalendarPage = lazy(() => import('./pages/CalendarPage'));
const EmbedBuilder = lazy(() => import('./pages/EmbedBuilder'));
const CalculatorPage = lazy(() => import('./pages/CalculatorPage'));
const MortgageCalculatorPage = lazy(() => import('./pages/MortgageCalculatorPage'));
const CompoundCalculatorPage = lazy(() => import('./pages/CompoundCalculatorPage'));
const DemographicsPage = lazy(() => import('./pages/DemographicsPage'));
const Login = lazy(() => import('./pages/Login'));
const Register = lazy(() => import('./pages/Register'));
const Account = lazy(() => import('./pages/Account'));
const RegionsHome = lazy(() => import('./pages/RegionsHome'));
const RegionProfile = lazy(() => import('./pages/RegionProfile'));
const RegionIndicatorPage = lazy(() => import('./pages/RegionIndicatorPage'));
const WorldRatingPage = lazy(() => import('./pages/WorldRatingPage'));
const WorldCountry = lazy(() => import('./pages/WorldCountry'));
const WorldIndicatorPage = lazy(() => import('./pages/WorldIndicatorPage'));
const WorldRegionsHome = lazy(() => import('./pages/WorldRegionsHome'));
const WorldRegionProfile = lazy(() => import('./pages/WorldRegionProfile'));
const WorldRegionIndicatorPage = lazy(() => import('./pages/WorldRegionIndicatorPage'));
const RussiaHome = lazy(() => import('./pages/RussiaHome'));
const TodayHub = lazy(() => import('./pages/TodayHub'));
const TodayIndicatorPage = lazy(() => import('./pages/TodayIndicatorPage'));
const RegionRatingPage = lazy(() => import('./pages/RegionRatingPage'));
const RegionComparePage = lazy(() => import('./pages/RegionComparePage'));
const CalendarMonthPage = lazy(() => import('./pages/CalendarMonthPage'));
const AdminBI = lazy(() => import('./pages/AdminBI'));

const EmbedChart = lazy(() => import('./embed/EmbedChart'));
const EmbedCard = lazy(() => import('./embed/EmbedCard'));
const EmbedTable = lazy(() => import('./embed/EmbedTable'));
const EmbedTicker = lazy(() => import('./embed/EmbedTicker'));
const EmbedCompare = lazy(() => import('./embed/EmbedCompare'));

function ScrollToTop() {
  const { pathname } = useLocation();
  const prevPathname = useRef(pathname);
  useEffect(() => {
    const prev = prevPathname.current;
    prevPathname.current = pathname;
    if (isVariantSiblingNavigation(prev, pathname)) return;
    // Мгновенно: при html{scroll-behavior:smooth} обычный scrollTo плавно «уезжал» вверх на каждом переходе.
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
  }, [pathname]);
  return null;
}

function YandexMetrikaHit() {
  const location = useLocation();
  const isFirst = useRef(true);
  const prevUrl = useRef(cleanPathWithSearch(window.location.pathname, window.location.search));
  useEffect(() => { behaviorInit(); sessionReplayInit(); }, []);
  useEffect(() => {
    if (isFirst.current) { isFirst.current = false; return; }
    const url = cleanPathWithSearch(location.pathname, location.search);
    behaviorRouteChange(url);
    replayRouteChange();
    const referer = prevUrl.current;
    prevUrl.current = url;
    // Delay to let page component update document.title via useDocumentMeta
    const timer = setTimeout(() => {
      if (typeof window.ym === 'function') {
        window.ym(107136069, 'hit', url, {
          title: document.title,
          referer: window.location.origin + referer,
        });
      }
    }, 50);
    return () => clearTimeout(timer);
  }, [location.pathname, location.search]);
  return null;
}

function IndicatorDetailKeyed() {
  const { code } = useParams();
  return <IndicatorDetail key={code} />;
}

/** Мировая карточка страны: /:countrySlug (не russia, не reserved). */
function WorldCountryRoute() {
  const { countrySlug } = useParams();
  if (isReservedFirstSegment(countrySlug) || countrySlug === RUSSIA) {
    return <NotFound />;
  }
  return <WorldCountry />;
}

/** Мировой индикатор: /:countrySlug/indicator/:code (не russia). */
function WorldIndicatorRoute() {
  const { countrySlug } = useParams();
  if (isReservedFirstSegment(countrySlug) || countrySlug === RUSSIA) {
    return <NotFound />;
  }
  return <WorldIndicatorPage />;
}

function RedirectTo({ build }) {
  const params = useParams();
  const { search } = useLocation();
  return <Navigate to={`${build(params)}${search}`} replace />;
}

/** Legacy path redirect that keeps ?preview_locale= and other query args. */
function NavigateKeepSearch({ to }) {
  const { search } = useLocation();
  return <Navigate to={`${to}${search}`} replace />;
}

/** Угаданные адреса калькуляторов: /calculators/mortgage → /calculator/mortgage, всё прочее → /calculator. */
function CalculatorsAlias() {
  const params = useParams();
  return <NavigateKeepSearch to={calculatorAliasTarget(params['*'])} />;
}

/** Guessed address of the country list: the home page, scrolled to the list. */
function CountriesToHome() {
  const { search } = useLocation();
  return <Navigate to={{ pathname: '/', search, hash: '#countries' }} replace />;
}

/**
 * Сервер уже признал этот адрес несуществующим и отдал документ 404 с флагом `window.__feNotFound`
 * (backend `render_not_found_html`). Приложение показывает свою страницу 404 в общей оболочке:
 * без этого адрес вроде `/germany/indicator/нет` открыл бы пустую карточку страны.
 * Флаг действует только на этом адресе: любой переход по ссылке работает как обычно.
 */
const SERVER_404_PATH = typeof window !== 'undefined' && window.__feNotFound ? window.location.pathname : null;

function ServerNotFoundGate({ children }) {
  const { pathname } = useLocation();
  return SERVER_404_PATH !== null && pathname === SERVER_404_PATH ? <NotFound /> : children;
}

const EMBED_RE = /^\/embed\/(chart|card|table|ticker|compare)/;

function EmbedSpinner() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh' }}>
      <div className="embed-spin" style={{ width: 24, height: 24, border: '2px solid #e5e5e5', borderTopColor: 'transparent', borderRadius: '50%' }} />
      <style>{`@keyframes espin{to{transform:rotate(360deg)}}.embed-spin{animation:espin 1s linear infinite}@media(prefers-reduced-motion:reduce){.embed-spin{animation:none;opacity:.4}}`}</style>
    </div>
  );
}

function EmbedRoutes() {
  return (
    <LocaleProvider>
    <ErrorBoundary>
      <Suspense fallback={<EmbedSpinner />}>
        <Routes>
          <Route path="/embed/chart/:code" element={<EmbedChart />} />
          <Route path="/embed/card/:code" element={<EmbedCard />} />
          <Route path="/embed/table/:code" element={<EmbedTable />} />
          <Route path="/embed/ticker" element={<EmbedTicker />} />
          <Route path="/embed/compare" element={<EmbedCompare />} />
        </Routes>
      </Suspense>
    </ErrorBoundary>
    </LocaleProvider>
  );
}

function AppRoutes() {
  const location = useLocation();

  if (EMBED_RE.test(location.pathname)) {
    return <EmbedRoutes />;
  }

  return (
    <LocaleProvider>
    <AuthProvider>
      <SkipLink />
      <LocalePreviewSync />
      <LocalePreviewBanner />
      <ScrollToTop />
      <PageProgress />
      <ScrollToAnchor />
      <YandexMetrikaHit />
      <YandexRSY />
      {/* Cookie-баннер не монтируется на /embed/* — iframe на чужих сайтах */}
      <CookieConsent />
      {/* Бегущая строка — декор: сбой её чанка не должен ронять всё приложение. */}
      <ErrorBoundary fallback={null}>
        <Suspense fallback={<div className="fixed top-0 inset-x-0 z-[110] h-9 bg-[#faf7f0]" style={{ height: 36 }} aria-hidden="true" />}>
          <LiveTicker />
        </Suspense>
      </ErrorBoundary>
      <Navbar />
      <main id="main-content" tabIndex={-1} className="relative z-0 flex-1 pt-9 outline-none">
        <ErrorBoundary>
        <Suspense fallback={<RouteFallback />}>
          <ServerNotFoundGate>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/about" element={<About />} />
            <Route path="/methodology" element={<Methodology />} />
            <Route path="/privacy" element={<Privacy />} />
            <Route path="/terms" element={<Terms />} />
            <Route path="/compare" element={<ComparePage />} />
            <Route path="/forecasts" element={<ForecastsPage />} />
            <Route path="/widgets" element={<EmbedBuilder />} />
            <Route path="/calculator" element={<CalculatorPage />} />
            <Route path="/calculator/mortgage" element={<MortgageCalculatorPage />} />
            <Route path="/calculator/compound" element={<CompoundCalculatorPage />} />
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/account" element={<Account />} />
            <Route path="/admin/bi" element={<AdminBI />} />

            {/* Мир: хаб и рейтинги до country catch-all */}
            <Route path="/world/rating" element={<WorldRatingPage />} />
            <Route path="/world/rating/:conceptSlug/:year?" element={<WorldRatingPage />} />

            <Route path="/currencies" element={<CategoryPage fixedSlug="currencies" />} />
            <Route path="/currencies/indicator/:code" element={<IndicatorDetailKeyed />} />
            <Route path="/currencies/indicator/:code/:year" element={<IndicatorDetailKeyed />} />

            {/* Россия — явные префиксы */}
            <Route path="/russia" element={<RussiaHome />} />
            <Route path="/russia/category" element={<CategoriesHub />} />
            <Route path="/russia/category/:slug" element={<CategoryPage />} />
            <Route path="/russia/indicator/:code" element={<IndicatorDetailKeyed />} />
            <Route path="/russia/indicator/:code/:year" element={<IndicatorDetailKeyed />} />
            <Route path="/russia/today" element={<TodayHub />} />
            <Route path="/russia/today/:code" element={<TodayIndicatorPage />} />
            <Route path="/russia/calendar" element={<CalendarPage />} />
            <Route path="/russia/calendar/:year/:month" element={<CalendarMonthPage />} />
            <Route path="/russia/demographics" element={<DemographicsPage />} />
            <Route path="/russia/region/map/:code" element={<RegionsHome />} />
            <Route path="/russia/region" element={<RegionsHome />} />
            <Route path="/russia/region/:slug" element={<RegionProfile />} />
            <Route path="/russia/region/:slug/:code" element={<RegionIndicatorPage />} />
            <Route path="/russia/region-rating" element={<RegionRatingsHub />} />
            <Route path="/russia/region-rating/:code" element={<RegionRatingPage />} />
            <Route path="/russia/region-vs/:pair" element={<RegionComparePage />} />

            {/* Субнациональные регионы других стран — до /:countrySlug */}
            <Route path="/:countrySlug/regions" element={<WorldRegionsHome />} />
            <Route path="/:countrySlug/region/map/:code" element={<WorldRegionsHome />} />
            <Route path="/:countrySlug/region/:slug/:code" element={<WorldRegionIndicatorPage />} />
            <Route path="/:countrySlug/region/:slug" element={<WorldRegionProfile />} />

            {/* Другие страны: /{slug}/indicator/{code} и /{slug} */}
            <Route path="/:countrySlug/indicator/:code/:year" element={<WorldIndicatorRoute />} />
            <Route path="/:countrySlug/indicator/:code" element={<WorldIndicatorRoute />} />
            <Route path="/:countrySlug/category/:slug" element={<NotFound />} />
            <Route path="/:countrySlug" element={<WorldCountryRoute />} />

            {/* Legacy → канон (клиентский safety; nginx 301 на проде) */}
            <Route path="/category/:slug" element={<RedirectTo build={({ slug }) => russiaCategoryPath(slug)} />} />
            <Route path="/indicator/:code/:year" element={<RedirectTo build={({ code, year }) => russiaIndicatorYearPath(code, year)} />} />
            <Route path="/indicator/:code" element={<RedirectTo build={({ code }) => russiaIndicatorPath(code)} />} />
            {/* Названия, которые люди угадывают: рейтинг стран и калькуляторы (nginx на проде делает то же 301). */}
            <Route path="/rankings" element={<NavigateKeepSearch to={worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT)} />} />
            <Route path="/ranking" element={<NavigateKeepSearch to={worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT)} />} />
            <Route path="/rankings/gdp" element={<NavigateKeepSearch to={worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT)} />} />
            <Route path="/ranking/gdp" element={<NavigateKeepSearch to={worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT)} />} />
            <Route path="/calculators" element={<NavigateKeepSearch to="/calculator" />} />
            <Route path="/calculators/*" element={<CalculatorsAlias />} />
            <Route path="/today" element={<NavigateKeepSearch to={todayPath()} />} />
            <Route path="/today/:code" element={<RedirectTo build={({ code }) => todayPath(code)} />} />
            <Route path="/calendar" element={<NavigateKeepSearch to={calendarPath()} />} />
            <Route path="/calendar/:year/:month" element={<RedirectTo build={({ year, month }) => calendarPath(year, month)} />} />
            <Route path="/demographics" element={<NavigateKeepSearch to={demographicsPath()} />} />
            <Route path="/regions" element={<NavigateKeepSearch to={regionHubPath()} />} />
            <Route path="/russia/regions" element={<NavigateKeepSearch to={regionHubPath()} />} />
            <Route path="/countries" element={<CountriesToHome />} />
            <Route path="/countries/:slug" element={<RedirectTo build={({ slug }) => countryPath(slug)} />} />
            <Route path="/regions/map/:code" element={<RedirectTo build={({ code }) => regionMapPath(code)} />} />
            <Route path="/region/:slug" element={<RedirectTo build={({ slug }) => regionPath(slug)} />} />
            <Route path="/region/:slug/:code" element={<RedirectTo build={({ slug, code }) => regionIndicatorPath(slug, code)} />} />
            <Route path="/region-rating/:code" element={<RedirectTo build={({ code }) => regionRatingPath(code)} />} />
            <Route path="/region-vs/:pair" element={<RedirectTo build={({ pair }) => {
              const m = String(pair || '').match(/^(.+)-vs-(.+)$/);
              return m ? regionVsPath(m[1], m[2]) : regionHubPath();
            }} />} />
            <Route path="/world/:slug/:code" element={<RedirectTo build={({ slug, code }) => indicatorPath(slug, code)} />} />
            <Route path="/world/:slug" element={<RedirectTo build={({ slug }) => {
              if (slug === 'rating') return '/world/rating';
              return countryPath(slug);
            }} />} />

            <Route path="*" element={<NotFound />} />
          </Routes>
          </ServerNotFoundGate>
          </Suspense>
        </ErrorBoundary>
      </main>
      <RegisterNudge />
      <PwaInstallPrompt />
      <Footer />
      <DownloadLimitModal />
      <ApiInterestModal />
    </AuthProvider>
    </LocaleProvider>
  );
}

export default function App() {
  return (
    <Router>
      <AppRoutes />
    </Router>
  );
}
