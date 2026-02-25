import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import NoiseOverlay from './components/NoiseOverlay';
import Footer from './components/Footer';
import Dashboard from './pages/Dashboard';
import IndicatorDetail from './pages/IndicatorDetail';

export default function App() {
  return (
    <Router>
      <NoiseOverlay />
      <Navbar />
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/indicator/:code" element={<IndicatorDetail />} />
        </Routes>
      </main>
      <Footer />
    </Router>
  );
}
