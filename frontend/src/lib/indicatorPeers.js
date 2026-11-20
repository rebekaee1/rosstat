/** Страны для списка «Этот показатель в других странах» (круг 11, F): крупные экономики первыми, остальные по алфавиту. */
import { countryPublicName } from './homeWorkbench';
import { COUNTRY_GROUPS } from './slugFlags';

const MAX_PEERS = 8;
const PRIORITY = new Set(COUNTRY_GROUPS.filter((group) => group.id === 'g7' || group.id === 'brics').flatMap((group) => group.slugs));

/** Страны для списка: крупные экономики первыми, остальные по алфавиту; текущая страна не предлагается сама себе. */
export function pickPeers(peers, currentSlug, locale, limit = MAX_PEERS) {
  const collator = new Intl.Collator(locale === 'en' ? 'en' : 'ru');
  return (Array.isArray(peers) ? peers : [])
    .filter((peer) => peer?.country_slug && peer?.indicator_code && peer.country_slug !== currentSlug)
    .map((peer) => ({ ...peer, name: countryPublicName(peer, locale) }))
    .sort((a, b) => (Number(!PRIORITY.has(a.country_slug)) - Number(!PRIORITY.has(b.country_slug)))
      || collator.compare(a.name, b.name))
    .slice(0, limit);
}


function codeTokens(code) {
  return String(code ?? '').toLowerCase().split('-').filter(Boolean);
}

/**
 * «Похожие показатели» по смыслу (круг наблюдателей 20.11.2026, №34): сначала ряды с общим началом кода («tour-outbound-…» к
 * «tour-outbound-…»), затем та же частота и единица; при равенстве остаётся порядок раздела.
 */
export function rankRelatedIndicators(current, candidates) {
  const own = codeTokens(current?.code);
  const score = (item) => {
    const other = codeTokens(item?.code);
    let common = 0;
    while (common < own.length && common < other.length && own[common] === other[common]) common += 1;
    // Общее только «tour» — это весь раздел, смысла не несёт: считаем с двух общих частей.
    let points = common >= 2 ? common * 10 : 0;
    if (current?.frequency && item?.frequency === current.frequency) points += 2;
    if (current?.unit && item?.unit === current.unit) points += 1;
    return points;
  };
  return (Array.isArray(candidates) ? candidates : [])
    .map((item, index) => ({ item, index, points: score(item) }))
    .sort((a, b) => (b.points - a.points) || (a.index - b.index))
    .map((entry) => entry.item);
}
