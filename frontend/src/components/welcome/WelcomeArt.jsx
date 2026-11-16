import { useId } from 'react';
import { Bell, Check, Search, Star } from 'lucide-react';

/**
 * Четыре сцены приветственного экрана: по одной мысли на шаг. Чистый SVG (вектор: на любом экране без пикселя, принцип 9),
 * движение задаёт `styles/welcome.css` классами `wl-*` и задержкой `--d`.
 *
 * Правила сцен:
 *  - настоящих чисел нет: вместо значений полосы-заготовки (на сайте статистики выдуманная цифра выглядит как ошибка данных);
 *  - прогноз — одна тонкая золотая линия до одной точки, без коридора (принцип 8);
 *  - базовый вид каждого элемента (без анимации) — итоговый кадр: при `prefers-reduced-motion` сцена стоит готовой;
 *  - сцены украшают текст и скрыты от экранного чтения (`aria-hidden`), смысл несут заголовок и абзац шага.
 */
const INK = '#1E2638';
const BLUE = '#2C4A8A';
const GOLD = '#B08A3E';
const BAR = 'rgba(30, 58, 110, 0.13)';
const BAR_STRONG = 'rgba(30, 58, 110, 0.24)';

function Defs({ uid }) {
  return (
    <defs>
      <linearGradient id={`wl-glass-${uid}`} x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="#FFFFFF" stopOpacity="0.96" />
        <stop offset="1" stopColor="#FFFFFF" stopOpacity="0.7" />
      </linearGradient>
      <linearGradient id={`wl-ink-${uid}`} x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="#2A3550" />
        <stop offset="1" stopColor="#1E2638" />
      </linearGradient>
      <linearGradient id={`wl-blue-${uid}`} x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="#2C4A8A" />
        <stop offset="1" stopColor="#1E3A6E" />
      </linearGradient>
      <linearGradient id={`wl-area-${uid}`} x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stopColor={BLUE} stopOpacity="0.2" />
        <stop offset="1" stopColor={BLUE} stopOpacity="0" />
      </linearGradient>
      <radialGradient id={`wl-shadow-${uid}`} cx="0.5" cy="0.5" r="0.5">
        <stop offset="0" stopColor={INK} stopOpacity="0.2" />
        <stop offset="0.6" stopColor={INK} stopOpacity="0.07" />
        <stop offset="1" stopColor={INK} stopOpacity="0" />
      </radialGradient>
    </defs>
  );
}

/** Стеклянная плита: мягкая тень-эллипс снизу (вместо фильтра: фильтры SVG дороги при движении), тело и блик сверху. */
function Slab({ uid, x, y, w, h, r = 18, fill }) {
  return (
    <>
      <ellipse cx={x + w / 2} cy={y + h + 5} rx={w * 0.47} ry={Math.max(9, h * 0.16)} fill={`url(#wl-shadow-${uid})`} />
      <rect x={x} y={y} width={w} height={h} rx={r} fill={fill || `url(#wl-glass-${uid})`} />
      <rect x={x + r * 0.7} y={y + 0.6} width={w - r * 1.4} height="1" rx="0.5" fill="#FFFFFF" fillOpacity="0.9" />
    </>
  );
}

const LINE = 'M58 224 C 84 222, 96 200, 120 204 S 156 228, 180 206 S 214 168, 238 176 S 268 190, 292 160';
const AREA = `${LINE} L 292 252 L 58 252 Z`;

