import { useId } from 'react';
import { Bell, Check, Search, Star } from 'lucide-react';
import { layoutChips } from '../../lib/welcome';

/**
 * Сцены приветственного экрана: по одной мысли на шаг. Чистый SVG (вектор: на любом экране без пикселя, принцип 9),
 * движение задаёт `styles/welcome.css` классами `wl-*` и задержкой `--d`.
 *
 * Сцена стоит на тёмном сапфире: светлые стеклянные плиты читаются как предметы под светом, под каждой холодное свечение.
 *
 * Правила сцен:
 *  - настоящих чисел нет: вместо значений полосы-заготовки (на сайте статистики выдуманная цифра выглядит как ошибка данных);
 *  - прогноз — одна тонкая золотая линия до одной точки, без коридора (принцип 8);
 *  - базовый вид каждого элемента (без анимации) — итоговый кадр: при `prefers-reduced-motion` сцена стоит готовой;
 *  - в конце по главной плите один раз проходит блик: сцена не обрывается, а «оседает»;
 *  - сцены украшают текст и скрыты от экранного чтения (`aria-hidden`), смысл несут заголовок и абзац шага.
 */
const INK = '#16213D';
const BLUE = '#2C4A8A';
const TEAL = '#238F9B';
const GOLD = '#C9A24D';
const BAR = 'rgba(30, 58, 110, 0.13)';
const BAR_STRONG = 'rgba(30, 58, 110, 0.26)';
const GHOST = 'rgba(255, 255, 255, 0.1)';
const GHOST_BAR = 'rgba(255, 255, 255, 0.26)';
const CARD = '#F7F9FD';

function Defs({ uid }) {
  return (
    <defs>
      <linearGradient id={`wl-glass-${uid}`} x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="#FFFFFF" />
        <stop offset="1" stopColor="#E9EEF8" />
      </linearGradient>
      <linearGradient id={`wl-blue-${uid}`} x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="#4C74CF" />
        <stop offset="1" stopColor="#2C4A8A" />
      </linearGradient>
      <linearGradient id={`wl-area-${uid}`} x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stopColor={BLUE} stopOpacity="0.22" />
        <stop offset="1" stopColor={BLUE} stopOpacity="0" />
      </linearGradient>
      <linearGradient id={`wl-sheen-${uid}`} x1="0" y1="0" x2="1" y2="0">
        <stop offset="0" stopColor="#FFFFFF" stopOpacity="0" />
        <stop offset="0.5" stopColor="#FFFFFF" stopOpacity="0.85" />
        <stop offset="1" stopColor="#FFFFFF" stopOpacity="0" />
      </linearGradient>
      <radialGradient id={`wl-glow-${uid}`} cx="0.5" cy="0.5" r="0.5">
        <stop offset="0" stopColor="#7FA2F2" stopOpacity="0.5" />
        <stop offset="0.55" stopColor="#5E86E6" stopOpacity="0.16" />
        <stop offset="1" stopColor="#5E86E6" stopOpacity="0" />
      </radialGradient>
    </defs>
  );
}

/** Стеклянная плита: холодное свечение под ней (вместо фильтра: фильтры SVG дороги при движении), тело и блик сверху. */
function Slab({ uid, x, y, w, h, r = 18, fill }) {
  return (
    <>
      <ellipse cx={x + w / 2} cy={y + h + 2} rx={w * 0.56} ry={Math.max(16, h * 0.34)} fill={`url(#wl-glow-${uid})`} />
      <rect x={x} y={y} width={w} height={h} rx={r} fill={fill || `url(#wl-glass-${uid})`} />
      <rect x={x + r * 0.7} y={y + 0.6} width={w - r * 1.4} height="1" rx="0.5" fill="#FFFFFF" />
    </>
  );
}

/** Блик проходит по плите один раз, в самом конце сцены. `id` — свой контур обрезки. */
function Sheen({ uid, id, x, y, w, h, r, delay }) {
  return (
    <>
      <clipPath id={`wl-sheen-${id}-${uid}`}><rect x={x} y={y} width={w} height={h} rx={r} /></clipPath>
      <g clipPath={`url(#wl-sheen-${id}-${uid})`}>
        <rect
          x={x - 90} y={y - 20} width={70} height={h + 40} fill={`url(#wl-sheen-${uid})`}
          className="wl-sheen" style={{ '--d': delay, '--sx': `${w + 180}px` }}
        />
      </g>
    </>
  );
}

