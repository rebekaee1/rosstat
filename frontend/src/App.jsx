import { useEffect, lazy, Suspense } from 'react';
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

const EMBED_RE = /^\/embed\/(chart|card|table|ticker|compare|calculator)/;

function EmbedRoutes() {
  return (
    <Suspense fallback={null}>
      <Routes>
        <Route path="/embed/chart/:code" element={<EmbedChart />} />
        <Route path="/embed/card/:code" element={<EmbedCard />} />
        <Route path="/embed/table/:code" element={<EmbedTable />} />
        <Route path="/embed/ticker" element={<EmbedTicker />} />
        <Route path="/embed/compare" element={<EmbedCompare />} />
      </Routes>
    </Suspense>
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