/** Шаг «Как пользоваться»: слово в поиске, строки выдачи, график. */
function FindArt({ uid, t }) {
  const word = [...t('welcome.find.word')];
  return (
    <svg viewBox="0 0 400 300" className="fe-wl-svg" aria-hidden="true" focusable="false">
      <Defs uid={uid} />
      <g className="wl-rise" style={{ '--d': '0ms' }}>
        <Slab uid={uid} x={40} y={28} w={320} h={52} r={26} />
        <Search x={60} y={44} width={20} height={20} color={INK} strokeWidth={2} opacity={0.62} />
        <text x={92} y={60.5} className="fe-wl-svg__word">
          {word.map((ch, i) => (
            // Ключ по месту буквы: слово не меняется, пока сцена на экране.
            <tspan key={i} className="wl-type" style={{ '--d': `${320 + i * 62}ms` }}>{ch}</tspan>
          ))}
          <tspan className="wl-caret" dx="2" style={{ '--d': `${320 + word.length * 62}ms` }}>|</tspan>
        </text>
      </g>

      {[0, 1, 2].map((i) => (
        <g key={i} className="wl-rise" style={{ '--d': `${1000 + i * 90}ms` }}>
          <rect x={40} y={98 + i * 46} width={320} height={38} rx={13} fill="#FFFFFF" fillOpacity={i === 0 ? 0.92 : 0.6} />
          <circle cx={62} cy={117 + i * 46} r={8} fill={i === 0 ? BLUE : BAR_STRONG} fillOpacity={i === 0 ? 0.9 : 1} />
          <rect x={80} y={113 + i * 46} width={[132, 104, 148][i]} height={8} rx={4} fill={i === 0 ? BAR_STRONG : BAR} />
          <rect x={306} y={113 + i * 46} width={36} height={8} rx={4} fill={BAR} />
        </g>
      ))}
      <circle cx={62} cy={117} r={15} fill="none" stroke={BLUE} strokeWidth={1.5} className="wl-ping" style={{ '--d': '1560ms' }} />

      <g className="wl-rise wl-rise--far" style={{ '--d': '1900ms' }}>
        <Slab uid={uid} x={40} y={146} w={320} h={126} r={20} fill="#FBFCFE" />
        <rect x={58} y={162} width={96} height={8} rx={4} fill={BAR_STRONG} />
        <rect x={58} y={177} width={58} height={7} rx={3.5} fill={BAR} />
        <g clipPath={`url(#wl-clip-find-${uid})`}>
          <path d={AREA} fill={`url(#wl-area-${uid})`} />
          <path d={LINE} fill="none" stroke={BLUE} strokeWidth={2.5} strokeLinecap="round" />
          {/* Шторка цвета плиты уезжает вправо и открывает линию: движется только transform. */}
          <rect x={52} y={150} width={254} height={110} fill="#FBFCFE" className="wl-wipe" style={{ '--d': '2150ms', '--wx': '256px' }} />
        </g>
        <circle cx={292} cy={160} r={4.5} fill={BLUE} stroke="#FFFFFF" strokeWidth={2} className="wl-pop" style={{ '--d': '2900ms' }} />
        <clipPath id={`wl-clip-find-${uid}`}><rect x={52} y={150} width={254} height={110} /></clipPath>
      </g>
    </svg>
  );
}

const F_LINE = 'M58 226 C 82 220, 92 196, 116 202 S 150 232, 176 208 S 206 170, 230 180 S 256 196, 276 168';
const F_AREA = `${F_LINE} L 276 244 L 58 244 Z`;

/** Шаг «Свежие данные»: источники отмечены, на графике появилась новая точка, дальше тонкая золотая линия прогноза. */
function FreshArt({ uid, t }) {
  const sources = [t('welcome.fresh.source1'), t('welcome.fresh.source2'), t('welcome.fresh.source3')];
  return (
    <svg viewBox="0 0 400 300" className="fe-wl-svg" aria-hidden="true" focusable="false">
      <Defs uid={uid} />
      {sources.map((name, i) => (
        <g key={name} className="wl-rise" style={{ '--d': `${i * 90}ms` }}>
          <rect x={40 + i * 107} y={30} width={106} height={36} rx={18} fill={`url(#wl-glass-${uid})`} />
          <g className="wl-pop" style={{ '--d': `${420 + i * 260}ms` }}>
            <circle cx={58 + i * 107} cy={48} r={9} fill={BLUE} />
            <Check x={52 + i * 107} y={42} width={12} height={12} color="#FFFFFF" strokeWidth={3} />
          </g>
          <text x={72 + i * 107} y={52.5} className="fe-wl-svg__chip">{name}</text>
        </g>
      ))}

      <g className="wl-rise" style={{ '--d': '260ms' }}>
        <Slab uid={uid} x={40} y={88} w={320} h={180} r={22} fill="#FBFCFE" />
        <rect x={58} y={106} width={104} height={8} rx={4} fill={BAR_STRONG} />
        <rect x={58} y={121} width={64} height={7} rx={3.5} fill={BAR} />
        {[166, 196, 226].map((y) => <rect key={y} x={58} y={y} width={284} height={1} fill={INK} fillOpacity={0.06} />)}
        <g clipPath={`url(#wl-clip-fresh-${uid})`}>
          <path d={F_AREA} fill={`url(#wl-area-${uid})`} />
          <path d={F_LINE} fill="none" stroke={BLUE} strokeWidth={2.5} strokeLinecap="round" />
          <rect x={52} y={140} width={232} height={110} fill="#FBFCFE" className="wl-wipe" style={{ '--d': '1150ms', '--wx': '234px' }} />
        </g>
        <clipPath id={`wl-clip-fresh-${uid}`}><rect x={52} y={140} width={232} height={110} /></clipPath>

        {/* Прогноз: одна золотая линия до одной точки, без коридора. */}
        <g className="wl-fade" style={{ '--d': '2500ms' }}>
          <path d="M276 168 C 296 160, 314 158, 336 150" fill="none" stroke={GOLD} strokeWidth={2} strokeLinecap="round" />
          <circle cx={336} cy={150} r={3} fill={GOLD} />
        </g>

        <circle cx={276} cy={168} r={14} fill="none" stroke={BLUE} strokeWidth={1.5} className="wl-ping" style={{ '--d': '2050ms' }} />
        <circle cx={276} cy={168} r={5} fill={BLUE} stroke="#FFFFFF" strokeWidth={2} className="wl-pop" style={{ '--d': '1950ms' }} />

        <g className="wl-rise wl-rise--near" style={{ '--d': '2150ms' }}>
          <rect x={222} y={128} width={108} height={26} rx={13} fill={`url(#wl-ink-${uid})`} />
          <circle cx={237} cy={141} r={3} fill="#C9A24D" />
          <text x={247} y={145.5} className="fe-wl-svg__tag">{t('welcome.fresh.updated')}</text>
        </g>
      </g>
    </svg>
  );
}

