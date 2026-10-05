/**
 * Флаги стран векторной графикой (K2.8): вместо эмодзи, которые на Windows и в части браузеров
 * превращаются в две буквы кода. Поле 60×40; рисуется внутри стеклянной «капли» (CountryFlag, prop glass).
 * Это упрощённые флаги: без гербов и надписей там, где герб мелкий и сложный; цвета и деления — по
 * официальному описанию. Для кода, которого здесь нет, CountryFlag покажет прежний эмодзи.
 * Каждая запись: [разметка SVG-внутренности, цвет свечения под каплей].
 */
const W = 60;
const H = 40;
const rect = (x, y, w, h, f) => `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="${f}"/>`;
const circ = (cx, cy, r, f, extra = '') => `<circle cx="${cx}" cy="${cy}" r="${r}" fill="${f}"${extra}/>`;
const poly = (pts, f, extra = '') => `<polygon points="${pts}" fill="${f}"${extra}/>`;
const num = (v) => Math.round(v * 100) / 100;

/** Полосы равной ширины сверху вниз (с запасом 0,25, чтобы между полосами не было светлых швов). */
const hs = (...cols) => cols.map((c, i) => rect(0, num((i * H) / cols.length), W, num(H / cols.length + 0.25), c)).join('');
const vs = (...cols) => cols.map((c, i) => rect(num((i * W) / cols.length), 0, num(W / cols.length + 0.25), H, c)).join('');
/** Горизонтальные полосы с весами: [[цвет, вес], …]. */
const hw = (list) => {
  const total = list.reduce((s, [, w]) => s + w, 0);
  let y = 0;
  return list.map(([c, w]) => {
    const h = (H * w) / total;
    const out = rect(0, num(y), W, num(h + 0.25), c);
    y += h;
    return out;
  }).join('');
};

/** Звезда: n лучей, радиус R, внутренний радиус R*ratio. */
const star = (cx, cy, R, f, n = 5, rot = -90, ratio = 0.382, extra = '') => {
  const pts = [];
  for (let i = 0; i < n * 2; i += 1) {
    const a = ((rot + (i * 180) / n) * Math.PI) / 180;
    const rr = i % 2 === 0 ? R : R * ratio;
    pts.push(`${num(cx + rr * Math.cos(a))},${num(cy + rr * Math.sin(a))}`);
  }
  return poly(pts.join(' '), f, extra);
};
/** Пентаграмма линией (Марокко). */
const pentagram = (cx, cy, R, stroke, width) => {
  const p = [0, 2, 4, 1, 3].map((i) => {
    const a = ((-90 + i * 72) * Math.PI) / 180;
    return `${num(cx + R * Math.cos(a))},${num(cy + R * Math.sin(a))}`;
  });
  return `<polygon points="${p.join(' ')}" fill="none" stroke="${stroke}" stroke-width="${width}" stroke-linejoin="round"/>`;
};
const crescent = (cx, cy, r, shift, color, bg, rIn = r * 0.82) => circ(cx, cy, r, color) + circ(cx + shift, cy, rIn, bg);
const nordic = (bg, x, y, cross, inner) => {
  // x, y — центр вертикальной и горизонтальной перекладин; cross = [ширина, цвет]; inner = [ширина, цвет] (необязательно).
  const [cw, cc] = cross;
  let out = rect(0, 0, W, H, bg) + rect(num(x - cw / 2), 0, cw, H, cc) + rect(0, num(y - cw / 2), W, cw, cc);
  if (inner) {
    const [iw, ic] = inner;
    out += rect(num(x - iw / 2), 0, iw, H, ic) + rect(0, num(y - iw / 2), W, iw, ic);
  }
  return out;
};

const unionJack = [
  rect(0, 0, W, H, '#012169'),
  '<path d="M0 0L60 40M60 0L0 40" stroke="#fff" stroke-width="8"/>',
  '<path d="M0 0L60 40M60 0L0 40" stroke="#C8102E" stroke-width="3"/>',
  rect(24, 0, 12, H, '#fff'), rect(0, 14, W, 12, '#fff'),
  rect(26, 0, 8, H, '#C8102E'), rect(0, 16, W, 8, '#C8102E'),
].join('');

