import { BrowserRouter as Router, Routes, Route, useParams } from 'react-router-dom';
import Navbar from './components/Navbar';
import NoiseOverlay from './components/NoiseOverlay';
import Footer from './components/Footer';
import Dashboard from './pages/Dashboard';
import IndicatorDetail from './pages/IndicatorDetail';
import About from './pages/About';
import Privacy from './pages/Privacy';
import CategoryPage from './pages/CategoryPage';
import ComparePage from './pages/ComparePage';

function IndicatorDetailKeyed() {
  const { code } = useParams();
  return <IndicatorDetail key={code} />;
}

export default function App() {
  return (
    <Router>
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
        </Routes>
      </main>
      <Footer />
    </Router>
  );
}
