import { geoArea, geoCentroid, geoContains } from 'd3-geo';
import { feature as topologyFeature } from 'topojson-client';
import { numericId, WORLD_FEATURES } from './worldTopology';

// UN M49 → ISO alpha-2, verified 2026-09-30:
// https://unstats.un.org/unsd/methodology/m49/overview/
// Taiwan is present in the atlas as ISO 158; Kosovo uses the project's XK key.
const NUMERIC_TO_ISO = Object.freeze(Object.fromEntries(`
004:AF 008:AL 010:AQ 012:DZ 016:AS 020:AD 024:AO 028:AG 031:AZ 032:AR 036:AU 040:AT
044:BS 048:BH 050:BD 051:AM 052:BB 056:BE 060:BM 064:BT 068:BO 070:BA 072:BW 074:BV
076:BR 084:BZ 086:IO 090:SB 092:VG 096:BN 100:BG 104:MM 108:BI 112:BY 116:KH 120:CM
124:CA 132:CV 136:KY 140:CF 144:LK 148:TD 152:CL 156:CN 158:TW 162:CX 166:CC 170:CO
174:KM 175:YT 178:CG 180:CD 184:CK 188:CR 191:HR 192:CU 196:CY 203:CZ 204:BJ 208:DK
212:DM 214:DO 218:EC 222:SV 226:GQ 231:ET 232:ER 233:EE 234:FO 238:FK 239:GS 242:FJ
246:FI 248:AX 250:FR 254:GF 258:PF 260:TF 262:DJ 266:GA 268:GE 270:GM 275:PS 276:DE
288:GH 292:GI 296:KI 300:GR 304:GL 308:GD 312:GP 316:GU 320:GT 324:GN 328:GY 332:HT
334:HM 336:VA 340:HN 344:HK 348:HU 352:IS 356:IN 360:ID 364:IR 368:IQ 372:IE 376:IL
380:IT 383:XK 384:CI 388:JM 392:JP 398:KZ 400:JO 404:KE 408:KP 410:KR 414:KW 417:KG
418:LA 422:LB 426:LS 428:LV 430:LR 434:LY 438:LI 440:LT 442:LU 446:MO 450:MG 454:MW
458:MY 462:MV 466:ML 470:MT 474:MQ 478:MR 480:MU 484:MX 492:MC 496:MN 498:MD 499:ME
500:MS 504:MA 508:MZ 512:OM 516:NA 520:NR 524:NP 528:NL 531:CW 533:AW 534:SX 535:BQ
540:NC 548:VU 554:NZ 558:NI 562:NE 566:NG 570:NU 574:NF 578:NO 580:MP 581:UM 583:FM
584:MH 585:PW 586:PK 591:PA 598:PG 600:PY 604:PE 608:PH 612:PN 616:PL 620:PT 624:GW
626:TL 630:PR 634:QA 638:RE 642:RO 643:RU 646:RW 652:BL 654:SH 659:KN 660:AI 662:LC
663:MF 666:PM 670:VC 674:SM 678:ST 682:SA 686:SN 688:RS 690:SC 694:SL 702:SG 703:SK
704:VN 705:SI 706:SO 710:ZA 716:ZW 724:ES 728:SS 729:SD 732:EH 740:SR 744:SJ 748:SZ
752:SE 756:CH 760:SY 762:TJ 764:TH 768:TG 772:TK 776:TO 780:TT 784:AE 788:TN 792:TR
795:TM 796:TC 798:TV 800:UG 804:UA 807:MK 818:EG 826:GB 831:GG 832:JE 833:IM 834:TZ
840:US 850:VI 854:BF 858:UY 860:UZ 862:VE 876:WF 882:WS 887:YE 894:ZM
`.trim().split(/\s+/).map((pair) => pair.split(':'))));

const ISO_CODES = new Set(Object.values(NUMERIC_TO_ISO));
const CODE_ALIASES = { UK: 'GB', EL: 'GR' };
const UNCODED_NAMES_RU = {
  'N. Cyprus': 'Северный Кипр',
  Somaliland: 'Сомалиленд',
  'Indian Ocean Ter.': 'Территории Индийского океана',
  'Siachen Glacier': 'Ледник Сиачен',
};
const ATLAS_IMPORT = {
  detailed: () => import('world-atlas/countries-50m.json'),
  fine: () => import('world-atlas/countries-10m.json'),
};
const atlasRequests = new Map();
const RAD = Math.PI / 180;
const DEG = 180 / Math.PI;

/** Canonical geometry key. Keep the catalog's original country.code for API reads. */
export function normalizePlanetCountryCode(value) {
  const raw = String(value ?? '').trim().toUpperCase();
  if (/^\d{1,3}$/.test(raw)) return NUMERIC_TO_ISO[numericId(raw)] || null;
  const code = CODE_ALIASES[raw] || raw;
  return ISO_CODES.has(code) ? code : null;
}

export function countryCodeForFeature(item) {
  const properties = item?.properties || {};
  for (const key of ['iso_a2', 'ISO_A2', 'alpha2']) {
    const code = normalizePlanetCountryCode(properties[key]);
    if (code) return code;
  }
  return normalizePlanetCountryCode(item?.id)
    || (properties.name === 'Kosovo' ? 'XK' : null);
}

