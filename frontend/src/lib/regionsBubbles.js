// Режим «Пузыри» карты регионов: у каждого региона одинаковый кружок (равная площадь), поставленный
// на центр региона и слегка раздвинутый от соседей. Так Москва, Петербург и Чукотка видны одинаково,
// а цвет по-прежнему говорит о значении показателя (на обычной карте огромные северные регионы
// «перекрикивают» маленькие густонаселённые).
// Геометрия — те же пути regionsMap.json (только команды M/L/Z), поэтому центр считается прямо из них.

const NUM_RE = /([ML])\s*(-?\d+(?:\.\d+)?)[ ,]+(-?\d+(?:\.\d+)?)/g;

/** Кольца пути: [[x, y], ...] для каждого подпути. */
export function pathRings(path) {
  const rings = [];
  let cur = null;
  NUM_RE.lastIndex = 0;
  let m = NUM_RE.exec(path);
  while (m) {
    const pt = [Number(m[2]), Number(m[3])];
    if (m[1] === 'M') {
      cur = [pt];
      rings.push(cur);
    } else if (cur) {
      cur.push(pt);
    }
    m = NUM_RE.exec(path);
  }
  return rings;
}

function ringArea(ring) {
  let a = 0;
  for (let i = 0; i < ring.length; i += 1) {
    const [x1, y1] = ring[i];
    const [x2, y2] = ring[(i + 1) % ring.length];
    a += x1 * y2 - x2 * y1;
  }
  return a / 2;
}

/** Центр самого большого кольца (центр тяжести многоугольника); для вырожденного кольца — середина его рамки. */
export function pathCentroid(path) {
  const rings = pathRings(path).filter((r) => r.length >= 3);
  if (!rings.length) return null;
  const biggest = rings.reduce((best, r) => (Math.abs(ringArea(r)) > Math.abs(ringArea(best)) ? r : best), rings[0]);
  const area = ringArea(biggest);
  if (Math.abs(area) < 1e-6) {
    const xs = biggest.map((p) => p[0]);
    const ys = biggest.map((p) => p[1]);
    return { x: (Math.min(...xs) + Math.max(...xs)) / 2, y: (Math.min(...ys) + Math.max(...ys)) / 2 };
  }
  let cx = 0;
  let cy = 0;
  for (let i = 0; i < biggest.length; i += 1) {
    const [x1, y1] = biggest[i];
    const [x2, y2] = biggest[(i + 1) % biggest.length];
    const f = x1 * y2 - x2 * y1;
    cx += (x1 + x2) * f;
    cy += (y1 + y2) * f;
  }
  return { x: cx / (6 * area), y: cy / (6 * area) };
}

const cache = new WeakMap();

/**
 * Раскладка пузырей: Map slug -> { x, y, r }. Радиус общий. Кружки раздвигаются простой релаксацией
 * (пары ближе двух радиусов расталкиваются, к исходному центру тянет слабая пружина), поэтому
 * положение остаётся «географическим», но кружки не налезают друг на друга.
 */
export function bubbleLayout(geometry, { radius = 6.4, iterations = 90 } = {}) {
  if (cache.has(geometry)) return cache.get(geometry);
  const [, , w, h] = String(geometry.viewBox || '0 0 1000 538').split(' ').map(Number);
  const nodes = [];
  for (const region of geometry.regions || []) {
    const c = pathCentroid(region.path);
    if (c) nodes.push({ slug: region.slug, ox: c.x, oy: c.y, x: c.x, y: c.y });
  }
  const gap = radius * 2 + 0.8;
  for (let step = 0; step < iterations; step += 1) {
    for (let i = 0; i < nodes.length; i += 1) {
      for (let j = i + 1; j < nodes.length; j += 1) {
        const a = nodes[i];
        const b = nodes[j];
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const dist = Math.hypot(dx, dy) || 0.01;
        if (dist >= gap) continue;
        const push = (gap - dist) / 2;
        const ux = dx / dist;
        const uy = dy / dist;
        a.x -= ux * push;
        a.y -= uy * push;
        b.x += ux * push;
        b.y += uy * push;
      }
    }
    for (const n of nodes) {
      n.x += (n.ox - n.x) * 0.04;
      n.y += (n.oy - n.y) * 0.04;
      n.x = Math.min(Math.max(n.x, radius + 1), w - radius - 1);
      n.y = Math.min(Math.max(n.y, radius + 1), h - radius - 1);
    }
  }
  const out = new Map(nodes.map((n) => [n.slug, { x: n.x, y: n.y, r: radius }]));
  cache.set(geometry, out);
  return out;
}
