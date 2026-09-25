import { getSiteOrigin } from './siteOrigin';

const DESCRIPTION_MIN = 50;
const DESCRIPTION_MAX = 5000;

function collapse(value) {
  return String(value || '').replace(/\s+/g, ' ').trim();
}

/** Absolute URL of the site terms. Host follows the page the visitor opened. */
export function datasetLicenseUrl(origin = getSiteOrigin()) {
  return `${String(origin || '').replace(/\/$/, '')}/terms`;
}

/**
 * Dataset JSON-LD with the fields Google Search Console requires or warns on:
 * description (50–5000 characters), creator, and license → /terms.
 */
export function completeDataset(node, locale = 'ru') {
  const name = collapse(node?.name) || 'Forecast Economy';
  const creatorName = collapse(node?.creator?.name) || 'Forecast Economy';
  let description = collapse(node?.description);
  if (description.length > DESCRIPTION_MAX) {
    description = `${description.slice(0, DESCRIPTION_MAX - 1).trimEnd()}…`;
  }
  if (description.length < DESCRIPTION_MIN) {
    const filler = locale === 'en'
      ? `${name} — data series on Forecast Economy. Source: ${creatorName}.`
      : `${name} — ряд данных на Forecast Economy. Источник: ${creatorName}.`;
    description = collapse(description ? `${description} ${filler}` : filler);
    if (description.length < DESCRIPTION_MIN) {
      description = collapse(
        description + (locale === 'en'
          ? ' The series is published as a chart and a table.'
          : ' Ряд опубликован в виде графика и таблицы.'),
      );
    }
    if (description.length > DESCRIPTION_MAX) {
      description = `${description.slice(0, DESCRIPTION_MAX - 1).trimEnd()}…`;
    }
  }
  return {
    ...node,
    '@context': 'https://schema.org',
    '@type': 'Dataset',
    name,
    description,
    creator: { '@type': 'Organization', name: creatorName },
    license: datasetLicenseUrl(),
  };
}
