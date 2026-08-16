import { Navigate, useParams } from 'react-router-dom';
import CalendarPage from './CalendarPage';
import {
  calendarPath,
} from '../lib/sitePaths';

/** SSR-посадочная /calendar/{year}/{month} — тот же UI, что интерактивный календарь. */
export default function CalendarMonthPage() {
  const { year, month } = useParams();
  const y = parseInt(year, 10);
  const m = parseInt(month, 10);
  if (!Number.isFinite(y) || !Number.isFinite(m) || m < 1 || m > 12 || y < 2000 || y > 2100) {
    return <Navigate to={calendarPath()} replace />;
  }
  const mm = String(m).padStart(2, '0');
  return (
    <CalendarPage
      key={`${y}-${mm}`}
      fixedYear={y}
      fixedMonth={m - 1}
      seoPath={calendarPath(y, mm)}
    />
  );
}
