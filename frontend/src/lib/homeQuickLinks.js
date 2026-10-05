/**
 * Быстрые действия под поиском на главной: прямые ссылки на то, что люди ищут чаще всего.
 * Курс, ставка и инфляция России ведут сразу на страницу показателя, без поиска и без промежуточной панели.
 * Для стран с неизвестным заранее кодом ряда («ВВП Индии») адрес берётся из уже загруженного среза,
 * пока его нет, ссылка ведёт на страницу страны, так что чип работает с первого кадра.
 */
import { mapSelectHref } from './homeWorkbench';
import { countryPath, indicatorPath, russiaIndicatorPath } from './sitePaths';

function snapshotHref(snapshot, code, slug, conceptSlug) {
  const item = (snapshot?.items || []).find((entry) => entry?.country_code === code);
  if (!item) return countryPath(slug);
  return mapSelectHref({ code, slug: item.country_slug || slug }, item, { conceptSlug }) || countryPath(slug);
}

/** @returns {{ id: string, labelKey: string, to: string }[]} */
export function buildQuickLinks({ locale = 'ru', gdp = null, inflation = null } = {}) {
  const india = { id: 'india-gdp', labelKey: 'z3.quick.indiaGdp', to: snapshotHref(gdp, 'IN', 'india', 'gdp-usd') };
  const turkey = { id: 'turkey-inflation', labelKey: 'z3.quick.turkeyInflation', to: snapshotHref(inflation, 'TR', 'turkey', 'hicp-index') };
  if (locale === 'en') {
    return [
      { id: 'us-inflation', labelKey: 'z3.quick.usInflation', to: snapshotHref(inflation, 'US', 'united-states', 'hicp-index') },
      { id: 'fed-rate', labelKey: 'z3.quick.fedRate', to: indicatorPath('united-states', 'us-policy-rate') },
      { id: 'eur-usd', labelKey: 'z3.quick.eurUsd', to: russiaIndicatorPath('eur-usd') },
      india,
      turkey,
    ];
  }
  return [
    { id: 'usd-rub', labelKey: 'z3.quick.usd', to: russiaIndicatorPath('usd-rub') },
    { id: 'ru-inflation', labelKey: 'z3.quick.ruInflation', to: russiaIndicatorPath('cpi-yoy') },
    { id: 'key-rate', labelKey: 'z3.quick.keyRate', to: russiaIndicatorPath('key-rate') },
    india,
    turkey,
  ];
}
