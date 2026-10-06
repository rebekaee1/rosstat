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
 * Градиент «ледяной хрусталь» для силуэта страны (круг 6: прежний золотой кристалл снят, «слишком жёлтый»):
 * `#E8F0FA` → блик → `#7C9AC9` (60 %) → `#2C4A8A`. Силуэт рисует `CountrySilhouette`, заливку даёт CSS: `fill: url(#fe-k6-crystal)`.
 */
export function CrystalDefs() {
  return (
    <svg className="k6-crystal-defs" width="0" height="0" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id="fe-k6-crystal" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#E8F0FA" />
          <stop offset="0.3" stopColor="#C9D7EA" />
          <stop offset="0.42" stopColor="#FFFFFF" />
          <stop offset="0.5" stopColor="#A9BFE0" />
          <stop offset="0.6" stopColor="#7C9AC9" />
          <stop offset="1" stopColor="#2C4A8A" />
        </linearGradient>
      </defs>
    </svg>
  );
}

export default CountryMood;
