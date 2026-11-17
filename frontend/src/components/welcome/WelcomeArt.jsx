import { useId } from 'react';
import { Bell, Check, ChevronRight, Search, Star } from 'lucide-react';
import { layoutChips } from '../../lib/welcome';
import { fieldBounds, linePath, areaPath, place, yearTicks } from '../../lib/welcomeChart';

/**
 * Сцены приветственного экрана: по одной мысли на шаг. Чистый SVG (вектор: на любом экране без пикселя, принцип 9),
 * движение задаёт `styles/welcome.css` классами `wl-*` и задержкой `--d`.
 *
 * С 17.11.2026 (слова владельца: «там заглушки как будто стоят, а нужно, чтобы прям прописано было, видно») сцены
 * показывают настоящее, а не серые полоски: название показателя, страну, последнее значение, месяц, источник и саму
 * линию — из ряда сайта (`facts`, собирает WelcomeScreen из `GET /world/compare/series`). Если данные не пришли,
 * сцена остаётся с названиями и условной линией, но без единого числа: выдуманных значений нет.
 *
 * Правила сцен:
 *  - числа только настоящие; прогноза в сценах нет (у этого ряда его может не быть, а рисовать выдуманный нельзя);
 *  - базовый вид каждого элемента (без анимации) — итоговый кадр: при `prefers-reduced-motion` сцена стоит готовой;
 *  - маленький знак сайта — стеклянная F значка сайта (`favicon-512.png`), плоской «F.» нет нигде;
 *  - в конце по главной плите один раз проходит блик; после этого живёт только зелёная точка «проверяем каждый день»;
 *  - сцены украшают текст и скрыты от экранного чтения (`aria-hidden`), смысл несут заголовок и абзац шага.
 */
const INK = '#16213D';
const MUTE = '#5F6B80';
const BLUE = '#2C4A8A';
const TEAL = '#238F9B';
const GOLD = '#C9A24D';
const LIVE = '#2E9C6A';
const GHOST = 'rgba(255, 255, 255, 0.1)';
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
        <stop offset="0" stopColor={BLUE} stopOpacity="0.24" />
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
      <radialGradient id={`wl-contact-${uid}`} cx="0.5" cy="0.5" r="0.5">
        <stop offset="0" stopColor="#040816" stopOpacity="0.55" />
        <stop offset="1" stopColor="#040816" stopOpacity="0" />
      </radialGradient>
    </defs>
  );
}

