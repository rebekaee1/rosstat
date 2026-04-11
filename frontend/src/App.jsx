import { useEffect, useRef, lazy, Suspense } from 'react';
import { BrowserRouter as Router, Routes, Route, useParams, useLocation, Link } from 'react-router-dom';
import Navbar from './components/Navbar';
import NoiseOverlay from './components/NoiseOverlay';
import Footer from './components/Footer';
import ErrorBoundary from './components/ErrorBoundary';
import { SkeletonBox } from './components/Skeleton';
import useDocumentMeta from './lib/useMeta';
import Dashboard from './pages/Dashboard';

const IndicatorDetail = lazy(() => import('./pages/IndicatorDetail'));
const About = lazy(() => import('./pages/About'));
const Privacy = lazy(() => import('./pages/Privacy'));
const CategoryPage = lazy(() => import('./pages/CategoryPage'));
const ComparePage = lazy(() => import('./pages/ComparePage'));
const CalendarPage = lazy(() => import('./pages/CalendarPage'));
const EmbedBuilder = lazy(() => import('./pages/EmbedBuilder'));
const CalculatorPage = lazy(() => import('./pages/CalculatorPage'));
const DemographicsPage = lazy(() => import('./pages/DemographicsPage'));

const EmbedChart = lazy(() => import('./embed/EmbedChart'));
const EmbedCard = lazy(() => import('./embed/EmbedCard'));
const EmbedTable = lazy(() => import('./embed/EmbedTable'));
const EmbedTicker = lazy(() => import('./embed/EmbedTicker'));
const EmbedCompare = lazy(() => import('./embed/EmbedCompare'));

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => { window.scrollTo(0, 0); }, [pathname]);
  return null;
}

function YandexMetrikaHit() {
  const location = useLocation();
  const isFirst = useRef(true);
  useEffect(() => {
    if (isFirst.current) { isFirst.current = false; return; }
    if (typeof window.ym === 'function') {
      window.ym(107136069, 'hit', location.pathname + location.search, {
        title: document.title,
      });
    }
  }, [location.pathname, location.search]);
  return null;
}

function IndicatorDetailKeyed() {
  const { code } = useParams();
  return <IndicatorDetail key={code} />;
}

function NotFound() {
  useDocumentMeta({
    title: '404 — Страница не найдена',
    description: 'Запрашиваемая страница не существует.',
    path: '/404',
  });

  return (
    <div className="max-w-2xl mx-auto px-4 pt-32 pb-24 text-center">
      <h1 className="text-6xl font-display font-bold text-text-primary mb-4">404</h1>
      <p className="text-lg text-text-secondary mb-8">Страница не найдена</p>
      <Link
        to="/"
        className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-champagne/10 text-champagne font-medium hover:bg-champagne/20 transition-colors"
      >
        На главную
      </Link>
    </div>
  );
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
  );
}

function AppRoutes() {
  const location = useLocation();

  if (EMBED_RE.test(location.pathname)) {
    return <EmbedRoutes />;
  }

  return (
    <>
      <ScrollToTop />
      <YandexMetrikaHit />
      <NoiseOverlay />
      <Navbar />
      <main className="relative z-0 flex-1">
        <ErrorBoundary>
        <Suspense fallback={
          <div className="min-h-screen flex items-center justify-center">
            <SkeletonBox className="h-8 w-48" />
          </div>
        }>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/about" element={<About />} />
            <Route path="/privacy" element={<Privacy />} />
            <Route path="/category/:slug" element={<CategoryPage />} />
            <Route path="/compare" element={<ComparePage />} />
            <Route path="/calendar" element={<CalendarPage />} />
            <Route path="/widgets" element={<EmbedBuilder />} />
            <Route path="/calculator" element={<CalculatorPage />} />
            <Route path="/demographics" element={<DemographicsPage />} />
            <Route path="/indicator/:code" element={<IndicatorDetailKeyed />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Suspense>
        </ErrorBoundary>
      </main>
      <Footer />
    </>
  );
}

export default function App() {
  return (
    <Router>
      <AppRoutes />
    </Router>
  );
}
