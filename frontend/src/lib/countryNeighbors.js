// Соседи по региону для подсказки «Сравнить с:» (круг 11, зона C): страны каталога сравнения, с которыми у страны общая граница
// или общий регион. Нужны, чтобы у Турции предлагались Греция и Болгария, а не первые пять стран из общего списка.
import { COUNTRY_GROUPS } from './slugFlags';

const RUSSIA_NEIGHBORS = COUNTRY_GROUPS.find((group) => group.id === 'neighbors')?.slugs || [];

/** slug страны → соседи, самые близкие первыми. Страны без записи получают подсказки только по близости ВВП. */
export const COUNTRY_NEIGHBORS = Object.freeze({
  'united-states': ['canada', 'mexico'],
  china: ['japan', 'south-korea', 'india', 'russia'],
  germany: ['france', 'austria', 'switzerland', 'poland', 'netherlands'],
  japan: ['south-korea', 'china'],
  'united-kingdom': ['ireland', 'france', 'germany'],
  india: ['china'],
  france: ['germany', 'spain', 'italy', 'belgium'],
  russia: RUSSIA_NEIGHBORS,
  italy: ['france', 'spain', 'austria', 'switzerland'],
  canada: ['united-states'],
  brazil: ['mexico'],
  spain: ['portugal', 'france', 'italy'],
  'south-korea': ['japan', 'china'],
  australia: ['new-zealand'],
  mexico: ['united-states', 'brazil'],
  turkey: ['greece', 'bulgaria', 'georgia', 'armenia', 'azerbaijan'],
  netherlands: ['belgium', 'germany'],
  switzerland: ['austria', 'germany', 'france', 'italy'],
  poland: ['germany', 'czechia', 'slovakia', 'lithuania', 'ukraine'],
  belgium: ['netherlands', 'france', 'germany', 'luxembourg'],
  ireland: ['united-kingdom'],
  sweden: ['norway', 'finland', 'denmark'],
  austria: ['germany', 'switzerland', 'czechia', 'hungary', 'slovenia'],
  norway: ['sweden', 'denmark', 'finland'],
  denmark: ['sweden', 'norway', 'germany'],
  romania: ['bulgaria', 'hungary', 'moldova', 'serbia'],
  czechia: ['poland', 'slovakia', 'austria', 'germany'],
  portugal: ['spain'],
  finland: ['sweden', 'estonia', 'norway'],
  greece: ['turkey', 'bulgaria', 'albania', 'north-macedonia', 'cyprus'],
  hungary: ['austria', 'slovakia', 'romania', 'serbia', 'croatia'],
  ukraine: ['poland', 'romania', 'moldova', 'russia'],
  slovakia: ['czechia', 'poland', 'hungary', 'austria'],
  bulgaria: ['romania', 'greece', 'turkey', 'serbia'],
  croatia: ['slovenia', 'serbia', 'hungary', 'bosnia'],
  serbia: ['croatia', 'bosnia', 'hungary', 'romania', 'bulgaria'],
  lithuania: ['latvia', 'estonia', 'poland'],
  latvia: ['estonia', 'lithuania'],
  estonia: ['latvia', 'lithuania', 'finland'],
  georgia: ['armenia', 'azerbaijan', 'turkey'],
  armenia: ['georgia', 'azerbaijan', 'turkey'],
  azerbaijan: ['georgia', 'armenia', 'turkey'],
});

export function neighborsOf(slug) {
  return COUNTRY_NEIGHBORS[slug] || [];
}
