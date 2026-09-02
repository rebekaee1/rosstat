export function countryMatchesQuery(option, query) {
  const q = (query || '').trim().toLowerCase().replace(/ё/g, 'е');
  if (!q) return true;
  const hay = [
    option.country_name,
    option.country_slug,
    option.country_code,
  ].filter(Boolean).join(' ').toLowerCase().replace(/ё/g, 'е');
  if (hay.includes(q)) return true;
  if (option.country_slug === 'russia') {
    return ['россия', 'russia', 'рф', 'rf'].some((alias) => alias.startsWith(q));
  }
  return false;
}
