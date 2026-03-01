import { BrowserRouter as Router, Routes, Route, useParams } from 'react-router-dom';
import Navbar from './components/Navbar';
import NoiseOverlay from './components/NoiseOverlay';
import Footer from './components/Footer';
import Dashboard from './pages/Dashboard';
import IndicatorDetail from './pages/IndicatorDetail';

function IndicatorDetailKeyed() {
  const { code } = useParams();
  return <IndicatorDetail key={code} />;
}

export default function App() {
  return (
    <Router>
      <NoiseOverlay />
      <Navbar />
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/indicator/:code" element={<IndicatorDetailKeyed />} />
        </Routes>
      </main>
      <Footer />
    </Router>
  );
}