const LINE = 'M58 224 C 84 222, 96 200, 120 204 S 156 228, 180 206 S 214 168, 238 176 S 268 190, 292 160';
const AREA = `${LINE} L 292 252 L 58 252 Z`;

/** Шаг «Как пользоваться»: слово в поиске, строки выдачи, график. */
function FindArt({ uid, t }) {
  const word = [...t('welcome.find.word')];
  return (
    <svg viewBox="28 14 344 272" className="fe-wl-svg" aria-hidden="true" focusable="false">
      <Defs uid={uid} />
      <g className="wl-rise" style={{ '--d': '0ms' }}>
        <Slab uid={uid} x={40} y={28} w={320} h={52} r={26} />
        <Search x={60} y={44} width={20} height={20} color={INK} strokeWidth={2.2} opacity={0.7} />
        <text x={92} y={60.5} className="fe-wl-svg__word">
          {word.map((ch, i) => (
            // Ключ по месту буквы: слово не меняется, пока сцена на экране.
            <tspan key={i} className="wl-type" style={{ '--d': `${420 + i * 66}ms` }}>{ch}</tspan>
          ))}
          <tspan className="wl-caret" dx="2" style={{ '--d': `${420 + word.length * 66}ms` }}>|</tspan>
        </text>
      </g>

      {[0, 1, 2].map((i) => (
        <g key={i} className="wl-rise" style={{ '--d': `${1150 + i * 90}ms` }}>
          <rect x={40} y={98 + i * 46} width={320} height={38} rx={13} fill={i === 0 ? CARD : GHOST} />
          <circle cx={62} cy={117 + i * 46} r={8} fill={i === 0 ? BLUE : GHOST_BAR} />
          <rect x={80} y={113 + i * 46} width={[132, 104, 148][i]} height={8} rx={4} fill={i === 0 ? BAR_STRONG : GHOST_BAR} />
          <rect x={306} y={113 + i * 46} width={36} height={8} rx={4} fill={i === 0 ? BAR : GHOST_BAR} />
        </g>
      ))}
      <circle cx={62} cy={117} r={15} fill="none" stroke="#9DB8F5" strokeWidth={1.5} className="wl-ping" style={{ '--d': '1750ms' }} />

      <g className="wl-rise wl-rise--far" style={{ '--d': '2100ms' }}>
        <Slab uid={uid} x={40} y={146} w={320} h={126} r={20} fill={CARD} />
        <rect x={58} y={162} width={96} height={8} rx={4} fill={BAR_STRONG} />
        <rect x={58} y={177} width={58} height={7} rx={3.5} fill={BAR} />
        <clipPath id={`wl-clip-find-${uid}`}><rect x={52} y={150} width={254} height={110} /></clipPath>
        <g clipPath={`url(#wl-clip-find-${uid})`}>
          <path d={AREA} fill={`url(#wl-area-${uid})`} />
          <path d={LINE} fill="none" stroke={BLUE} strokeWidth={2.75} strokeLinecap="round" />
          {/* Шторка цвета плиты уезжает вправо и открывает линию: движется только transform. */}
          <rect x={52} y={150} width={254} height={110} fill={CARD} className="wl-wipe" style={{ '--d': '2400ms', '--wx': '256px' }} />
        </g>
        <circle cx={292} cy={160} r={12} fill="none" stroke={BLUE} strokeWidth={1.5} className="wl-ping" style={{ '--d': '3250ms' }} />
        <circle cx={292} cy={160} r={5} fill={BLUE} stroke="#FFFFFF" strokeWidth={2} className="wl-pop" style={{ '--d': '3200ms' }} />
        <Sheen uid={uid} id="find" x={40} y={146} w={320} h={126} r={20} delay="3550ms" />
      </g>
    </svg>
  );
}

const F_LINE = 'M58 226 C 82 220, 92 196, 116 202 S 150 232, 176 208 S 206 170, 230 180 S 256 196, 276 168';
const F_AREA = `${F_LINE} L 276 244 L 58 244 Z`;

