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

