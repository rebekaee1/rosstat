// Флаги стран по slug каталога (эмодзи из региональных индикаторов ISO-кода; векторные капли — components/brand/flagArt.js по тому же ISO-коду).
// Нужен там, где в данных есть только slug (подбор стран в сравнении). Нет в карте — пустая строка, а не серый глобус.
export const SLUG_ISO = {
  albania: 'AL', armenia: 'AM', australia: 'AU', austria: 'AT', azerbaijan: 'AZ', belgium: 'BE',
  bosnia: 'BA', brazil: 'BR', bulgaria: 'BG', canada: 'CA', china: 'CN', croatia: 'HR', cyprus: 'CY',
  czechia: 'CZ', denmark: 'DK', estonia: 'EE', finland: 'FI', france: 'FR', georgia: 'GE',
  germany: 'DE', greece: 'GR', hungary: 'HU', iceland: 'IS', india: 'IN', ireland: 'IE', israel: 'IL',
  italy: 'IT', japan: 'JP', kosovo: 'XK', latvia: 'LV', lithuania: 'LT', luxembourg: 'LU', malta: 'MT',
  mexico: 'MX', moldova: 'MD', montenegro: 'ME', netherlands: 'NL', 'new-zealand': 'NZ',
  'north-macedonia': 'MK', norway: 'NO', poland: 'PL', portugal: 'PT', romania: 'RO', russia: 'RU',
  serbia: 'RS', slovakia: 'SK', slovenia: 'SI', 'south-africa': 'ZA', 'south-korea': 'KR', spain: 'ES',
  sweden: 'SE', switzerland: 'CH', turkey: 'TR', ukraine: 'UA', 'united-kingdom': 'GB',
  'united-states': 'US',
};

export function flagFromIso(iso) {
  const code = String(iso || '').toUpperCase();
  if (!/^[A-Z]{2}$/.test(code)) return '';
  return String.fromCodePoint(...[...code].map((ch) => 0x1F1E6 + ch.charCodeAt(0) - 65));
}

/** ISO-код страны по slug каталога (для <CountryFlag code glass />); неизвестный slug — пустая строка. */
export function isoForSlug(slug) {
  return SLUG_ISO[slug] || '';
}

export function flagForSlug(slug) {
  return flagFromIso(SLUG_ISO[slug]);
}

/** Быстрые подборки стран для выбора в сравнении (slug-и каталога). */
export const COUNTRY_GROUPS = [
  { id: 'g7', slugs: ['united-states', 'japan', 'germany', 'united-kingdom', 'france', 'italy', 'canada'] },
  { id: 'brics', slugs: ['brazil', 'russia', 'india', 'china', 'south-africa'] },
  { id: 'neighbors', slugs: ['china', 'finland', 'norway', 'poland', 'estonia', 'latvia', 'lithuania', 'ukraine', 'georgia', 'azerbaijan'] },
];