/** Шаг «Свежие данные»: источники отмечены, на графике появилась новая точка, дальше тонкая золотая линия прогноза. */
function FreshArt({ uid, t, sources }) {
  const names = sources?.length ? sources : [t('welcome.fresh.source1'), t('welcome.fresh.source2'), t('welcome.fresh.source3')];
  const chips = layoutChips(names);
  return (
    <svg viewBox="28 14 344 272" className="fe-wl-svg" aria-hidden="true" focusable="false">
      <Defs uid={uid} />
      {chips.map(({ label, w, x }, i) => (
        <g key={label} className="wl-rise" style={{ '--d': `${i * 110}ms` }}>
          <rect x={x} y={28} width={w} height={36} rx={18} fill={`url(#wl-glass-${uid})`} />
          <g className="wl-pop" style={{ '--d': `${520 + i * 300}ms` }}>
            <circle cx={x + 18} cy={46} r={9} fill={BLUE} />
            <Check x={x + 12} y={40} width={12} height={12} color="#FFFFFF" strokeWidth={3} />
          </g>
          <text x={x + 33} y={50.5} className="fe-wl-svg__chip">{label}</text>
        </g>
      ))}

      <g className="wl-rise" style={{ '--d': '320ms' }}>
        <Slab uid={uid} x={40} y={86} w={320} h={184} r={22} fill={CARD} />
        <rect x={58} y={104} width={104} height={8} rx={4} fill={BAR_STRONG} />
        <rect x={58} y={119} width={64} height={7} rx={3.5} fill={BAR} />
        {[166, 196, 226].map((y) => <rect key={y} x={58} y={y} width={284} height={1} fill={INK} fillOpacity={0.07} />)}
        <clipPath id={`wl-clip-fresh-${uid}`}><rect x={52} y={140} width={232} height={110} /></clipPath>
        <g clipPath={`url(#wl-clip-fresh-${uid})`}>
          <path d={F_AREA} fill={`url(#wl-area-${uid})`} />
          <path d={F_LINE} fill="none" stroke={BLUE} strokeWidth={2.75} strokeLinecap="round" />
          <rect x={52} y={140} width={232} height={110} fill={CARD} className="wl-wipe" style={{ '--d': '1450ms', '--wx': '234px' }} />
        </g>

        {/* Прогноз: одна золотая линия до одной точки, без коридора. */}
        <g className="wl-fade" style={{ '--d': '3000ms' }}>
          <path d="M276 168 C 296 160, 314 158, 336 150" fill="none" stroke={GOLD} strokeWidth={2.25} strokeLinecap="round" />
          <circle cx={336} cy={150} r={3.5} fill={GOLD} />
        </g>

        <circle cx={276} cy={168} r={14} fill="none" stroke={BLUE} strokeWidth={1.5} className="wl-ping" style={{ '--d': '2380ms' }} />
        <circle cx={276} cy={168} r={5.5} fill={BLUE} stroke="#FFFFFF" strokeWidth={2} className="wl-pop" style={{ '--d': '2300ms' }} />

        <g className="wl-rise wl-rise--near" style={{ '--d': '2520ms' }}>
          <rect x={218} y={126} width={112} height={27} rx={13.5} fill={INK} />
          <circle cx={233} cy={139.5} r={3} fill={GOLD} />
          <text x={243} y={144} className="fe-wl-svg__tag">{t('welcome.fresh.updated')}</text>
        </g>
        <Sheen uid={uid} id="fresh" x={40} y={86} w={320} h={184} r={22} delay="3350ms" />
      </g>
    </svg>
  );
}

