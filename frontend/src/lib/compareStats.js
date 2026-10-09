// Связь двух рядов на странице «Сравнение»: по изменениям от даты к дате, а не по уровням.
// Два растущих ряда (ВВП Китая и США) всегда «связаны» по уровням, потому что оба идут вверх; по изменениям видно,
// совпадали ли подъёмы и спады на самом деле.

export function pearsonCorrelation(pairs) {
  if (!Array.isArray(pairs) || pairs.length < 6) return null;
  const meanX = pairs.reduce((sum, pair) => sum + pair[0], 0) / pairs.length;
  const meanY = pairs.reduce((sum, pair) => sum + pair[1], 0) / pairs.length;
  let covariance = 0;
  let varianceX = 0;
  let varianceY = 0;
  for (const [x, y] of pairs) {
    const dx = x - meanX;
    const dy = y - meanY;
    covariance += dx * dy;
    varianceX += dx * dx;
    varianceY += dy * dy;
  }
  const denominator = Math.sqrt(varianceX * varianceY);
  return denominator > 0 ? covariance / denominator : null;
}

/**
 * Изменения двух рядов на общих датах: пары (изменение первого, изменение второго) между соседними общими датами.
 * Положительные ряды (уровни, индексы) берутся в логарифмическом приросте, остальные (проценты, сальдо) разностью.
 *
 * @param {Array<{date:string,value:number}>} a
 * @param {Array<{date:string,value:number}>} b
 */
export function changePairs(a, b) {
  const byDate = new Map((b || []).map((p) => [p.date, Number(p.value)]));
  const common = (a || [])
    .map((p) => ({ date: p.date, x: Number(p.value), y: byDate.get(p.date) }))
    .filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y))
    .sort((p, q) => (p.date < q.date ? -1 : 1));
  if (common.length < 2) return [];
  const positive = common.every((p) => p.x > 0 && p.y > 0);
  const pairs = [];
  for (let i = 1; i < common.length; i += 1) {
    const prev = common[i - 1];
    const cur = common[i];
    pairs.push(positive
      ? [Math.log(cur.x / prev.x), Math.log(cur.y / prev.y)]
      : [cur.x - prev.x, cur.y - prev.y]);
  }
  return pairs;
}

/** Связь по изменениям; null, если общих дат мало. */
export function changeCorrelation(a, b) {
  const pairs = changePairs(a, b);
  return { value: pearsonCorrelation(pairs), observations: pairs.length };
}
