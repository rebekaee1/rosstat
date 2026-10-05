/** Страны, которые сравнивают чаще всего: стоят в начале списка, остальные по алфавиту. */
export const PRIORITY_COUNTRIES = ['russia', 'united-states', 'china', 'germany', 'india'];

/**
 * Порядок для выбора стран: «Россия, США, Китай, Германия, Индия», затем остальные в том порядке,
 * который задан выше по потоку (алфавит). Особый пункт «average» остаётся самым первым.
 */
export function orderCountryOptions(options) {
  const rank = (option) => {
    if (option.code === 'average') return -1;
    const index = PRIORITY_COUNTRIES.indexOf(option.country_slug);
    return index === -1 ? PRIORITY_COUNTRIES.length : index;
  };
  // sort стабилен: внутри «остальных» алфавитный порядок сохраняется.
  return [...(options || [])].sort((a, b) => rank(a) - rank(b));
}
