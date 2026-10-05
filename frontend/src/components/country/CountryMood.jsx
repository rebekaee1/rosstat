// Настроение страны (K6.2) и градиент золотого кристалла для её силуэта (K6.1).
import { moodColors } from '../../lib/countryMood';
import '../../styles/z5-country.css';
import '../../styles/k6-country.css';

/** Два размытых пятна цветов флага за текстом героя. Чисто декоративно; плавание 20 с (CSS), выключается при reduced-motion. */
export function CountryMood({ code }) {
  const [first, second] = moodColors(code);
  return <span className="z5-mood" aria-hidden="true" data-testid="country-mood" style={{ '--mood-a': first, '--mood-b': second }} />;
}

/**
 * Градиент «золотой кристалл» для силуэта страны: `#F3E4B8` → блик → `#B08A3E` (60 %) → `#7A5F2A`.
 * Силуэт рисует `CountrySilhouette` (общий компонент карты), заливку ему даёт CSS: `fill: url(#fe-k6-crystal)`.
 */
export function CrystalDefs() {
  return (
    <svg className="k6-crystal-defs" width="0" height="0" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id="fe-k6-crystal" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#F3E4B8" />
          <stop offset="0.3" stopColor="#E9CF8E" />
          <stop offset="0.42" stopColor="#FFF6DA" />
          <stop offset="0.5" stopColor="#D9B766" />
          <stop offset="0.6" stopColor="#B08A3E" />
          <stop offset="1" stopColor="#7A5F2A" />
        </linearGradient>
      </defs>
    </svg>
  );
}

export default CountryMood;