/** Шаг «Telegram»: вопрос человека, ответ бота с графиком, кнопка «Присылать новые данные» включается. */
function TelegramArt({ uid, t }) {
  return (
    <svg viewBox="0 0 400 300" className="fe-wl-svg" aria-hidden="true" focusable="false">
      <Defs uid={uid} />
      <g className="wl-rise" style={{ '--d': '0ms' }}>
        <circle cx={58} cy={44} r={18} fill={`url(#wl-ink-${uid})`} />
        <path d="M51.5 53V40.5Q51.5 34 58.5 34H65V38.5H59Q56.5 38.5 56.5 41.5V42H63.5V46.5H56.5V53Z" fill="#F2F5FA" />
        <rect x={62} y={48.5} width={3.4} height={4.5} fill="#C9A24D" />
        <text x={86} y={42} className="fe-wl-svg__name">Forecast Economy</text>
        <rect x={86} y={50} width={44} height={6} rx={3} fill={BAR} />
      </g>

      <g className="wl-rise wl-rise--near" style={{ '--d': '380ms' }}>
        <rect x={232} y={78} width={128} height={38} rx={19} fill={`url(#wl-ink-${uid})`} />
        <text x={296} y={102} textAnchor="middle" className="fe-wl-svg__say">{t('welcome.find.word')}</text>
      </g>

      {/* Три точки «бот печатает»: видны только в середине сцены, в итоговом кадре их нет. */}
      <g className="wl-typing" style={{ '--d': '820ms' }}>
        <rect x={40} y={130} width={62} height={34} rx={17} fill="#FFFFFF" fillOpacity={0.9} />
        {[0, 1, 2].map((i) => <circle key={i} cx={59 + i * 12} cy={147} r={3} fill={INK} fillOpacity={0.45} />)}
      </g>

      <g className="wl-rise" style={{ '--d': '1500ms' }}>
        <Slab uid={uid} x={40} y={130} w={236} h={88} r={20} fill="#FBFCFE" />
        <rect x={58} y={148} width={112} height={8} rx={4} fill={BAR_STRONG} />
        <rect x={58} y={164} width={150} height={7} rx={3.5} fill={BAR} />
        <rect x={58} y={178} width={96} height={7} rx={3.5} fill={BAR} />
        <path d="M184 200 C 196 198, 202 188, 214 190 S 232 200, 242 186 S 254 176, 262 178" fill="none" stroke={BLUE} strokeWidth={2.25} strokeLinecap="round" />
        <circle cx={262} cy={178} r={3.5} fill={BLUE} stroke="#FFFFFF" strokeWidth={1.5} />
      </g>

      <g className="wl-rise wl-rise--near" style={{ '--d': '2050ms' }}>
        <rect x={40} y={232} width={236} height={38} rx={19} fill="#FFFFFF" fillOpacity={0.9} />
        <g className="wl-fade" style={{ '--d': '2750ms' }}>
          <rect x={40} y={232} width={236} height={38} rx={19} fill={`url(#wl-blue-${uid})`} />
        </g>
        <circle cx={62} cy={251} r={15} fill="none" stroke="#FFFFFF" strokeWidth={1.5} className="wl-ping" style={{ '--d': '2700ms' }} />
        <Bell x={54} y={243} width={16} height={16} color="#FFFFFF" strokeWidth={2.2} />
        <text x={80} y={255.5} className="fe-wl-svg__btn">{t('welcome.telegram.subscribe')}</text>
      </g>
    </svg>
  );
}