/** Шаг «Telegram»: вопрос человека, ответ бота с графиком, кнопка «Присылать новые данные» включается. */
function TelegramArt({ uid, t }) {
  return (
    <svg viewBox="28 14 344 272" className="fe-wl-svg" aria-hidden="true" focusable="false">
      <Defs uid={uid} />
      <g className="wl-rise" style={{ '--d': '0ms' }}>
        <circle cx={58} cy={44} r={18} fill={`url(#wl-glass-${uid})`} />
        <path d="M51.5 53V40.5Q51.5 34 58.5 34H65V38.5H59Q56.5 38.5 56.5 41.5V42H63.5V46.5H56.5V53Z" fill={INK} />
        <rect x={62} y={48.5} width={3.4} height={4.5} fill={GOLD} />
        <text x={86} y={42} className="fe-wl-svg__name">Forecast Economy</text>
        <rect x={86} y={50} width={44} height={6} rx={3} fill={GHOST_BAR} />
      </g>

      <g className="wl-rise wl-rise--near" style={{ '--d': '480ms' }}>
        <rect x={232} y={78} width={128} height={38} rx={19} fill={`url(#wl-blue-${uid})`} />
        <text x={296} y={102} textAnchor="middle" className="fe-wl-svg__say">{t('welcome.find.word')}</text>
      </g>

      {/* Три точки «бот печатает»: видны только в середине сцены, в итоговом кадре их нет. */}
      <g className="wl-typing" style={{ '--d': '1050ms' }}>
        <rect x={40} y={130} width={62} height={34} rx={17} fill={CARD} />
        {[0, 1, 2].map((i) => <circle key={i} cx={59 + i * 12} cy={147} r={3} fill={INK} fillOpacity={0.5} />)}
      </g>

      <g className="wl-rise" style={{ '--d': '1850ms' }}>
        <Slab uid={uid} x={40} y={130} w={236} h={88} r={20} fill={CARD} />
        <rect x={58} y={148} width={112} height={8} rx={4} fill={BAR_STRONG} />
        <rect x={58} y={164} width={150} height={7} rx={3.5} fill={BAR} />
        <rect x={58} y={178} width={96} height={7} rx={3.5} fill={BAR} />
        <path d="M184 200 C 196 198, 202 188, 214 190 S 232 200, 242 186 S 254 176, 262 178" fill="none" stroke={BLUE} strokeWidth={2.25} strokeLinecap="round" />
        <circle cx={262} cy={178} r={3.5} fill={BLUE} stroke="#FFFFFF" strokeWidth={1.5} />
        <Sheen uid={uid} id="tg" x={40} y={130} w={236} h={88} r={20} delay="3550ms" />
      </g>

      <g className="wl-rise wl-rise--near" style={{ '--d': '2450ms' }}>
        <rect x={40} y={232} width={236} height={38} rx={19} fill="rgba(255, 255, 255, 0.14)" />
        <g className="wl-fade" style={{ '--d': '3150ms' }}>
          <rect x={40} y={232} width={236} height={38} rx={19} fill={`url(#wl-blue-${uid})`} />
        </g>
        <circle cx={62} cy={251} r={15} fill="none" stroke="#FFFFFF" strokeWidth={1.5} className="wl-ping" style={{ '--d': '3100ms' }} />
        <Bell x={54} y={243} width={16} height={16} color="#FFFFFF" strokeWidth={2.2} />
        <text x={80} y={255.5} className="fe-wl-svg__btn">{t('welcome.telegram.subscribe')}</text>
      </g>
    </svg>
  );
}

const C_LINE_A = 'M58 214 C 84 208, 100 186, 126 190 S 164 206, 190 180 S 232 150, 258 156 S 300 150, 336 118';
const C_LINE_B = 'M58 228 C 86 230, 104 214, 130 216 S 170 232, 196 212 S 236 196, 262 204 S 304 196, 336 172';

/** Шаг «Сравнение» (английская версия): две страны, две линии на одном графике. */
function CompareArt({ uid, t, audience }) {
  const chips = layoutChips([audience?.home || t('welcome.compare.home'), audience?.peer || t('welcome.compare.peer')]);
  const colors = [BLUE, TEAL];
  return (
    <svg viewBox="28 14 344 272" className="fe-wl-svg" aria-hidden="true" focusable="false">
      <Defs uid={uid} />
      {chips.map(({ label, w, x }, i) => (
        <g key={label} className="wl-rise" style={{ '--d': `${i * 140}ms` }}>
          <rect x={x} y={28} width={w} height={36} rx={18} fill={`url(#wl-glass-${uid})`} />
          <circle cx={x + 18} cy={46} r={6} fill={colors[i]} className="wl-pop" style={{ '--d': `${480 + i * 260}ms` }} />
          <text x={x + 31} y={50.5} className="fe-wl-svg__chip">{label}</text>
        </g>
      ))}
      <g className="wl-rise" style={{ '--d': '320ms' }}>
        <Slab uid={uid} x={40} y={86} w={320} h={184} r={22} fill={CARD} />
        <rect x={58} y={104} width={104} height={8} rx={4} fill={BAR_STRONG} />
        {[166, 196, 226].map((y) => <rect key={y} x={58} y={y} width={284} height={1} fill={INK} fillOpacity={0.07} />)}
        <clipPath id={`wl-clip-cmp-${uid}`}><rect x={52} y={110} width={292} height={130} /></clipPath>
        <g clipPath={`url(#wl-clip-cmp-${uid})`}>
          <path d={C_LINE_B} fill="none" stroke={TEAL} strokeWidth={2.75} strokeLinecap="round" />
          <rect x={52} y={110} width={292} height={130} fill={CARD} className="wl-wipe" style={{ '--d': '1900ms', '--wx': '294px' }} />
          <path d={C_LINE_A} fill="none" stroke={BLUE} strokeWidth={2.75} strokeLinecap="round" />
          <rect x={52} y={110} width={292} height={106} fill={CARD} className="wl-wipe" style={{ '--d': '1250ms', '--wx': '294px' }} />
        </g>
        <circle cx={336} cy={118} r={5} fill={BLUE} stroke="#FFFFFF" strokeWidth={2} className="wl-pop" style={{ '--d': '2150ms' }} />
        <circle cx={336} cy={172} r={5} fill={TEAL} stroke="#FFFFFF" strokeWidth={2} className="wl-pop" style={{ '--d': '2800ms' }} />
        <Sheen uid={uid} id="cmp" x={40} y={86} w={320} h={184} r={22} delay="3150ms" />
      </g>
    </svg>
  );
}

