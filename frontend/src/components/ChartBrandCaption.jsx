import { useAuth } from '../context/authContext';

/** Гостевая подпись домена под интерактивным графиком. */
export default function ChartBrandCaption() {
  const { isAuthed, isLoading } = useAuth();
  if (isAuthed || isLoading) return null;
  return (
    <p className="fe-chart-signature" aria-label="forecasteconomy.com">
      forecasteconomy.com
    </p>
  );
}