/** Шаг «Аккаунт»: звезда у показателя загорается, строка ложится в «Избранное», колокольчик включается. */
function AccountArt({ uid, t }) {
  return (
    <svg viewBox="0 0 400 300" className="fe-wl-svg" aria-hidden="true" focusable="false">
      <Defs uid={uid} />
      <g className="wl-rise" style={{ '--d': '0ms' }}>
        <Slab uid={uid} x={40} y={28} w={320} h={78} r={20} />
        <rect x={60} y={50} width={140} height={10} rx={5} fill={BAR_STRONG} />
        <rect x={60} y={70} width={92} height={8} rx={4} fill={BAR} />

        <circle cx={290} cy={67} r={18} fill="#FFFFFF" fillOpacity={0.9} />
        <Star x={281} y={58} width={18} height={18} color={INK} strokeWidth={1.8} opacity={0.5} />
        <g className="wl-pop" style={{ '--d': '760ms' }}>
          <circle cx={290} cy={67} r={18} fill={`url(#wl-blue-${uid})`} />
          <Star x={281} y={58} width={18} height={18} color="#FFFFFF" fill="#FFFFFF" strokeWidth={1.8} />
        </g>
        <circle cx={290} cy={67} r={18} fill="none" stroke={BLUE} strokeWidth={1.5} className="wl-ping" style={{ '--d': '700ms' }} />

        <circle cx={334} cy={67} r={18} fill="#FFFFFF" fillOpacity={0.9} />
        <Bell x={325} y={58} width={18} height={18} color={INK} strokeWidth={1.8} opacity={0.5} />
        <g className="wl-pop" style={{ '--d': '1900ms' }}>
          <circle cx={334} cy={67} r={18} fill={`url(#wl-blue-${uid})`} />
          <Bell x={325} y={58} width={18} height={18} color="#FFFFFF" strokeWidth={1.8} />
          <circle cx={346} cy={54} r={4} fill="#C9A24D" stroke="#FBFCFE" strokeWidth={1.5} />
        </g>
      </g>

      <g className="wl-rise" style={{ '--d': '200ms' }}>
        <Slab uid={uid} x={40} y={124} w={320} h={148} r={22} fill="#FBFCFE" />
        <text x={60} y={150} className="fe-wl-svg__label">{t('welcome.account.saved')}</text>

        <g className="wl-rise wl-rise--near" style={{ '--d': '1150ms' }}>
          <rect x={56} y={162} width={288} height={30} rx={10} fill={BLUE} fillOpacity={0.08} />
          <Star x={66} y={169} width={16} height={16} color={BLUE} fill={BLUE} strokeWidth={1.8} />
          <rect x={92} y={173} width={140} height={8} rx={4} fill={BAR_STRONG} />
          <rect x={300} y={173} width={30} height={8} rx={4} fill={BAR} />
        </g>
        {/* Прежние строки уступают место новой: съезжают на одну строку вниз. */}
        <g className="wl-shift" style={{ '--d': '1050ms' }}>
          {[0, 1].map((i) => (
            <g key={i}>
              <circle cx={74} cy={211 + i * 34} r={7} fill={BAR_STRONG} />
              <rect x={92} y={207 + i * 34} width={[112, 156][i]} height={8} rx={4} fill={BAR} />
              <rect x={300} y={207 + i * 34} width={30} height={8} rx={4} fill={BAR} />
            </g>
          ))}
        </g>
      </g>
    </svg>
  );
}

const ART = { find: FindArt, fresh: FreshArt, telegram: TelegramArt, account: AccountArt };

export default function WelcomeArt({ step, t }) {
  const uid = useId().replace(/:/g, '');
  const Scene = ART[step] || FindArt;
  return <Scene uid={uid} t={t} />;
}
