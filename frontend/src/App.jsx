import { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, useParams, useLocation, Link } from 'react-router-dom';
import Navbar from './components/Navbar';
import NoiseOverlay from './components/NoiseOverlay';
import Footer from './components/Footer';
import Dashboard from './pages/Dashboard';
import IndicatorDetail from './pages/IndicatorDetail';
import About from './pages/About';
import Privacy from './pages/Privacy';
import CategoryPage from './pages/CategoryPage';
import ComparePage from './pages/ComparePage';

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

export default function App() {
  return (
    <Router>
      <ScrollToTop />
      <NoiseOverlay />
      <Navbar />
      <main className="relative z-0 flex-1">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/about" element={<About />} />
          <Route path="/privacy" element={<Privacy />} />
          <Route path="/category/:slug" element={<CategoryPage />} />
          <Route path="/compare" element={<ComparePage />} />
          <Route path="/indicator/:code" element={<IndicatorDetailKeyed />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
      <Footer />
    </Router>
  );
}