/**
 * Raw atlas features, including islands, duplicate IDs and uncoded territories.
 * worldTopology.loadWorldFeatures intentionally collapses those for silhouettes.
 * null means the optional atlas failed; the renderer can retain its base atlas.
 */
export function loadPlanetFeatures(level = 'detailed') {
  if (level === 'base') return Promise.resolve(WORLD_FEATURES);
  if (!ATLAS_IMPORT[level]) return Promise.resolve(null);
  if (!atlasRequests.has(level)) {
    atlasRequests.set(level, ATLAS_IMPORT[level]()
      .then((module) => {
        const topology = module.default || module;
        return topologyFeature(topology, topology.objects.countries).features;
      })
      .catch(() => {
        atlasRequests.delete(level);
        return null;
      }));
  }
  return atlasRequests.get(level);
}

function validLonLat(point) {
  return Array.isArray(point) && point.length >= 2
    && Number.isFinite(point[0]) && Number.isFinite(point[1])
    && Math.abs(point[1]) <= 90;
}

function wrapLongitude(longitude) {
  return ((longitude + 180) % 360 + 360) % 360 - 180;
}

/** +Y is north, longitude 0 is +Z, longitude 90 east is +X. */
export function lonLatToSphere(point, radius = 1) {
  if (!validLonLat(point) || !Number.isFinite(radius) || radius <= 0) return null;
  const longitude = point[0] * RAD;
  const latitude = point[1] * RAD;
  const horizontal = radius * Math.cos(latitude);
  return [horizontal * Math.sin(longitude), radius * Math.sin(latitude), horizontal * Math.cos(longitude)];
}

/** Accept an array or a Three.js-style {x, y, z}; input radius need not be 1. */
export function sphereToLonLat(vector) {
  const [x, y, z] = Array.isArray(vector)
    ? vector
    : [vector?.x, vector?.y, vector?.z];
  if (![x, y, z].every(Number.isFinite)) return null;
  const radius = Math.hypot(x, y, z);
  if (!radius) return null;
  return [wrapLongitude(Math.atan2(x, z) * DEG), Math.asin(Math.max(-1, Math.min(1, y / radius))) * DEG];
}

/**
 * Camera target: spherical centroid of the largest polygon. This avoids averaging
 * longitudes across ±180 or dragging France's camera toward an overseas island.
 * Picking and borders still use the unmodified full geometry.
 */
export function countryFocusLonLat(item) {
  const geometry = item?.type === 'Feature' ? item.geometry : item;
  if (!geometry || !['Polygon', 'MultiPolygon'].includes(geometry.type)) return null;
  const polygons = geometry.type === 'Polygon'
    ? [geometry]
    : geometry.coordinates.map((coordinates) => ({ type: 'Polygon', coordinates }));
  const dominant = polygons.reduce((best, polygon) => {
    const area = geoArea(polygon);
    return !best || area > best.area ? { polygon, area } : best;
  }, null)?.polygon;
  if (!dominant) return null;
  const centroid = geoCentroid(dominant);
  if (validLonLat(centroid)) return [wrapLongitude(centroid[0]), centroid[1]];
  const first = dominant.coordinates?.[0]?.[0];
  return validLonLat(first) ? [wrapLongitude(first[0]), first[1]] : null;
}

/**
 * Adapter independent of React/WebGL. `code` is ISO, `dataCode` retains UK/EL;
 * `country` is the original catalog object, or null when no public route exists.
 * Example: bindPlanetCountries(countries, features, { locale: 'en' }).
 */
export function bindPlanetCountries(countries = [], features = WORLD_FEATURES, { locale = 'ru' } = {}) {
  const countryByCode = new Map();
  for (const country of countries) {
    const code = normalizePlanetCountryCode(country?.code);
    if (code && !countryByCode.has(code)) countryByCode.set(code, country);
  }
  const displayNames = typeof Intl.DisplayNames === 'function'
    ? new Intl.DisplayNames([locale === 'en' ? 'en' : 'ru'], { type: 'region', fallback: 'none' })
    : null;
  return features.filter((item) => ['Polygon', 'MultiPolygon'].includes(item?.geometry?.type))
    .map((item, index) => {
      const code = countryCodeForFeature(item);
      const country = code ? countryByCode.get(code) || null : null;
      const atlasName = item.properties?.name || code || '';
      const countryName = locale === 'en'
        ? country?.name_en || country?.name
        : country?.name || country?.name_ru;
      const name = countryName
        || (code && displayNames?.of(code))
        || (locale !== 'en' && UNCODED_NAMES_RU[atlasName])
        || atlasName;
      return {
        id: `${item.id ?? 'uncoded'}:${atlasName || index}`,
        code,
        dataCode: country?.code || code,
        country,
        feature: item,
        name,
        focus: countryFocusLonLat(item),
      };
    });
}

/** The renderer must raycast the visible globe first; this resolves its surface point. */
export function pickPlanetCountry(entries, point) {
  if (!validLonLat(point)) return null;
  const normalized = [wrapLongitude(point[0]), point[1]];
  return entries.find((entry) => entry.feature && geoContains(entry.feature, normalized)) || null;
}