/** Шаг «Аккаунт»: звезда у показателя загорается, строка ложится в «Избранное», колокольчик включается. */
function AccountArt({ uid, t }) {
  return (
    <svg viewBox="28 14 344 272" className="fe-wl-svg" aria-hidden="true" focusable="false">
      <Defs uid={uid} />
      <g className="wl-rise" style={{ '--d': '0ms' }}>
        <Slab uid={uid} x={40} y={28} w={320} h={78} r={20} />
        <rect x={60} y={50} width={140} height={10} rx={5} fill={BAR_STRONG} />
        <rect x={60} y={70} width={92} height={8} rx={4} fill={BAR} />

        <circle cx={290} cy={67} r={18} fill={BAR} />
        <Star x={281} y={58} width={18} height={18} color={INK} strokeWidth={1.8} opacity={0.55} />
        <g className="wl-pop" style={{ '--d': '900ms' }}>
          <circle cx={290} cy={67} r={18} fill={`url(#wl-blue-${uid})`} />
          <Star x={281} y={58} width={18} height={18} color="#FFFFFF" fill="#FFFFFF" strokeWidth={1.8} />
        </g>
        <circle cx={290} cy={67} r={18} fill="none" stroke={BLUE} strokeWidth={1.5} className="wl-ping" style={{ '--d': '840ms' }} />

        <circle cx={334} cy={67} r={18} fill={BAR} />
        <Bell x={325} y={58} width={18} height={18} color={INK} strokeWidth={1.8} opacity={0.55} />
        <g className="wl-pop" style={{ '--d': '2300ms' }}>
          <circle cx={334} cy={67} r={18} fill={`url(#wl-blue-${uid})`} />
          <Bell x={325} y={58} width={18} height={18} color="#FFFFFF" strokeWidth={1.8} />
          <circle cx={346} cy={54} r={4.5} fill={GOLD} stroke="#F7F9FD" strokeWidth={1.5} />
        </g>
      </g>

      <g className="wl-rise" style={{ '--d': '240ms' }}>
        <Slab uid={uid} x={40} y={124} w={320} h={148} r={22} fill={CARD} />
        <text x={60} y={150} className="fe-wl-svg__label">{t('welcome.account.saved')}</text>

        <g className="wl-rise wl-rise--near" style={{ '--d': '1400ms' }}>
          <rect x={56} y={162} width={288} height={30} rx={10} fill={BLUE} fillOpacity={0.1} />
          <Star x={66} y={169} width={16} height={16} color={BLUE} fill={BLUE} strokeWidth={1.8} />
          <rect x={92} y={173} width={140} height={8} rx={4} fill={BAR_STRONG} />
          <rect x={300} y={173} width={30} height={8} rx={4} fill={BAR} />
        </g>
        {/* Прежние строки уступают место новой: съезжают на одну строку вниз. */}
        <g className="wl-shift" style={{ '--d': '1280ms' }}>
          {[0, 1].map((i) => (
            <g key={i}>
              <circle cx={74} cy={211 + i * 34} r={7} fill={BAR_STRONG} />
              <rect x={92} y={207 + i * 34} width={[112, 156][i]} height={8} rx={4} fill={BAR} />
              <rect x={300} y={207 + i * 34} width={30} height={8} rx={4} fill={BAR} />
            </g>
          ))}
        </g>
        <Sheen uid={uid} id="acc" x={40} y={124} w={320} h={148} r={22} delay="2900ms" />
      </g>
    </svg>
  );
}

const ART = { find: FindArt, fresh: FreshArt, telegram: TelegramArt, compare: CompareArt, account: AccountArt };

/**
 * @param {{ step: string, t: Function, audience?: { sources: string[], home: string, peer: string } | null }} props
 * `audience` — набор иностранного посетителя (lib/welcomeAudience.js); без него сцены берут подписи из словаря.
 */
export default function WelcomeArt({ step, t, audience = null }) {
  const uid = useId().replace(/:/g, '');
  const Scene = ART[step];
  if (!Scene) return null;
  return <Scene uid={uid} t={t} sources={audience?.sources} audience={audience} />;
}
