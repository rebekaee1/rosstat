/**
 * Смысловой цвет изменения. Рост инфляции, безработицы или долга — не «зелёное», а падение золота не обязательно «красное».
 * Если по названию нельзя понять, хорошо ли это, изменение остаётся нейтральным (графит со стрелкой), без оценки.
 * Круг 10 (Г3): у котировок активов (биткоин, золото, нефть Brent, металлы, индексы бирж) цвет задаёт только знак: рост зелёный,
 * падение красное, как на бирже; это не оценка «хорошо/плохо» для экономики, поэтому у них свой вид полярности `market`.
 * Курсы валют остаются без оценки: рост доллара для рубля не «хорошо» и не «плохо» (решение раунда 6, не меняется).
 */
const MARKET = /биткоин|биткойн|bitcoin|\bbtc\b|эфириум|ethereum|\beth\b|solana|золот[оаы]|gold|серебр|silver|платин|палладий|brent|мосбирж|moex|\brts\b|s&p|nasdaq|dow jones/i;
const MARKET_CODE = /^(btc|eth|sol)-usd|^brent|^gold|^silver|^platinum|^palladium|^copper|^natural-gas|^imoex|^rts/i;
const UP_IS_BAD = /инфляц|безработ|долг|дефицит|бедност|смертност|ключевая ставка|ставк|ипц|потребительск[а-я]+ цен|inflation|unemploy|debt|deficit|poverty|mortality|interest rate|consumer price|\bcpi\b|умерш|смертн|deaths|преступ|crime/i;
const UP_IS_GOOD = /ввп|валов|gdp|зарплат|заработн|wage|доход|income|занятост|employment|экспорт|export|рождаем|birth rate|инвестиц|investment|промышлен|производств|production|retail|розничн|родивш|births|население|population|числ[оа] заняты/i;

export function indicatorPolarity(...labels) {
  const text = labels.filter(Boolean).join(' ');
  if (!text) return 'neutral';
  if (/безработ|unemploy/i.test(text)) return 'up-bad';
  if (UP_IS_BAD.test(text)) return 'up-bad';
  if (UP_IS_GOOD.test(text)) return 'up-good';
  if (MARKET.test(text) || labels.some((label) => typeof label === 'string' && MARKET_CODE.test(label))) return 'market';
  return 'neutral';
}

/** @returns {'good'|'bad'|'neutral'|'flat'} */
export function deltaTone(delta, polarity = 'neutral') {
  const value = Number(delta);
  if (!Number.isFinite(value) || value === 0) return 'flat';
  if (polarity === 'up-good') return value > 0 ? 'good' : 'bad';
  if (polarity === 'up-bad') return value > 0 ? 'bad' : 'good';
  if (polarity === 'market') return value > 0 ? 'good' : 'bad';
  return 'neutral';
}

export function deltaArrow(delta) {
  const value = Number(delta);
  if (!Number.isFinite(value) || value === 0) return '→';
  return value > 0 ? '↗' : '↘';
}
