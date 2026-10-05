/**
 * «Возможно, вы искали»: по словам из неверного адреса подсказывает раздел сайта.
 * Правила совпадают с backend/app/services/seo_renderer.py (`_NF_GUESS_RULES`):
 * серверная и клиентская 404 подсказывают одно и то же.
 */
import {
  calendarPath,
  comparePath,
  countryPath,
  regionHubPath,
  russiaHomePath,
  todayPath,
  WORLD_RATING_DEFAULT_CONCEPT,
  worldRatingPath,
} from './sitePaths';

const RULES = [
  { keys: ['rank', 'rating', 'gdp', 'vvp', 'top'], id: 'rating' },
  { keys: ['calc', 'calculator', 'kalk', 'inflation', 'mortgage', 'ipotek'], id: 'calculator' },
  { keys: ['region', 'regions', 'oblast', 'okrug'], id: 'regions' },
  { keys: ['compare', 'comparison', 'vs', 'sravn'], id: 'compare' },
  { keys: ['today', 'segodnya', 'now'], id: 'today' },
  { keys: ['calendar', 'kalendar', 'schedule'], id: 'calendar' },
  { keys: ['currency', 'currencies', 'usd', 'eur', 'dollar', 'rate', 'rates', 'kurs', 'fx'], id: 'currencies' },
  { keys: ['usa', 'us', 'america', 'states'], id: 'usa' },
  { keys: ['russia', 'rossiya', 'rus'], id: 'russia' },
  { keys: ['about', 'contact', 'contacts'], id: 'about' },
  { keys: ['method', 'methodology', 'forecast', 'prognoz'], id: 'methodology' },
];

const TARGETS = {
  rating: { to: worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT), labelKey: 'w6f.nf.guess.rating' },
  calculator: { to: '/calculator', labelKey: 'w6f.nf.guess.calculator' },
  regions: { to: regionHubPath(), labelKey: 'w6f.nf.guess.regions' },
  compare: { to: comparePath(), labelKey: 'w6f.nf.guess.compare' },
  today: { to: todayPath(), labelKey: 'w6f.nf.guess.today' },
  calendar: { to: calendarPath(), labelKey: 'w6f.nf.guess.calendar' },
  currencies: { to: '/currencies', labelKey: 'w6f.nf.guess.currencies' },
  usa: { to: countryPath('united-states'), labelKey: 'w6f.nf.guess.usa' },
  russia: { to: russiaHomePath(), labelKey: 'w6f.nf.guess.russia' },
  about: { to: '/about', labelKey: 'w6f.nf.guess.about' },
  methodology: { to: '/methodology', labelKey: 'w6f.nf.guess.methodology' },
};

/** Не больше трёх подсказок: [{ to, labelKey }]. Пустой массив, если в адресе нет знакомых слов. */
export function suggestForPath(pathname) {
  const raw = String(pathname || '').split('?')[0].toLowerCase();
  const words = raw.match(/[a-z]+/g);
  if (!words) return [];
  const hit = (keys) => words.some((w) => keys.some((k) => w === k || (k.length >= 4 && w.startsWith(k))));
  const found = [];
  for (const rule of RULES) {
    if (hit(rule.keys)) found.push(TARGETS[rule.id]);
    if (found.length === 3) break;
  }
  return found;
}