const usStripes = Array.from({ length: 13 }, (_, i) => rect(0, num((i * H) / 13), W, num(H / 13 + 0.2), i % 2 === 0 ? '#B22234' : '#fff')).join('');
const usStars = Array.from({ length: 20 }, (_, k) => circ(num(3.2 + (k % 5) * 4.9), num(3.4 + Math.floor(k / 5) * 4.9), 0.95, '#fff')).join('');

const chakra = (() => {
  let out = circ(30, 20, 5, 'none', ' stroke="#000080" stroke-width="0.9"') + circ(30, 20, 1, '#000080');
  for (let i = 0; i < 12; i += 1) {
    const a = (i * Math.PI) / 6;
    out += `<path d="M${num(30 + Math.cos(a))} ${num(20 + Math.sin(a))}L${num(30 + 5 * Math.cos(a))} ${num(20 + 5 * Math.sin(a))}" stroke="#000080" stroke-width="0.5"/>`;
  }
  return out;
})();

const kr = (() => {
  const bars = (cx, cy, rot, broken) => {
    const g = [];
    for (let i = 0; i < 3; i += 1) {
      const y = cy - 3 + i * 3;
      if (broken && i !== 1) g.push(rect(cx - 4.4, y - 0.7, 3.6, 1.4, '#000'), rect(cx + 0.8, y - 0.7, 3.6, 1.4, '#000'));
      else g.push(rect(cx - 4.4, y - 0.7, 8.8, 1.4, '#000'));
    }
    return `<g transform="rotate(${rot} ${cx} ${cy})">${g.join('')}</g>`;
  };
  return [
    rect(0, 0, W, H, '#fff'),
    '<path d="M18 20A12 12 0 0 1 42 20Z" fill="#CD2E3A"/>',
    '<path d="M18 20A12 12 0 0 0 42 20Z" fill="#0047A0"/>',
    circ(24, 20, 6, '#CD2E3A'), circ(36, 20, 6, '#0047A0'),
    bars(9.5, 7.5, -56, false), bars(50.5, 32.5, -56, true), bars(50.5, 7.5, 56, true), bars(9.5, 32.5, 56, false),
  ].join('');
})();

const sgStars = Array.from({ length: 5 }, (_, i) => {
  const a = ((-90 + i * 72) * Math.PI) / 180;
  return star(num(24 + 5.6 * Math.cos(a)), num(10.5 + 5.6 * Math.sin(a)), 1.7, '#fff');
}).join('');

