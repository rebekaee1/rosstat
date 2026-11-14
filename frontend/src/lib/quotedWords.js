/** Слова запроса, без которых нашлись ряды «Ближайшего»: «структура», «кормовых» (ru) / “structure” (en). */
export function quotedWords(words, locale) {
  const list = Array.isArray(words) ? words.filter(Boolean) : [];
  return list.map((word) => (locale === 'en' ? `“${word}”` : `«${word}»`)).join(', ');
}
