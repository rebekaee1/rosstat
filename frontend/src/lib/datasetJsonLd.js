/** Complete a Dataset description without changing source ownership or rights. */
export function completeDataset(node, locale = 'ru') {
  const name = String(node?.name || '').replace(/\s+/g, ' ').trim();
  let description = String(node?.description || '').replace(/\s+/g, ' ').trim();
  if (description.length < 50) {
    const creatorName = String(node?.creator?.name || '').trim();
    const source = creatorName
      ? (locale === 'en' ? ` Source: ${creatorName}.` : ` Источник: ${creatorName}.`)
      : '';
    const detail = locale === 'en'
      ? ' Details and published observations are available on Forecast Economy.'
      : ' Описание и опубликованные значения доступны на Forecast Economy.';
    description = `${description} ${name}.${source}${detail}`.replace(/\s+/g, ' ').trim();
  }
  if (description.length > 5000) {
    description = `${description.slice(0, 4999).trimEnd()}…`;
  }
  return { ...node, description };
}