/** Стеклянная плита: холодное свечение, узкая тень-касание под нижней кромкой (плита стоит, а не висит), тело и блик сверху. */
function Slab({ uid, x, y, w, h, r = 18, fill }) {
  return (
    <>
      <ellipse cx={x + w / 2} cy={y + h + 2} rx={w * 0.56} ry={Math.max(16, h * 0.34)} fill={`url(#wl-glow-${uid})`} />
      <ellipse cx={x + w / 2} cy={y + h + 1} rx={w * 0.44} ry={5} fill={`url(#wl-contact-${uid})`} />
      <rect x={x} y={y} width={w} height={h} rx={r} fill={fill || `url(#wl-glass-${uid})`} />
      <rect x={x + r} y={y + 0.6} width={w - r * 2} height="1" rx="0.5" fill="#FFFFFF" />
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

/** Условная линия на случай, когда ряд не пришёл: форма без чисел (в полях 0…1). */
const GENERIC = [0.62, 0.6, 0.5, 0.52, 0.66, 0.58, 0.44, 0.34, 0.38, 0.46, 0.3, 0.22];
const GENERIC_B = [0.8, 0.82, 0.74, 0.76, 0.84, 0.78, 0.7, 0.66, 0.7, 0.72, 0.62, 0.56];

/**
 * Линия в рамке `box` ({ x, y, w, h }): настоящий ряд (`series`, при сравнении вместе с `other` в общих границах)
 * или условная форма, если ряда нет. Возвращает пути, место последней точки и отметки лет.
 */
function plot(series, box, other = null, generic = GENERIC) {
  if (series && series.length) {
    const bounds = fieldBounds(series, other && other.length ? other : null);
    const field = { w: box.w, h: box.h, top: 5, bottom: 5 };
    const last = place(series[series.length - 1], bounds, field);
    return {
      line: linePath(series, bounds, field),
      area: areaPath(series, bounds, field),
      end: { x: box.x + last.x, y: box.y + last.y },
      ticks: yearTicks(bounds, 4).map((tick) => ({ year: tick.year, x: box.x + tick.fraction * box.w })),
    };
  }
  const pts = generic.map((v, i) => ({ x: (i / (generic.length - 1)) * box.w, y: 5 + v * (box.h - 10) }));
  const line = pts.map((p, i) => `${i ? 'L' : 'M'}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');
  const end = pts[pts.length - 1];
  return { line, area: `${line} L${box.w} ${box.h} L0 ${box.h} Z`, end: { x: box.x + end.x, y: box.y + end.y }, ticks: [] };
}

/** Линия с проходом слева направо: шторка цвета плиты уезжает вправо, движется только transform. */
function Line({ uid, id, box, shape, color = BLUE, area = true, delay, width = 2.5 }) {
  return (
    <>
      <clipPath id={`wl-plot-${id}-${uid}`}><rect x={box.x - 3} y={box.y - 3} width={box.w + 6} height={box.h + 6} /></clipPath>
      <g clipPath={`url(#wl-plot-${id}-${uid})`}>
        <g transform={`translate(${box.x} ${box.y})`}>
          {area ? <path d={shape.area} fill={`url(#wl-area-${uid})`} /> : null}
          <path d={shape.line} fill="none" stroke={color} strokeWidth={width} strokeLinejoin="round" strokeLinecap="round" />
        </g>
        <rect
          x={box.x - 3} y={box.y - 3} width={box.w + 6} height={box.h + 6} fill={CARD}
          className="wl-wipe" style={{ '--d': delay, '--wx': `${box.w + 8}px` }}
        />
      </g>
    </>
  );
}

function Years({ ticks, y }) {
  return ticks.map((tick) => <text key={tick.year} x={tick.x} y={y} textAnchor="middle" className="fe-wl-svg__tick">{tick.year}</text>);
}

/** Шаг «Как пользоваться»: слово в поиске, две строки выдачи с настоящими значениями, карточка показателя с линией. */
function FindArt({ uid, t, facts }) {
  const word = [...t('welcome.find.word')];
  const box = { x: 196, y: 204, w: 146, h: 50 };
  const shape = plot(facts.series, box);
  const rows = [
    { country: facts.home, value: facts.value, color: BLUE, strong: true },
    { country: facts.peer, value: facts.peerValue, color: TEAL, strong: false },
  ];
  return (
    <svg viewBox="28 14 344 272" className="fe-wl-svg" aria-hidden="true" focusable="false">
      <Defs uid={uid} />
      <g className="wl-rise" style={{ '--d': '0ms' }}>
        <Slab uid={uid} x={40} y={26} w={320} h={50} r={25} />
        <Search x={60} y={41} width={20} height={20} color={INK} strokeWidth={2.2} opacity={0.7} />
        <text x={92} y={57.5} className="fe-wl-svg__word">
          {word.map((ch, i) => (
            // Ключ по месту буквы: слово не меняется, пока сцена на экране.
            <tspan key={i} className="wl-type" style={{ '--d': `${420 + i * 58}ms` }}>{ch}</tspan>
          ))}
          <tspan className="wl-caret" dx="2" style={{ '--d': `${420 + word.length * 58}ms` }}>|</tspan>
        </text>
      </g>

      {rows.map((row, i) => (
        <g key={row.country} className="wl-rise" style={{ '--d': `${1250 + i * 110}ms` }}>
          <rect x={40} y={88 + i * 46} width={320} height={40} rx={13} fill={row.strong ? CARD : GHOST} />
          <circle cx={61} cy={108 + i * 46} r={6} fill={row.color} />
          <text x={78} y={105 + i * 46} className={row.strong ? 'fe-wl-svg__row' : 'fe-wl-svg__row fe-wl-svg__row--ghost'}>{t('welcome.scene.indicator')}</text>
          <text x={78} y={118.5 + i * 46} className={row.strong ? 'fe-wl-svg__sub' : 'fe-wl-svg__sub fe-wl-svg__sub--ghost'}>{row.country}</text>
          {row.value ? (
            <text x={344} y={113 + i * 46} textAnchor="end" className={row.strong ? 'fe-wl-svg__num' : 'fe-wl-svg__num fe-wl-svg__num--ghost'}>{row.value}</text>
          ) : <ChevronRight x={328} y={100 + i * 46} width={16} height={16} color={row.strong ? MUTE : '#B8C4DD'} strokeWidth={2} />}
        </g>
      ))}
      <circle cx={61} cy={108} r={14} fill="none" stroke="#9DB8F5" strokeWidth={1.5} className="wl-ping" style={{ '--d': '1850ms' }} />

      <g className="wl-rise wl-rise--far" style={{ '--d': '2150ms' }}>
        <Slab uid={uid} x={40} y={186} w={320} h={86} r={20} fill={CARD} />
        <text x={58} y={207} className="fe-wl-svg__row">{t('welcome.scene.indicator')}</text>
        <text x={58} y={236} className="fe-wl-svg__big">{facts.value || facts.home}</text>
        <text x={58} y={254} className="fe-wl-svg__sub">{facts.caption || t('welcome.scene.official')}</text>
        <Line uid={uid} id="find" box={box} shape={shape} delay="2500ms" />
        <circle cx={shape.end.x} cy={shape.end.y} r={11} fill="none" stroke={BLUE} strokeWidth={1.5} className="wl-ping" style={{ '--d': '3400ms' }} />
        <circle cx={shape.end.x} cy={shape.end.y} r={4.5} fill={BLUE} stroke="#FFFFFF" strokeWidth={2} className="wl-pop" style={{ '--d': '3350ms' }} />
        <Sheen uid={uid} id="find" x={40} y={186} w={320} h={86} r={20} delay="3700ms" />
      </g>
    </svg>
  );
}

/** Шаг «Свежие данные»: источники отмечены, карточка показателя с настоящей линией, на ней новое значение с месяцем. */
function FreshArt({ uid, t, facts, sources }) {
  const names = sources?.length ? sources : [t('welcome.fresh.source1'), t('welcome.fresh.source2'), t('welcome.fresh.source3')];
  const chips = layoutChips(names);
  const box = { x: 58, y: 166, w: 284, h: 72 };
  const shape = plot(facts.series, box);
  const daily = t('welcome.scene.daily');
  const dailyW = Math.round(28 + daily.length * 5.2);
  // Подпись новой точки короткая (месяц): длинная закрывала бы саму линию.
  const tag = facts.month || t('welcome.scene.newValue');
  const tagW = Math.round(30 + tag.length * 5.6);
  // Подпись новой точки стоит над ней и не выходит за плиту; если точка под самым верхом поля, подпись уходит под неё.
  const tagX = Math.max(52, Math.min(shape.end.x - tagW + 12, 348 - tagW));
  const tagY = shape.end.y - 36 < 150 ? shape.end.y + 12 : shape.end.y - 36;
  return (
    <svg viewBox="28 14 344 272" className="fe-wl-svg" aria-hidden="true" focusable="false">
      <Defs uid={uid} />
      {chips.map(({ label, w, x }, i) => (
        <g key={label} className="wl-rise" style={{ '--d': `${i * 110}ms` }}>
          <rect x={x} y={26} width={w} height={36} rx={18} fill={`url(#wl-glass-${uid})`} />
          <g className="wl-pop" style={{ '--d': `${520 + i * 300}ms` }}>
            <circle cx={x + 18} cy={44} r={9} fill={BLUE} />
            <Check x={x + 12} y={38} width={12} height={12} color="#FFFFFF" strokeWidth={3} />
          </g>
          <text x={x + 33} y={48.5} className="fe-wl-svg__chip">{label}</text>
        </g>
      ))}

      <g className="wl-rise" style={{ '--d': '320ms' }}>
        <Slab uid={uid} x={40} y={78} w={320} h={194} r={22} fill={CARD} />
        <text x={58} y={102} className="fe-wl-svg__row">{t('welcome.scene.indicator')}</text>
        <text x={58} y={132} className="fe-wl-svg__big">{facts.value || facts.home}</text>
        <text x={58} y={149} className="fe-wl-svg__sub">{facts.caption ? `${facts.home}, ${facts.caption}` : t('welcome.scene.official')}</text>

        {/* «Проверяем каждый день»: зелёная точка живёт после конца сцены. */}
        <g className="wl-fade" style={{ '--d': '900ms' }}>
          <rect x={342 - dailyW} y={90} width={dailyW} height={22} rx={11} fill="rgba(46, 156, 106, 0.12)" />
          <circle cx={342 - dailyW + 12} cy={101} r={3.5} fill={LIVE} />
          <circle cx={342 - dailyW + 12} cy={101} r={3.5} fill="none" stroke={LIVE} strokeWidth={1.2} className="wl-live" />
          <text x={342 - dailyW + 21} y={104.6} className="fe-wl-svg__live">{daily}</text>
        </g>

        {[box.y + 18, box.y + 42, box.y + 66].map((y) => <rect key={y} x={box.x} y={y} width={box.w} height={1} fill={INK} fillOpacity={0.06} />)}
        <Line uid={uid} id="fresh" box={box} shape={shape} delay="1450ms" />
        <Years ticks={shape.ticks} y={258} />

        <circle cx={shape.end.x} cy={shape.end.y} r={13} fill="none" stroke={GOLD} strokeWidth={1.5} className="wl-ping" style={{ '--d': '2500ms' }} />
        <g className="wl-pop" style={{ '--d': '2420ms' }}>
          <circle cx={shape.end.x} cy={shape.end.y} r={7} fill="#FFFFFF" stroke={GOLD} strokeWidth={1.5} />
          <circle cx={shape.end.x} cy={shape.end.y} r={3.6} fill={BLUE} />
        </g>
        <g className="wl-rise wl-rise--near" style={{ '--d': '2650ms' }}>
          <rect x={tagX} y={tagY} width={tagW} height={24} rx={12} fill={INK} />
          <circle cx={tagX + 13} cy={tagY + 12} r={3} fill={GOLD} />
          <text x={tagX + 22} y={tagY + 16} className="fe-wl-svg__tag">{tag}</text>
        </g>
        <Sheen uid={uid} id="fresh" x={40} y={78} w={320} h={194} r={22} delay="3450ms" />
      </g>
    </svg>
  );
}

/** Знак сайта в сцене: стеклянная F значка сайта, скруглённый квадрат. */
function SiteMark({ uid, x, y, size }) {
  return (
    <>
      <clipPath id={`wl-mark-${uid}`}><rect x={x} y={y} width={size} height={size} rx={size * 0.26} /></clipPath>
      <image href="/favicon-512.png" x={x} y={y} width={size} height={size} clipPath={`url(#wl-mark-${uid})`} preserveAspectRatio="xMidYMid slice" />
    </>
  );
}

/** Шаг «Telegram»: вопрос человека, ответ бота настоящей фразой и линией, кнопка «Присылать новые данные» включается. */
function TelegramArt({ uid, t, facts }) {
  const box = { x: 58, y: 180, w: 216, h: 34 };
  const recent = facts.series.length > 40 ? facts.series.slice(-37) : facts.series;
  const shape = plot(recent, box);
  return (
    <svg viewBox="28 14 344 272" className="fe-wl-svg" aria-hidden="true" focusable="false">
      <Defs uid={uid} />
      <g className="wl-rise" style={{ '--d': '0ms' }}>
        <SiteMark uid={uid} x={40} y={24} size={38} />
        <text x={88} y={40} className="fe-wl-svg__name">Forecast Economy</text>
        <text x={88} y={54.5} className="fe-wl-svg__role">{t('welcome.scene.bot')}</text>
      </g>

      <g className="wl-rise wl-rise--near" style={{ '--d': '480ms' }}>
        <rect x={228} y={74} width={132} height={36} rx={18} fill={`url(#wl-blue-${uid})`} />
        <text x={294} y={97} textAnchor="middle" className="fe-wl-svg__say">{t('welcome.find.word')}</text>
      </g>

      {/* Три точки «бот печатает»: видны только в середине сцены, в итоговом кадре их нет. */}
      <g className="wl-typing" style={{ '--d': '1050ms' }}>
        <rect x={40} y={122} width={62} height={34} rx={17} fill={CARD} />
        {[0, 1, 2].map((i) => <circle key={i} cx={59 + i * 12} cy={139} r={3} fill={INK} fillOpacity={0.5} />)}
      </g>

      <g className="wl-rise" style={{ '--d': '1850ms' }}>
        <Slab uid={uid} x={40} y={122} w={252} h={104} r={20} fill={CARD} />
        <text x={58} y={146} className="fe-wl-svg__answer">{facts.answer || t('welcome.scene.answerEmpty')}</text>
        {facts.caption ? <text x={58} y={162} className="fe-wl-svg__sub">{facts.caption}</text> : null}
        <Line uid={uid} id="tg" box={box} shape={shape} delay="2150ms" width={2.25} />
        <circle cx={shape.end.x} cy={shape.end.y} r={3.5} fill={BLUE} stroke="#FFFFFF" strokeWidth={1.5} className="wl-pop" style={{ '--d': '3000ms' }} />
        <Sheen uid={uid} id="tg" x={40} y={122} w={252} h={104} r={20} delay="3650ms" />
      </g>

      <g className="wl-rise wl-rise--near" style={{ '--d': '2550ms' }}>
        <rect x={40} y={236} width={252} height={36} rx={18} fill="rgba(255, 255, 255, 0.14)" />
        <g className="wl-fade" style={{ '--d': '3250ms' }}>
          <rect x={40} y={236} width={252} height={36} rx={18} fill={`url(#wl-blue-${uid})`} />
        </g>
        <circle cx={62} cy={254} r={14} fill="none" stroke="#FFFFFF" strokeWidth={1.5} className="wl-ping" style={{ '--d': '3200ms' }} />
        <Bell x={54} y={246} width={16} height={16} color="#FFFFFF" strokeWidth={2.2} />
        <text x={80} y={258.5} className="fe-wl-svg__btn">{t('welcome.telegram.subscribe')}</text>
      </g>
    </svg>
  );
}

/** Шаг «Сравнение» (английская версия): две страны с настоящими значениями, две настоящие линии на одном поле. */
function CompareArt({ uid, t, facts }) {
  const labels = [
    facts.value ? `${facts.home} ${facts.value}` : facts.home,
    facts.peerValue ? `${facts.peer} ${facts.peerValue}` : facts.peer,
  ];
  const chips = layoutChips(labels);
  const colors = [BLUE, TEAL];
  const box = { x: 58, y: 126, w: 284, h: 112 };
  const both = facts.series.length && facts.peerSeries.length;
  const a = plot(facts.series, box, both ? facts.peerSeries : null);
  const b = plot(both ? facts.peerSeries : [], box, both ? facts.series : null, GENERIC_B);
  return (
    <svg viewBox="28 14 344 272" className="fe-wl-svg" aria-hidden="true" focusable="false">
      <Defs uid={uid} />
      {chips.map(({ label, w, x }, i) => (
        <g key={label} className="wl-rise" style={{ '--d': `${i * 140}ms` }}>
          <rect x={x} y={26} width={w} height={36} rx={18} fill={`url(#wl-glass-${uid})`} />
          <circle cx={x + 18} cy={44} r={6} fill={colors[i]} className="wl-pop" style={{ '--d': `${480 + i * 260}ms` }} />
          <text x={x + 31} y={48.5} className="fe-wl-svg__chip">{label}</text>
        </g>
      ))}
      <g className="wl-rise" style={{ '--d': '320ms' }}>
        <Slab uid={uid} x={40} y={78} w={320} h={194} r={22} fill={CARD} />
        <text x={58} y={102} className="fe-wl-svg__row">{t('welcome.scene.indicator')}</text>
        {facts.month ? <text x={342} y={102} textAnchor="end" className="fe-wl-svg__sub">{facts.month}</text> : null}
        {[box.y + 28, box.y + 56, box.y + 84].map((y) => <rect key={y} x={box.x} y={y} width={box.w} height={1} fill={INK} fillOpacity={0.06} />)}
        <Line uid={uid} id="cmp-b" box={box} shape={b} color={TEAL} area={false} delay="1950ms" />
        <Line uid={uid} id="cmp-a" box={box} shape={a} color={BLUE} area={false} delay="1250ms" />
        <Years ticks={a.ticks} y={258} />
        <circle cx={a.end.x} cy={a.end.y} r={4.5} fill={BLUE} stroke="#FFFFFF" strokeWidth={2} className="wl-pop" style={{ '--d': '2250ms' }} />
        <circle cx={b.end.x} cy={b.end.y} r={4.5} fill={TEAL} stroke="#FFFFFF" strokeWidth={2} className="wl-pop" style={{ '--d': '2950ms' }} />
        <Sheen uid={uid} id="cmp" x={40} y={78} w={320} h={194} r={22} delay="3300ms" />
      </g>
    </svg>
  );
}

/** Шаг «Аккаунт»: звезда у показателя загорается, он ложится первой строкой в «Избранное», колокольчик включается. */
function AccountArt({ uid, t, facts }) {
  const saved = [t('welcome.scene.saved1'), t('welcome.scene.saved2')];
  return (
    <svg viewBox="28 14 344 272" className="fe-wl-svg" aria-hidden="true" focusable="false">
      <Defs uid={uid} />
      <g className="wl-rise" style={{ '--d': '0ms' }}>
        <Slab uid={uid} x={40} y={26} w={320} h={76} r={20} />
        <text x={60} y={56} className="fe-wl-svg__head">{t('welcome.scene.indicator')}</text>
        <text x={60} y={76} className="fe-wl-svg__sub fe-wl-svg__sub--lg">{facts.value ? `${facts.home}, ${facts.value}` : facts.home}</text>

        <circle cx={290} cy={64} r={18} fill="rgba(30, 58, 110, 0.1)" />
        <Star x={281} y={55} width={18} height={18} color={INK} strokeWidth={1.8} opacity={0.55} />
        <g className="wl-pop" style={{ '--d': '900ms' }}>
          <circle cx={290} cy={64} r={18} fill={`url(#wl-blue-${uid})`} />
          <Star x={281} y={55} width={18} height={18} color="#FFFFFF" fill="#FFFFFF" strokeWidth={1.8} />
        </g>
        <circle cx={290} cy={64} r={18} fill="none" stroke={BLUE} strokeWidth={1.5} className="wl-ping" style={{ '--d': '840ms' }} />

        <circle cx={334} cy={64} r={18} fill="rgba(30, 58, 110, 0.1)" />
        <Bell x={325} y={55} width={18} height={18} color={INK} strokeWidth={1.8} opacity={0.55} />
        <g className="wl-pop" style={{ '--d': '2300ms' }}>
          <circle cx={334} cy={64} r={18} fill={`url(#wl-blue-${uid})`} />
          <Bell x={325} y={55} width={18} height={18} color="#FFFFFF" strokeWidth={1.8} />
          <circle cx={346} cy={51} r={4.5} fill={GOLD} stroke="#F7F9FD" strokeWidth={1.5} />
        </g>
      </g>

      <g className="wl-rise" style={{ '--d': '240ms' }}>
        <Slab uid={uid} x={40} y={118} w={320} h={154} r={22} fill={CARD} />
        <text x={60} y={144} className="fe-wl-svg__label">{t('welcome.account.saved')}</text>

        <g className="wl-rise wl-rise--near" style={{ '--d': '1400ms' }}>
          <rect x={54} y={156} width={292} height={32} rx={11} fill={BLUE} fillOpacity={0.1} />
          <Star x={64} y={164} width={16} height={16} color={BLUE} fill={BLUE} strokeWidth={1.8} />
          <text x={90} y={176.5} className="fe-wl-svg__row">{t('welcome.scene.indicator')}, {facts.home}</text>
          {facts.value ? <text x={336} y={176.5} textAnchor="end" className="fe-wl-svg__num">{facts.value}</text> : null}
        </g>
        {/* Прежние строки уступают место новой: съезжают на одну строку вниз. */}
        <g className="wl-shift" style={{ '--d': '1280ms' }}>
          {saved.map((label, i) => (
            <g key={label}>
              <Star x={64} y={200 + i * 34} width={16} height={16} color="#9AA6BC" strokeWidth={1.8} />
              <text x={90} y={212.5 + i * 34} className="fe-wl-svg__row fe-wl-svg__row--quiet">{label}</text>
              <ChevronRight x={322} y={200 + i * 34} width={16} height={16} color="#B3BDCF" strokeWidth={2} />
            </g>
          ))}
        </g>
        <Sheen uid={uid} id="acc" x={40} y={118} w={320} h={154} r={22} delay="2900ms" />
      </g>
    </svg>
  );
}

const ART = { find: FindArt, fresh: FreshArt, telegram: TelegramArt, compare: CompareArt, account: AccountArt };
const NO_FACTS = Object.freeze({ series: [], peerSeries: [], home: '', peer: '', value: '', peerValue: '', month: '', caption: '', answer: '' });

/**
 * @param {{ step: string, t: Function, audience?: { sources: string[] } | null, facts?: object }} props
 * `facts` — настоящее для сцен: ряды, названия стран, последнее значение, месяц, подпись «месяц, источник», фраза бота.
 * `audience` — набор иностранного посетителя (lib/welcomeAudience.js): ведомства его страны.
 */
export default function WelcomeArt({ step, t, audience = null, facts = NO_FACTS }) {
  const uid = useId().replace(/:/g, '');
  const Scene = ART[step];
  if (!Scene) return null;
  return <Scene uid={uid} t={t} sources={audience?.sources} facts={facts} />;
}
