/**
 * Смысловой цвет изменения. Рост инфляции, безработицы или долга — не «зелёное», а падение золота не обязательно «красное».
 * Если по названию нельзя понять, хорошо ли это, изменение остаётся нейтральным (графит со стрелкой), без оценки.
 */
const UP_IS_BAD = /инфляц|безработ|долг|дефицит|бедност|смертност|ключевая ставка|ставк|ипц|потребительск[а-я]+ цен|inflation|unemploy|debt|deficit|poverty|mortality|interest rate|consumer price|\bcpi\b/i;
const UP_IS_GOOD = /ввп|валов|gdp|зарплат|заработн|wage|доход|income|занятост|employment|экспорт|export|рождаем|birth rate|инвестиц|investment|промышлен|производств|production|retail|розничн/i;

export function indicatorPolarity(...labels) {
  const text = labels.filter(Boolean).join(' ');
  if (!text) return 'neutral';
  if (/безработ|unemploy/i.test(text)) return 'up-bad';
  if (UP_IS_BAD.test(text)) return 'up-bad';
  if (UP_IS_GOOD.test(text)) return 'up-good';
  return 'neutral';
}

/** @returns {'good'|'bad'|'neutral'|'flat'} */
export function deltaTone(delta, polarity = 'neutral') {
  const value = Number(delta);
  if (!Number.isFinite(value) || value === 0) return 'flat';
  if (polarity === 'up-good') return value > 0 ? 'good' : 'bad';
  if (polarity === 'up-bad') return value > 0 ? 'bad' : 'good';
  return 'neutral';
}

export function deltaArrow(delta) {
  const value = Number(delta);
  if (!Number.isFinite(value) || value === 0) return '→';
  return value > 0 ? '↗' : '↘';
}