const ART = {
  // Европа
  RU: [hs('#fff', '#0039A6', '#D52B1E'), '#0039A6'],
  DE: [hs('#000', '#DD0000', '#FFCE00'), '#DD0000'],
  FR: [vs('#0055A4', '#fff', '#EF4135'), '#0055A4'],
  IT: [vs('#009246', '#fff', '#CE2B37'), '#009246'],
  ES: [hw([['#AA151B', 1], ['#F1BF00', 2], ['#AA151B', 1]]), '#F1BF00'],
  PT: [rect(0, 0, 24, H, '#006600') + rect(24, 0, 36, H, '#FF0000') + circ(24, 20, 6.2, '#FFE000') + circ(24, 20, 3.8, '#fff'), '#006600'],
  GB: [unionJack, '#012169'],
  IE: [vs('#169B62', '#fff', '#FF883E'), '#169B62'],
  NL: [hs('#AE1C28', '#fff', '#21468B'), '#21468B'],
  BE: [vs('#000', '#FDDA24', '#EF3340'), '#FDDA24'],
  LU: [hs('#EF3340', '#fff', '#00A3E0'), '#00A3E0'],
  CH: [rect(0, 0, W, H, '#DA291C') + rect(26, 8, 8, 24, '#fff') + rect(18, 16, 24, 8, '#fff'), '#DA291C'],
  AT: [hs('#ED2939', '#fff', '#ED2939'), '#ED2939'],
  LI: [hs('#002B7F', '#CE1126') + circ(10, 10, 3, '#FFD83D'), '#002B7F'],
  SE: [nordic('#006AA7', 21, 20, [8, '#FECC00']), '#006AA7'],
  NO: [nordic('#BA0C2F', 21, 20, [12, '#fff'], [6, '#00205B']), '#BA0C2F'],
  DK: [nordic('#C8102E', 21, 20, [6, '#fff']), '#C8102E'],
  FI: [rect(0, 0, W, H, '#fff') + rect(17, 0, 7.5, H, '#003580') + rect(0, 16.2, W, 7.5, '#003580'), '#003580'],
  IS: [nordic('#02529C', 21, 20, [10, '#fff'], [5, '#DC1E35']), '#02529C'],
  PL: [hs('#fff', '#DC143C'), '#DC143C'],
  CZ: [rect(0, 0, W, 20, '#fff') + rect(0, 20, W, 20, '#D7141A') + poly('0,0 30,20 0,40', '#11457E'), '#11457E'],
  SK: [hs('#fff', '#0B4EA2', '#EE1C25') + poly('10,9 24,9 24,22 17,28.5 10,22', '#EE1C25') + rect(16, 12, 2, 10, '#fff') + rect(13, 15, 8, 2, '#fff'), '#0B4EA2'],
  HU: [hs('#CD2A3E', '#fff', '#436F4D'), '#CD2A3E'],
  RO: [vs('#002B7F', '#FCD116', '#CE1126'), '#FCD116'],
  BG: [hs('#fff', '#00966E', '#D62612'), '#00966E'],
  GR: [Array.from({ length: 9 }, (_, i) => rect(0, num((i * H) / 9), W, num(H / 9 + 0.2), i % 2 === 0 ? '#0D5EAF' : '#fff')).join('') + rect(0, 0, 22.3, 22.3, '#0D5EAF') + rect(8.9, 0, 4.5, 22.3, '#fff') + rect(0, 8.9, 22.3, 4.5, '#fff'), '#0D5EAF'],
  CY: [rect(0, 0, W, H, '#fff') + '<ellipse cx="30" cy="17" rx="11" ry="4.6" fill="#D57800"/><path d="M20 28Q30 34 40 28" stroke="#4E5B31" stroke-width="1.6" fill="none"/>', '#D57800'],
  MT: [rect(0, 0, 30, H, '#fff') + rect(30, 0, 30, H, '#CF142B') + rect(7, 5, 6, 6, '#9AA3AE'), '#CF142B'],
  HR: [hs('#FF0000', '#fff', '#171796') + rect(25, 13, 10, 14, '#FF0000') + rect(25, 13, 5, 3.5, '#fff') + rect(30, 16.5, 5, 3.5, '#fff') + rect(25, 20, 5, 3.5, '#fff') + rect(30, 23.5, 5, 3.5, '#fff'), '#171796'],
  SI: [hs('#fff', '#0000FF', '#FF0000') + poly('10,8 22,8 22,20 16,25 10,20', '#0000FF', ' stroke="#fff" stroke-width="0.8"'), '#0000FF'],
  RS: [hs('#C6363C', '#0C4076', '#fff'), '#0C4076'],
  BA: [rect(0, 0, W, H, '#002F6C') + poly('17,0 47,0 47,40', '#FECB00') + Array.from({ length: 7 }, (_, i) => star(num(14.5 + i * 4.7), num(-1 + i * 6.3), 1.3, '#fff')).join(''), '#002F6C'],
  ME: [rect(0, 0, W, H, '#D4AF37') + rect(2.4, 1.6, 55.2, 36.8, '#C40308'), '#C40308'],
  MK: [rect(0, 0, W, H, '#D20000') + poly('27,0 33,0 30,20', '#FFE600') + poly('27,40 33,40 30,20', '#FFE600') + poly('0,17 0,23 30,20', '#FFE600') + poly('60,17 60,23 30,20', '#FFE600') + poly('0,0 8,0 30,20', '#FFE600') + poly('60,0 52,0 30,20', '#FFE600') + poly('0,40 8,40 30,20', '#FFE600') + poly('60,40 52,40 30,20', '#FFE600') + circ(30, 20, 7, '#FFE600') + circ(30, 20, 5.8, '#D20000') + circ(30, 20, 4.6, '#FFE600'), '#D20000'],
  AL: [rect(0, 0, W, H, '#E41E20') + '<ellipse cx="30" cy="22" rx="7" ry="9" fill="#000"/>' + poly('16,13 30,20 44,13 40,28 30,26 20,28', '#000') + circ(25, 11, 3, '#000') + circ(35, 11, 3, '#000'), '#E41E20'],
  XK: [rect(0, 0, W, H, '#244AA5') + poly('22,23 26,18 32,16 38,18 41,22 38,27 31,28 25,27', '#D0A650') + [[20, 10], [24, 8], [28, 7], [32, 7], [36, 8], [40, 10]].map(([x, y]) => star(x, y, 1.7, '#fff')).join(''), '#244AA5'],
  UA: [hs('#0057B7', '#FFD700'), '#0057B7'],
  BY: [rect(0, 0, W, 27, '#C8313E') + rect(0, 27, W, 13, '#4AA657') + rect(0, 0, 7, H, '#fff') + rect(1, 3, 2, 34, '#C8313E') + rect(4, 3, 2, 34, '#C8313E'), '#C8313E'],
  MD: [vs('#0046AE', '#FFD200', '#CC092F') + circ(30, 20, 4.2, '#9C7A32'), '#FFD200'],
  LT: [hs('#FDB913', '#006A44', '#C1272D'), '#006A44'],
  LV: [rect(0, 0, W, H, '#9E3039') + rect(0, 16, W, 8, '#fff'), '#9E3039'],
  EE: [hs('#0072CE', '#000', '#fff'), '#0072CE'],
  GE: [rect(0, 0, W, H, '#fff') + rect(26.5, 0, 7, H, '#FF0000') + rect(0, 16.5, W, 7, '#FF0000') + [[13, 9], [47, 9], [13, 31], [47, 31]].map(([x, y]) => rect(x - 1.5, y - 3.5, 3, 7, '#FF0000') + rect(x - 3.5, y - 1.5, 7, 3, '#FF0000')).join(''), '#FF0000'],
  AM: [hs('#D90012', '#0033A0', '#F2A800'), '#0033A0'],
  AZ: [hs('#00B5E2', '#EF3340', '#509E2F') + circ(28.5, 20, 5, '#fff') + circ(30, 20, 4, '#EF3340') + star(35, 20, 2.2, '#fff', 8, -90, 0.5), '#00B5E2'],
  TR: [rect(0, 0, W, H, '#E30A17') + circ(23, 20, 10, '#fff') + circ(26, 20, 8, '#E30A17') + star(33.5, 20, 4.2, '#fff'), '#E30A17'],
  // Америка
  US: [usStripes + rect(0, 0, 26, 21.6, '#3C3B6E') + usStars, '#B22234'],
  CA: [rect(0, 0, W, H, '#D80621') + rect(15, 0, 30, H, '#fff') + '<path d="M30 8L32.2 13 35.5 11.5 34.6 17.8 38 15.8 37 19.5 41 20.8 36 24.2 36.8 26.4 31 25.4 31 31 29 31 29 25.4 23.2 26.4 24 24.2 19 20.8 23 19.5 22 15.8 25.4 17.8 24.5 11.5 27.8 13Z" fill="#D80621"/>', '#D80621'],
  MX: [vs('#006847', '#fff', '#CE1126') + circ(30, 20, 5, '#8C6B3F', ' fill-opacity="0.85"'), '#006847'],
  BR: [rect(0, 0, W, H, '#009C3B') + poly('30,5 54,20 30,35 6,20', '#FFDF00') + circ(30, 20, 8.6, '#002776') + '<path d="M21.6 18.2Q30 15 38.5 21" stroke="#fff" stroke-width="1.6" fill="none"/>', '#009C3B'],
  AR: [hs('#74ACDF', '#fff', '#74ACDF') + circ(30, 20, 3.8, '#F6B40E'), '#74ACDF'],
  CL: [rect(0, 0, W, H, '#fff') + rect(0, 20, W, 20, '#D52B1E') + rect(0, 0, 20, 20, '#0039A6') + star(10, 10, 5, '#fff'), '#D52B1E'],
  CO: [hw([['#FCD116', 2], ['#003893', 1], ['#CE1126', 1]]), '#FCD116'],
  PE: [vs('#D91023', '#fff', '#D91023'), '#D91023'],
  VE: [hs('#FFCC00', '#00247D', '#CF142B'), '#00247D'],
  UY: [Array.from({ length: 9 }, (_, i) => rect(0, num((i * H) / 9), W, num(H / 9 + 0.2), i % 2 === 0 ? '#fff' : '#0038A8')).join('') + rect(0, 0, 22.3, 22.3, '#fff') + circ(11, 11, 5, '#FCD116'), '#0038A8'],
  PY: [hs('#D52B1E', '#fff', '#0038A8'), '#0038A8'],
  BO: [hs('#D52B1E', '#F9E300', '#007A33'), '#F9E300'],
  EC: [hw([['#FFDD00', 2], ['#034EA2', 1], ['#ED1C24', 1]]), '#FFDD00'],
  CU: [hs('#002A8F', '#fff', '#002A8F', '#fff', '#002A8F') + poly('0,0 26,20 0,40', '#CF142B') + star(8, 20, 5, '#fff'), '#002A8F'],
  CR: [hw([['#002B7F', 1], ['#fff', 1], ['#CE1126', 2], ['#fff', 1], ['#002B7F', 1]]), '#CE1126'],
  PA: [rect(0, 0, W, H, '#fff') + rect(30, 0, 30, 20, '#D21034') + rect(0, 20, 30, 20, '#005293') + star(15, 10, 5, '#005293') + star(45, 30, 5, '#D21034'), '#005293'],
  GT: [vs('#4997D0', '#fff', '#4997D0'), '#4997D0'],
  HN: [hs('#0073CF', '#fff', '#0073CF') + [[30, 20], [24, 17], [36, 17], [24, 23], [36, 23]].map(([x, y]) => star(x, y, 1.8, '#0073CF')).join(''), '#0073CF'],
  SV: [hs('#0F47AF', '#fff', '#0F47AF'), '#0F47AF'],
  NI: [hs('#0067C6', '#fff', '#0067C6'), '#0067C6'],
  HT: [hs('#00209F', '#D21034'), '#00209F'],
  DO: [rect(0, 0, W, H, '#fff') + rect(0, 0, 25, 16, '#002D62') + rect(35, 0, 25, 16, '#CE1126') + rect(0, 24, 25, 16, '#CE1126') + rect(35, 24, 25, 16, '#002D62'), '#002D62'],
  JM: [rect(0, 0, W, H, '#009B3A') + poly('0,0 30,20 0,40', '#000') + poly('60,0 30,20 60,40', '#000') + '<path d="M0 0L60 40M60 0L0 40" stroke="#FED100" stroke-width="5"/>', '#009B3A'],
  BS: [hw([['#00ABC9', 1], ['#FFC72C', 1], ['#00ABC9', 1]]) + poly('0,0 24,20 0,40', '#000'), '#00ABC9'],
  // Азия и Ближний Восток
  CN: [rect(0, 0, W, H, '#DE2910') + star(12, 11, 7, '#FFDE00') + star(24, 4, 2.2, '#FFDE00') + star(28, 9, 2.2, '#FFDE00') + star(28, 16, 2.2, '#FFDE00') + star(24, 21, 2.2, '#FFDE00'), '#DE2910'],
  JP: [rect(0, 0, W, H, '#fff') + circ(30, 20, 12, '#BC002D'), '#BC002D'],
  KR: [kr, '#0047A0'],
  IN: [hs('#FF9933', '#fff', '#138808') + chakra, '#FF9933'],
  PK: [rect(0, 0, W, H, '#01411C') + rect(0, 0, 15, H, '#fff') + crescent(38, 20, 10, 3.6, '#fff', '#01411C', 8.6) + star(44, 14.5, 3.2, '#fff'), '#01411C'],
  BD: [rect(0, 0, W, H, '#006A4E') + circ(27, 20, 12, '#F42A41'), '#006A4E'],
  ID: [hs('#FF0000', '#fff'), '#FF0000'],
  MY: [Array.from({ length: 14 }, (_, i) => rect(0, num((i * H) / 14), W, num(H / 14 + 0.2), i % 2 === 0 ? '#CC0001' : '#fff')).join('') + rect(0, 0, 30, 21.5, '#010066') + crescent(11, 10.7, 6, 1.9, '#FFCC00', '#010066', 5) + star(19, 10.7, 3.4, '#FFCC00', 14, -90, 0.55), '#CC0001'],
  SG: [rect(0, 0, W, 20, '#ED2939') + rect(0, 20, W, 20, '#fff') + crescent(14, 10, 7.2, 3.2, '#fff', '#ED2939', 6) + sgStars, '#ED2939'],
  TH: [hw([['#A51931', 1], ['#fff', 1], ['#2D2A4A', 2], ['#fff', 1], ['#A51931', 1]]), '#2D2A4A'],
  VN: [rect(0, 0, W, H, '#DA251D') + star(30, 21.5, 11, '#FFFF00'), '#DA251D'],
  PH: [rect(0, 0, W, 20, '#0038A8') + rect(0, 20, W, 20, '#CE1126') + poly('0,0 34,20 0,40', '#fff') + circ(10, 20, 3.4, '#FCD116') + star(3, 6, 1.7, '#FCD116') + star(3, 34, 1.7, '#FCD116') + star(22, 20, 1.7, '#FCD116'), '#0038A8'],
  MM: [hs('#FECB00', '#34B233', '#EA2839') + star(30, 21, 11, '#fff'), '#34B233'],
  MN: [vs('#C4272F', '#015197', '#C4272F') + rect(8, 11, 4, 18, '#F9CF02') + circ(10, 14, 1.6, '#F9CF02'), '#015197'],
  TW: [rect(0, 0, W, H, '#FE0000') + rect(0, 0, 30, 20, '#000095') + circ(15, 10, 5.4, '#fff') + circ(15, 10, 3.9, '#000095') + circ(15, 10, 3.2, '#fff'), '#FE0000'],
  KZ: [rect(0, 0, W, H, '#00AFCA') + circ(30, 20, 6.2, '#FEC50C') + circ(30, 20, 9, 'none', ' stroke="#FEC50C" stroke-width="1.2"'), '#00AFCA'],
  UZ: [hs('#0099B5', '#fff', '#1EB53A') + rect(0, 12.5, W, 1.1, '#CE1126') + rect(0, 26.4, W, 1.1, '#CE1126') + crescent(8, 6.4, 3.4, 1.3, '#fff', '#0099B5', 2.9), '#0099B5'],
  SA: [rect(0, 0, W, H, '#006C35') + '<path d="M18 14q4-4 8 0t8 0 8 0" stroke="#fff" stroke-width="2" fill="none"/><path d="M15 28H45" stroke="#fff" stroke-width="1.8"/>', '#006C35'],
  AE: [rect(0, 0, W, 13.4, '#00732F') + rect(0, 13.3, W, 13.4, '#fff') + rect(0, 26.6, W, 13.4, '#000') + rect(0, 0, 15, H, '#FF0000'), '#FF0000'],
  QA: [rect(0, 0, W, H, '#8A1538') + poly('0,0 16,0 22,3.1 16,6.2 22,9.3 16,12.4 22,15.5 16,18.6 22,21.7 16,24.8 22,27.9 16,31 22,34.1 16,37.2 20,40 0,40', '#fff'), '#8A1538'],
  KW: [hs('#007A3D', '#fff', '#CE1126') + poly('0,0 15,13 15,27 0,40', '#000'), '#007A3D'],
  JO: [hs('#000', '#fff', '#007A3D') + poly('0,0 30,20 0,40', '#CE1126'), '#007A3D'],
  IL: [rect(0, 0, W, H, '#fff') + rect(0, 4, W, 5.5, '#0038B8') + rect(0, 30.5, W, 5.5, '#0038B8') + '<g fill="none" stroke="#0038B8" stroke-width="1.4"><polygon points="30,12 36.2,23 23.8,23"/><polygon points="30,28 23.8,17 36.2,17"/></g>', '#0038B8'],
  IR: [hs('#239F40', '#fff', '#DA0000') + circ(30, 20, 3.2, '#DA0000'), '#239F40'],
  IQ: [hs('#CE1126', '#fff', '#000'), '#CE1126'],
  // Африка
  EG: [hs('#CE1126', '#fff', '#000') + circ(30, 20, 3, '#C09300'), '#CE1126'],
  ZA: [rect(0, 0, W, H, '#fff') + rect(0, 0, W, 17, '#E03C31') + rect(0, 23, W, 17, '#001489') + poly('0,0 22,0 36,16 60,16 60,24 36,24 22,40 0,40', '#fff') + poly('0,2.4 20,2.4 33,17.4 60,17.4 60,22.6 33,22.6 20,37.6 0,37.6', '#007749') + poly('0,0 0,40 20,20', '#FFB81C') + poly('0,3.4 0,36.6 16.2,20', '#000'), '#007749'],
  NG: [vs('#008751', '#fff', '#008751'), '#008751'],
  KE: [rect(0, 0, W, 12, '#000') + rect(0, 12, W, 1.4, '#fff') + rect(0, 13.4, W, 13.2, '#BB0000') + rect(0, 26.6, W, 1.4, '#fff') + rect(0, 28, W, 12, '#006600') + '<ellipse cx="30" cy="20" rx="5" ry="10" fill="#BB0000" stroke="#fff" stroke-width="1"/>', '#BB0000'],
  ET: [hs('#078930', '#FCDD09', '#DA121A') + circ(30, 20, 8, '#0F47AF') + star(30, 20, 5.6, '#FCDD09'), '#078930'],
  GH: [hs('#CE1126', '#FCD116', '#006B3F') + star(30, 20, 6, '#000'), '#FCD116'],
  MA: [rect(0, 0, W, H, '#C1272D') + pentagram(30, 20.5, 8.5, '#006233', 1.5), '#C1272D'],
  DZ: [rect(0, 0, 30, H, '#006233') + rect(30, 0, 30, H, '#fff') + crescent(30, 20, 10, 3, '#D21034', '#fff', 8.2) + star(33.5, 20, 3.6, '#D21034'), '#006233'],
  TN: [rect(0, 0, W, H, '#E70013') + circ(30, 20, 10, '#fff') + circ(28.6, 20, 7.8, '#E70013') + circ(31, 20, 6.3, '#fff') + star(31, 20, 3.8, '#E70013'), '#E70013'],
  LY: [hw([['#E70013', 1], ['#000', 2], ['#239E46', 1]]) + crescent(29, 20, 6, 2, '#fff', '#000', 5) + star(35, 20, 2.2, '#fff'), '#E70013'],
  SN: [vs('#00853F', '#FDEF42', '#E31B23') + star(30, 20, 5, '#00853F'), '#00853F'],
  CI: [vs('#F77F00', '#fff', '#009E60'), '#F77F00'],
  ML: [vs('#14B53A', '#FCD116', '#CE1126'), '#14B53A'],
  CM: [vs('#007A5E', '#CE1126', '#FCD116') + star(30, 20, 5.4, '#FCD116'), '#007A5E'],
  AO: [hs('#CC092F', '#000') + circ(30, 20, 5.2, '#FFCB00'), '#CC092F'],
  UG: [hs('#000', '#FCDC04', '#D90000', '#000', '#FCDC04', '#D90000') + circ(30, 20, 7, '#fff'), '#FCDC04'],
  // Океания
  AU: [rect(0, 0, W, H, '#012169') + `<g transform="scale(.5)">${unionJack}</g>` + star(15, 30, 5, '#fff', 7, -90, 0.5) + star(44, 7, 2.5, '#fff', 7, -90, 0.5) + star(37, 18, 2.5, '#fff', 7, -90, 0.5) + star(52, 16, 2.5, '#fff', 7, -90, 0.5) + star(44, 32, 2.5, '#fff', 7, -90, 0.5), '#012169'],
  NZ: [rect(0, 0, W, H, '#012169') + `<g transform="scale(.5)">${unionJack}</g>` + [[44, 9], [37, 19], [52, 17], [44, 31]].map(([x, y]) => star(x, y, 3, '#CC142B', 5, -90, 0.382, ' stroke="#fff" stroke-width="0.7"')).join(''), '#012169'],
};

/** Код ISO (в каталоге UK и EL — это GB и GR). */
const ALIASES = { UK: 'GB', EL: 'GR' };

/** Векторный флаг по двухбуквенному коду: { svg, glow } или null, если рисунка нет (тогда остаётся эмодзи). */
export function flagArt(code) {
  const raw = String(code ?? '').trim().toUpperCase();
  const iso = ALIASES[raw] || raw;
  const entry = ART[iso];
  if (!entry) return null;
  return { svg: entry[0], glow: entry[1] };
}

/** Какие коды нарисованы (для тестов и проверки покрытия). */
export const FLAG_ART_CODES = Object.freeze(Object.keys(ART));
