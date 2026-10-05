import {
  Component, Suspense, lazy, useCallback, useEffect, useId, useMemo, useRef, useState,
} from 'react';
import { Link, useInRouterContext } from 'react-router-dom';
import {
  ArrowUpRight, Check, ChevronDown, ChevronRight, GitCompare, Globe2, Hand, Layers3, Minus, Pause, Play,
  Plus, RotateCcw, Search, Share2, X,
} from 'lucide-react';
import { useLocale, useT } from '../i18n';
import { localizeSource } from '../i18n/viewModeLabels';
import { formatWorldValue, localizeWorldUnit } from '../lib/worldApi';
import { buildWorldColorModel } from '../lib/worldMapColors';
import { valueExtent } from '../lib/regionsMapColors';
import { comparePath, countryPath } from '../lib/sitePaths';
import {
  formatWorldPeriod, resolveWorldPeriodFormat, worldPeriodDates,
} from '../lib/worldMapPeriod';
import { playbackYears, yearTag } from '../lib/planetView';
import { splitUnit, uniformDigits } from '../lib/countryFlag';
import CountryFlag from './CountryFlag';
import PlanetMiniMap from './PlanetMiniMap';
import SourceLink from './SourceLink';
import Spinner from './Spinner';
import YearPicker from './YearPicker';
import './PlanetView.css';

const WorldMap = lazy(() => import('./WorldMap'));

// Адрес для просьбы добавить страну: тот же, что в подвале сайта.
const CONTACT_EMAIL = 'rebeka.ee@yandex.ru';
const HINT_STORAGE_KEY = 'fe_planet_hint_seen';
const HINT_MS = 9000;
const PLAY_STEP_MS = 950;
// Ближе этого расстояния камеры в углу шара показывается мини-карта вида.
const MINIMAP_DISTANCE = 2.6;

function PlanetLink({ href, children, ...props }) {
  const inRouter = useInRouterContext();
  return inRouter ? <Link to={href} {...props}>{children}</Link> : <a href={href} {...props}>{children}</a>;
}

function collectionValue(collection, code) {
  return collection instanceof Map ? collection.get(code) : collection?.[code];
}

function countryAlias(code) {
  return { GB: 'UK', GR: 'EL' }[code] || code;
}

function countryName(country, locale) {
  return (locale === 'en' ? country?.name_en || country?.name : country?.name) || country?.code || '';
}

function hasValue(value) {
  return value != null && value !== '' && Number.isFinite(Number(value));
}

function readHintSeen() {
  try { return window.localStorage.getItem(HINT_STORAGE_KEY) === '1'; } catch { return false; }
}

function writeHintSeen() {
  try { window.localStorage.setItem(HINT_STORAGE_KEY, '1'); } catch { /* private mode: the hint just shows again */ }
}

/** Список на телефоне показывает первые строки, остальное — по кнопке: без вложенной прокрутки, которая «ест» свайп страницы. */
const COMPACT_LIST_ROWS = 7;
const NO_ITEMS = [];

function legendBinRange(bin, locale) {
  const format = (value) => formatWorldValue(value, undefined, locale);
  if (bin.zero) return format(0);
  if (bin.min == null) return '≤ ' + format(bin.max);
  if (bin.max == null) return '≥ ' + format(bin.min);
  return format(bin.min) + '–' + format(bin.max);
}

class SceneBoundary extends Component {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(error) { this.props.onError(error); }
  render() { return this.state.failed ? null : this.props.children; }
}

export default function PlanetView({
  countries = [], valuesByCode: rawValues = null, detailsByCode: rawDetails = null,
  unit: rawUnit = '', metricName: rawMetric = '', periodLabel: rawPeriod = '',
  colorMode: rawColorMode = 'relative', colorDirection: rawDirection = null, defaultScope = 'world',
  initialMode = 'data', showLayerSwitch = false, onSelect,
  years = [], year = null, onYearChange, conceptSlug = '',
  rankingItems: rawRanking = NO_ITEMS, benchmark = null, ratingHref = '',
  // На телефоне список стран под планетой не нужен, если ниже на странице стоит свой полный рейтинг.
  hideListOnPhone = false,
  // Быстрая смена показателя прямо на шаре, «Поделиться видом» и страна, выбранная по ссылке.
  quickConcepts = [], onConceptChange, shareable = false, initialCountry = '',
  // Середина рейтинга по годам: рисуется крошечной линией рядом с числом «в середине рейтинга».
  benchmarkSeries = [],
}) {
  const t = useT();
  const { locale } = useLocale();
  const id = useId().replaceAll(':', '');
  const [mode, setMode] = useState(initialMode === 'earth' ? 'earth' : 'data');
  const [sceneStatus, setSceneStatus] = useState('loading');
  const [sceneGeneration, setSceneGeneration] = useState(0);
  const [PlanetScene, setPlanetScene] = useState(() => lazy(() => import('./PlanetScene')));
  const [selectedCode, setSelectedCode] = useState(null);
  const [hoverCode, setHoverCode] = useState(null);
  // Geography without a public country page: named on hover, never navigable.
  const [hoverPlace, setHoverPlace] = useState(null);
  // Суша без страницы в каталоге, по которой нажали: отвечаем «данных пока нет», а не молчим.
  const [placeCard, setPlaceCard] = useState(null);
  const [query, setQuery] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const [activeOption, setActiveOption] = useState(0);
  const [cameraCommand, setCameraCommand] = useState(null);
  const [comparisonCodes, setComparisonCodes] = useState([]);
  const [touchNavigation, setTouchNavigation] = useState(() => window.matchMedia?.('(pointer: coarse)').matches || false);
  const [listExpanded, setListExpanded] = useState(false);
  // Первое касание шара прекращает самовращение и подсказку.
  const [engaged, setEngaged] = useState(false);
  const [hintSeen, setHintSeen] = useState(readHintSeen);
  const [hintExpired, setHintExpired] = useState(false);
  const [water, setWater] = useState(false);
  const [zoomedView, setZoomedView] = useState(false);
  const [layer, setLayer] = useState('metric');
  const [playing, setPlaying] = useState(false);
  const [shared, setShared] = useState(false);
  const commandId = useRef(0);
  const stageRef = useRef(null);
  const searchInput = useRef(null);
  const searchResults = useRef(null);
  const countryCard = useRef(null);
  const countryList = useRef(null);
  const focusCountryCard = useRef(false);
  const lastView = useRef(null);
  const viewBus = useRef(null);
  const playIndex = useRef(0);
  const playExpected = useRef(null);
  const lastPlayYear = useRef(year);
  const initialApplied = useRef(false);

  useEffect(() => {
    const preference = window.matchMedia?.('(pointer: coarse)');
    if (!preference) return undefined;
    const update = () => { setTouchNavigation(preference.matches); };
    preference.addEventListener('change', update);
    return () => preference.removeEventListener('change', update);
  }, []);

  const countryByCode = useMemo(() => {
    const result = new Map(countries.map((country) => [country.code, country]));
    const entries = rawDetails instanceof Map
      ? rawDetails.entries() : Object.entries(rawDetails || {});
    for (const [key, detail] of entries) {
      const code = detail?.country_code || key;
      if (!result.has(code) && detail?.country_slug) {
        result.set(code, { code, slug: detail.country_slug, name: detail.country_name || code, name_en: detail.country_name_en });
      }
    }
    return result;
  }, [countries, rawDetails]);
  const availableCountries = useMemo(() => [...countryByCode.values()].sort((a, b) =>
    countryName(a, locale).localeCompare(countryName(b, locale), locale)), [countryByCode, locale]);

  // Слой «Охват данных»: цветом показано, сколько показателей есть по каждой стране каталога.
  const coverageValues = useMemo(() => new Map(availableCountries
    .filter((country) => Number(country.indicators_count) > 0)
    .map((country) => [country.code, Number(country.indicators_count)])), [availableCountries]);
  const coverageAvailable = coverageValues.size > 3;
  const coverage = layer === 'coverage' && coverageAvailable;
  const valuesByCode = coverage ? coverageValues : rawValues;
  const detailsByCode = coverage ? null : rawDetails;
  const unit = coverage ? t('w6c.coverage.unit') : rawUnit;
  const metricName = coverage ? t('w6c.coverage.title') : rawMetric;
  const periodLabel = coverage ? '' : rawPeriod;
  const colorMode = coverage ? 'relative' : rawColorMode;
  const colorDirection = coverage ? 'desc' : rawDirection;
  const rankingItems = useMemo(() => (coverage ? NO_ITEMS : rawRanking), [coverage, rawRanking]);

  const searchCountries = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase(locale);
    if (!needle) return availableCountries;
    const code = countryAlias(needle.toUpperCase());
    const fields = (country) => [country.name, country.name_en, country.code, country.slug]
      .map((value) => String(value || '').toLocaleLowerCase(locale));
    const score = (country) => country.code === code || fields(country).includes(needle)
      ? 0 : fields(country).some((value) => value.startsWith(needle)) ? 1 : 2;
    return availableCountries.filter((country) => country.code === code
      || fields(country).some((value) => value.includes(needle))).sort((a, b) => score(a) - score(b));
  }, [availableCountries, locale, query]);
  const valueForCountry = useCallback((country) => collectionValue(valuesByCode, country.code)
    ?? collectionValue(detailsByCode, country.code)?.value, [valuesByCode, detailsByCode]);
  // The surface labels, color scale and country card share the same observation.
  const displayValues = useMemo(() => {
    const result = new Map(valuesByCode instanceof Map ? valuesByCode : Object.entries(valuesByCode || {}));
    for (const country of availableCountries) result.set(country.code, valueForCountry(country));
    return result;
  }, [valuesByCode, availableCountries, valueForCountry]);
  const colorModel = useMemo(() => buildWorldColorModel(displayValues, { mode: colorMode, direction: colorDirection }), [displayValues, colorMode, colorDirection]);
  const extent = useMemo(() => valueExtent(displayValues), [displayValues]);
  // Одна точность на весь экран: карточка, список, подсказки и подписи на шаре показывают число одинаково.
  const digits = useMemo(() => uniformDigits(displayValues.values()), [displayValues]);
  const fmt = useCallback((value) => formatWorldValue(value, digits, locale), [digits, locale]);
  const mapDetails = useMemo(() => detailsByCode instanceof Map ? detailsByCode : new Map(Object.entries(detailsByCode || {})), [detailsByCode]);
  const periodFormat = useMemo(() => resolveWorldPeriodFormat(worldPeriodDates(detailsByCode)), [detailsByCode]);
  const rankedCountries = useMemo(() => {
    const rankByCode = new Map(rankingItems.map((row, index) => [row.country_code, row.rank || index + 1]));
    const entries = availableCountries.map((country) => ({ country, value: valueForCountry(country), rank: rankByCode.get(country.code) }));
    entries.sort((a, b) => {
      const aData = hasValue(a.value); const bData = hasValue(b.value);
      if (aData !== bData) return aData ? -1 : 1;
      if (aData && a.rank && b.rank) return a.rank - b.rank;
      if (aData && Number(a.value) !== Number(b.value)) return (Number(a.value) - Number(b.value)) * (colorDirection === 'asc' ? 1 : -1);
      return countryName(a.country, locale).localeCompare(countryName(b.country, locale), locale);
    });
    let position = 0;
    return entries.map((entry) => {
      if (hasValue(entry.value)) position += 1;
      return { ...entry, rank: hasValue(entry.value) ? entry.rank || position : null };
    });
  }, [availableCountries, rankingItems, valueForCountry, colorDirection, locale]);

  const handleHover = useCallback((code, place = null) => {
    setHoverCode(code || null);
    setHoverPlace(code ? null : place || null);
  }, []);
  // The pointer label follows the cursor through CSS variables: no React re-render per move.
  const trackPointer = useCallback((event) => {
    if (event.pointerType === 'touch') return;
    const stage = event.currentTarget;
    const box = stage.getBoundingClientRect();
    stage.style.setProperty('--planet-pointer-x', Math.round(event.clientX - box.left) + 'px');
    stage.style.setProperty('--planet-pointer-y', Math.round(event.clientY - box.top) + 'px');
  }, []);
  const commandCamera = useCallback((type, countryCode, instant = false) => {
    commandId.current += 1;
    setHoverCode(null);
    setHoverPlace(null);
    setEngaged(true);
    setCameraCommand({ id: commandId.current, type, countryCode, instant });
  }, []);
  const selectCountry = useCallback((code, moveFocus = false, instant = false) => {
    const country = countryByCode.get(code) || countryByCode.get(countryAlias(code));
    if (!country) return;
    if (moveFocus) { focusCountryCard.current = true; searchInput.current?.blur(); }
    setSelectedCode(country.code); setPlaceCard(null); setSearchOpen(false); setQuery('');
    commandCamera('focus', country.code, instant);
  }, [commandCamera, countryByCode]);
  // First press previews the country; pressing the same country again opens it.
  const activateCountry = useCallback((code, moveFocus = false, place = null) => {
    if (!code) {
      // Суша без страницы: «Данных пока нет»; океан просто закрывает карточку.
      setSelectedCode(null);
      setPlaceCard(place?.name ? place : null);
      if (place?.code) commandCamera('focus', place.code);
      return;
    }
    const country = countryByCode.get(code) || countryByCode.get(countryAlias(code));
    if (!country) return;
    if (country.code === selectedCode && country.slug && typeof onSelect === 'function') {
      onSelect(country, collectionValue(detailsByCode, country.code) || null);
      return;
    }
    selectCountry(country.code, moveFocus);
  }, [countryByCode, selectedCode, onSelect, detailsByCode, selectCountry, commandCamera]);
  // Сцена передаёт код страны и, для суши без страницы, её название.
  const handleSceneSelect = useCallback((code, place) => activateCountry(code, false, place), [activateCountry]);
  const handleReady = useCallback(() => setSceneStatus('ready'), []);
  const handleError = useCallback((error) => {
    console.warn('Planet rendering failed:', error);
    setSceneStatus('error'); setHoverCode(null); setHoverPlace(null);
  }, []);
  const handleInteract = useCallback(() => setEngaged(true), []);
  const handleOcean = useCallback((value) => setWater(value), []);
  const handleView = useCallback((view) => {
    lastView.current = view;
    viewBus.current?.(view);
    const near = view.distance < MINIMAP_DISTANCE;
    setZoomedView((previous) => (previous === near ? previous : near));
  }, []);
  const selectedCountry = countryByCode.get(selectedCode) || null;

  // Страна из ссылки «Поделиться видом»: выбирается один раз, когда каталог загружен.
  useEffect(() => {
    if (initialApplied.current || !initialCountry || !countryByCode.size) return;
    const code = String(initialCountry).toUpperCase();
    if (!countryByCode.has(code) && !countryByCode.has(countryAlias(code))) return;
    initialApplied.current = true;
    selectCountry(code, false, true);
  }, [initialCountry, countryByCode, selectCountry]);

  useEffect(() => {
    if (!focusCountryCard.current || !selectedCountry) return;
    focusCountryCard.current = false;
    countryCard.current?.focus({ preventScroll: true });
    // Строку выбрали в списке под планетой: на телефоне возвращаем к ПЛАНЕТЕ (она повернулась, карточка лежит на ней),
    // а не оставляем у таблицы.
    if (typeof window.matchMedia === 'function' && window.matchMedia('(max-width: 700px)').matches) {
      const box = stageRef.current?.getBoundingClientRect();
      if (box && (box.top < 64 || box.bottom > window.innerHeight)) {
        const quiet = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        stageRef.current.scrollIntoView?.({ block: 'start', behavior: quiet ? 'auto' : 'smooth' });
      }
    }
  }, [selectedCountry, cameraCommand]);

  // Подсказка-жест: один раз поверх шара, пока человек его не коснулся.
  const hintVisible = sceneStatus === 'ready' && !engaged && !hintSeen && !hintExpired;
  useEffect(() => {
    if (sceneStatus !== 'ready' || engaged || hintSeen) return undefined;
    const timer = window.setTimeout(() => setHintExpired(true), HINT_MS);
    return () => window.clearTimeout(timer);
  }, [sceneStatus, engaged, hintSeen]);
  useEffect(() => {
    if (!engaged || hintSeen) return;
    writeHintSeen();
    setHintSeen(true);
  }, [engaged, hintSeen]);

  // «Проиграть»: шар перекрашивается по годам, пока не дойдёт до последнего наступившего.
  const playYears = useMemo(() => playbackYears(years), [years]);
  const canPlay = !coverage && playYears.length > 1 && typeof onYearChange === 'function';
  useEffect(() => {
    if (!playing) return undefined;
    // Год сменили вручную (выбор в списке лет): воспроизведение уступает человеку.
    if (year !== lastPlayYear.current) {
      lastPlayYear.current = year;
      if (playExpected.current != null && Number(year) !== playExpected.current) { setPlaying(false); return undefined; }
    }
    const timer = window.setTimeout(() => {
      const next = playYears[playIndex.current + 1];
      if (next == null) { setPlaying(false); playExpected.current = null; return; }
      playIndex.current += 1;
      playExpected.current = next;
      onYearChange(next);
    }, PLAY_STEP_MS);
    return () => window.clearTimeout(timer);
  }, [playing, year, playYears, onYearChange]);
  function togglePlay() {
    if (playing) { setPlaying(false); playExpected.current = null; return; }
    playIndex.current = 0;
    playExpected.current = playYears[0];
    lastPlayYear.current = year;
    setEngaged(true);
    setPlaying(true);
    onYearChange(playYears[0]);
  }

  async function shareView() {
    const url = new URL(window.location.href);
    url.searchParams.delete('q');
    url.searchParams.set('planet', [conceptSlug, year ?? '', selectedCode || ''].join(':'));
    const link = url.toString();
    try {
      if (typeof navigator.share === 'function') { await navigator.share({ title: document.title, url: link }); return; }
      await navigator.clipboard?.writeText(link);
      setShared(true);
      window.setTimeout(() => setShared(false), 2600);
    } catch { /* закрыли окно «Поделиться» */ }
  }

  const selectedRank = selectedCountry ? rankedCountries.find((entry) => entry.country.code === selectedCountry.code)?.rank || null : null;
  const rankTotal = rankedCountries.filter((entry) => entry.rank).length;
  const selectedDetail = selectedCountry ? collectionValue(detailsByCode, selectedCountry.code) || null : null;
  const selectedValue = selectedCountry ? valueForCountry(selectedCountry) : null;
  const selectedPeriod = formatWorldPeriod(selectedDetail?.date, periodFormat) || periodLabel;
  const hoveredCountry = countryByCode.get(hoverCode) || countryByCode.get(countryAlias(hoverCode));
  const displayUnit = localizeWorldUnit(unit, locale);
  // В строках — только короткая единица; длинное пояснение («% экономически активного населения») стоит над списком.
  const rowUnit = splitUnit(displayUnit).short;
  const hasMetric = Boolean(metricName || valuesByCode != null);
  const isMap = sceneStatus === 'error';
  const showKey = !isMap && mode === 'data' && hasMetric;
  const activeCountry = searchCountries[Math.min(activeOption, searchCountries.length - 1)];
  const optionId = (code) => 'planet-' + id + '-country-' + code;
  const comparisonCountries = comparisonCodes.map((code) => countryByCode.get(code)).filter(Boolean);
  const compareReady = Boolean(conceptSlug) && comparisonCountries.length === 2 && comparisonCountries.every((country) => hasValue(valueForCountry(country)));
  const comparisonHref = compareReady ? comparePath() + '?' + new URLSearchParams({ codes: comparisonCountries.map((country) => 'w:' + country.slug + ':' + conceptSlug).join(',') }) : '';
  const selectedPinned = comparisonCodes.includes(selectedCode);
  const canPin = selectedPinned || (selectedCountry?.slug && conceptSlug && hasValue(selectedValue) && comparisonCodes.length < 2);
  const comparisonFull = comparisonCodes.length === 2 && !selectedPinned && hasValue(selectedValue);
  const median = benchmark?.value ?? colorModel.median;
  // Слово «медиана» человеку ничего не говорит: середина списка называется «в середине рейтинга».
  const footerLabel = benchmark?.label && !/медиан|median/i.test(benchmark.label) ? benchmark.label : t('w2.planet.middle');
  // Единая метафора: золото всегда «выше в рейтинге». Слева — хуже, справа — лучше, у каждого края своё число.
  const ranked = colorDirection === 'asc' || colorDirection === 'desc';
  const reversed = colorDirection === 'asc';
  const keyColors = colorModel.bins.map((bin) => bin.color);
  const keyGradient = 'linear-gradient(90deg, ' + (reversed ? [...keyColors].reverse() : keyColors).join(', ') + ')';
  const keyLeft = extent ? (reversed ? extent.max : extent.min) : null;
  const keyRight = extent ? (reversed ? extent.min : extent.max) : null;
  const tag = coverage ? null : yearTag(year, { annual: periodFormat === 'annual' });
  const tagLabel = tag ? t(tag === 'forecast' ? 'w6c.tag.forecast' : 'w6c.tag.estimate') : '';
  const catalogCount = availableCountries.length;
  const trend = useMemo(() => {
    const points = (benchmarkSeries || []).filter((point) => hasValue(point?.value));
    if (coverage || points.length < 3) return null;
    const values = points.map((point) => Number(point.value));
    const low = Math.min(...values);
    const span = Math.max(...values) - low || 1;
    const coords = values.map((value, index) => [2 + (60 * index) / (values.length - 1), 18 - (16 * (value - low)) / span]);
    return {
      line: coords.map(([x, y]) => x.toFixed(1) + ',' + y.toFixed(1)).join(' '),
      last: coords[coords.length - 1],
      from: points[0].year,
      to: points[points.length - 1].year,
    };
  }, [benchmarkSeries, coverage]);
  const compactList = !listExpanded && rankedCountries.length > COMPACT_LIST_ROWS + 1;
  const playTitle = t(playing ? 'w6c.play.stop' : 'w6c.play.start', { from: playYears[0], to: playYears[playYears.length - 1] });
  const shareTitle = t(shared ? 'w6c.share.done' : 'w6c.share');
  const placeMail = placeCard ? 'mailto:' + CONTACT_EMAIL + '?' + new URLSearchParams({
    subject: t('w6c.place.mailSubject', { country: placeCard.name }),
  }).toString().replaceAll('+', '%20') : '';

  function handleSearchKey(event) {
    if (event.key === 'Escape') { setSearchOpen(false); return; }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      if (!searchOpen) { setSearchOpen(true); setActiveOption(0); return; }
      const increment = event.key === 'ArrowDown' ? 1 : -1;
      const index = searchCountries.length ? (activeOption + increment + searchCountries.length) % searchCountries.length : 0;
      setActiveOption(index);
      const nextCountry = searchCountries[index];
      if (nextCountry) searchResults.current?.querySelector('[id="' + optionId(nextCountry.code) + '"]')?.scrollIntoView?.({ block: 'nearest' });
    }
    if (event.key === 'Enter' && searchOpen && activeCountry) {
      event.preventDefault(); selectCountry(activeCountry.code, true, true);
    }
  }
  function retryScene() {
    setPlanetScene(() => lazy(() => import('./PlanetScene')));
    setSceneGeneration((previous) => previous + 1); setSceneStatus('loading');
  }
  function clearSelection() {
    setSelectedCode(null); setPlaceCard(null); setHoverCode(null); setHoverPlace(null); commandCamera('reset');
    countryList.current?.focus({ preventScroll: true });
  }
  function toggleComparison() {
    setComparisonCodes((codes) => codes.includes(selectedCode) ? codes.filter((code) => code !== selectedCode)
      : codes.length < 2 ? [...codes, selectedCode] : codes);
  }
  function chooseComparisonCountry() {
    setQuery(''); setActiveOption(0); setSearchOpen(true);
    searchInput.current?.focus();
  }
  function chooseConcept(slug) {
    setLayer('metric');
    if (slug !== conceptSlug) onConceptChange?.(slug);
  }

  return (
    <div className="planet-host">
      <section className={'planet-view' + (hideListOnPhone ? ' planet-view--no-phone-list' : '')} aria-labelledby={'planet-' + id + '-title'} data-planet-view="true">
        <h3 id={'planet-' + id + '-title'} className="sr-only">{t('planet.title')}</h3>
        {comparisonCountries.length > 0 && <div className="planet-comparison" aria-label={t('planet.comparison')}>
          <span className="planet-comparison-title"><GitCompare size={17} aria-hidden="true" />{t('planet.comparison')}<small>{comparisonCountries.length}/2</small></span>
          <div className="planet-comparison-pair">{comparisonCountries.map((country) => <button type="button" key={country.code} onClick={() => setComparisonCodes((codes) => codes.filter((code) => code !== country.code))}
              aria-label={t('planet.removeComparison', { country: countryName(country, locale) })}>{countryName(country, locale)}<X size={14} aria-hidden="true" /></button>)}
            {comparisonCountries.length === 1 && <button type="button" className="planet-comparison-empty" onClick={chooseComparisonCountry}><Plus size={15} aria-hidden="true" />{t('planet.chooseSecond')}</button>}
          </div>
          {compareReady ? <PlanetLink href={comparisonHref}>{t('planet.showComparison')}<ArrowUpRight size={15} aria-hidden="true" /></PlanetLink> : comparisonCountries.length === 2 && <span role="status">{t('planet.noData')}</span>}
        </div>}
        <div className={'planet-shell' + (showKey ? ' has-key' : '')}>
          <div className="planet-toolbar">
            <div className="planet-search" onBlur={(event) => {
              if (!event.currentTarget.contains(event.relatedTarget)) setSearchOpen(false);
            }}>
              <label className="planet-control-label" htmlFor={'planet-' + id + '-search'}>{t('planet.search')}</label>
              <div className="planet-search-field">
                <Search size={18} aria-hidden="true" />
                <input ref={searchInput} id={'planet-' + id + '-search'} type="text" role="combobox" autoComplete="off" autoCapitalize="none" autoCorrect="off" enterKeyHint="search"
                  placeholder={selectedCountry && !searchOpen ? countryName(selectedCountry, locale) : t('planet.searchPlaceholder')} value={query} aria-expanded={searchOpen} aria-autocomplete="list"
                  aria-controls={searchOpen && searchCountries.length > 0 ? 'planet-' + id + '-results' : undefined}
                  aria-activedescendant={searchOpen && activeCountry ? optionId(activeCountry.code) : undefined}
                  onFocus={() => { setSearchOpen(true); setActiveOption(0); }}
                  onChange={(event) => { setQuery(event.target.value); setActiveOption(0); setSearchOpen(true); }} onKeyDown={handleSearchKey} />
                {query && <button type="button" aria-label={t('planet.clearSearch')} onClick={() => { setQuery(''); setActiveOption(0); searchInput.current?.focus(); }}><X size={16} aria-hidden="true" /></button>}
                <button type="button" aria-label={t('planet.search')} aria-expanded={searchOpen} onClick={() => {
                  if (searchOpen) setSearchOpen(false); else { setSearchOpen(true); searchInput.current?.focus(); }
                }}><ChevronDown size={16} aria-hidden="true" /></button>
              </div>
              {searchOpen && <div className="planet-search-dropdown">
                {searchCountries.length ? <div ref={searchResults} id={'planet-' + id + '-results'} role="listbox" aria-label={t('planet.searchResults')}>
                  {searchCountries.map((country, index) => <button key={country.code} id={optionId(country.code)} type="button" role="option" tabIndex={-1} aria-selected={index === activeOption}
                    onMouseDown={(event) => event.preventDefault()} onMouseEnter={() => setActiveOption(index)} onClick={() => selectCountry(country.code, true)}>
                    <span className="planet-option-name"><CountryFlag code={country.code} />{countryName(country, locale)}</span>
                    <strong>{hasValue(valueForCountry(country)) ? <>{fmt(valueForCountry(country))}{rowUnit && <small>{rowUnit}</small>}</> : <em>{t('planet.noDataLegend')}</em>}</strong>
                  </button>)}
                </div> : <p role="status">{t('planet.noMatches')}</p>}
              </div>}
            </div>
            <div className="planet-display-controls">
              {years.length > 1 && year != null && typeof onYearChange === 'function' && !coverage && <div className="planet-year">
                <span>{t('common.year')}</span>
                <YearPicker years={years} value={year} onChange={onYearChange} label={t('map.timeline.yearOnMap')} />
                {tagLabel && <em className="planet-tag planet-tag--year">{tagLabel}</em>}
              </div>}
              {showLayerSwitch && hasMetric && !isMap && <div className="planet-layer-control"><span className="planet-control-label">{t('planet.viewLabel')}</span><div className="planet-layer-switch" role="group" aria-label={t('planet.layerLabel')}>
                  <button type="button" aria-pressed={mode === 'earth'} onClick={() => { setMode('earth'); setHoverCode(null); setHoverPlace(null); }}><Globe2 size={15} aria-hidden="true" />{t('planet.earth')}</button>
                  <button type="button" aria-pressed={mode === 'data'} onClick={() => { setMode('data'); setHoverCode(null); setHoverPlace(null); }}><Layers3 size={15} aria-hidden="true" />{t('planet.data')}</button>
                </div></div>}
            </div>
          </div>
          <div className="planet-geography">
            <div ref={stageRef} className={'planet-stage' + (isMap ? ' planet-stage--map' : '') + (selectedCountry || placeCard ? ' has-card' : '')} data-scene-ready={!isMap && sceneStatus === 'ready' ? 'true' : 'false'} data-planet-mode={mode} onPointerMove={trackPointer}>
              {isMap ? <div className="planet-map-fallback">
                <div className="planet-fallback-message" role="status"><span>{t('planet.unavailable')}</span><button type="button" onClick={retryScene}>{t('planet.retry')}</button></div>
                <Suspense fallback={<div className="planet-loading" role="status"><Spinner size={19} />{t('planet.loading')}</div>}><WorldMap countries={availableCountries} valuesByCode={displayValues} detailsByCode={mapDetails} unit={unit} metricName={metricName} periodLabel={periodLabel} colorMode={colorMode} colorDirection={colorDirection} defaultScope={defaultScope} onSelect={(country) => selectCountry(country.code, true)} /></Suspense>
              </div> : <>
                <SceneBoundary key={sceneGeneration} onError={handleError}><Suspense fallback={null}>
                  <PlanetScene countries={availableCountries} valuesByCode={displayValues} unit={displayUnit} showValues={hasMetric} colorModel={colorModel} mode={mode} selectedCode={selectedCountry?.code || null}
                    valueDigits={digits} onHover={handleHover} onSelect={handleSceneSelect} onReady={handleReady} onError={handleError} cameraCommand={cameraCommand} defaultScope={defaultScope}
                    interactive={!touchNavigation} touchNavigation={touchNavigation}
                    autoRotate={!engaged && sceneStatus === 'ready'} onInteract={handleInteract} onView={handleView} onOcean={handleOcean} />
                </Suspense></SceneBoundary>
                <div className="planet-orb" aria-hidden="true" />
                {sceneStatus === 'loading' && <div className="planet-loading" role="status"><Spinner size={16} />{t('planet.loading')}</div>}
                {quickConcepts.length > 1 && <div className="planet-quick" role="group" aria-label={t('w6c.quick.label')}>
                  {quickConcepts.map((concept) => <button key={concept.slug} type="button" className={'planet-quick-chip' + (!coverage && concept.slug === conceptSlug ? ' is-active' : '')}
                    aria-pressed={!coverage && concept.slug === conceptSlug} onClick={() => chooseConcept(concept.slug)}>{concept.label}</button>)}
                </div>}
                {playing && year != null && <div className="planet-play-year" role="status" aria-live="polite">{year}{tagLabel && <em className="planet-tag">{tagLabel}</em>}</div>}
                {hintVisible && <div className="planet-gesture-hint" role="note"><Hand size={18} aria-hidden="true" /><span>{t(touchNavigation ? 'w6c.hint.touch' : 'w6c.hint.mouse')}</span></div>}
                {hoveredCountry && <div className="planet-hover-label"><span>{countryName(hoveredCountry, locale)}</span><strong>{hasValue(valueForCountry(hoveredCountry)) ? fmt(valueForCountry(hoveredCountry)) + ' ' + displayUnit : t('planet.noDataLegend')}</strong>
                  <small>{t(hoveredCountry.code === selectedCode ? 'planet.pressToOpen' : 'planet.pressToSelect')}</small></div>}
                {!hoveredCountry && hoverPlace && <div className="planet-hover-label planet-hover-label--muted"><span>{hoverPlace}</span><small>{t('planet.notInCatalog')}</small></div>}
                {zoomedView && <PlanetMiniMap viewBusRef={viewBus} lastViewRef={lastView} label={t('w6c.minimap')} />}
                <div className="planet-camera-controls" role="group" aria-label={t('w2.planet.zoomGroup')}>
                  <button type="button" onClick={() => commandCamera('zoomIn')} aria-label={t('planet.zoomIn')} title={t('planet.zoomIn')} data-tip={t('planet.zoomIn')}><Plus size={18} aria-hidden="true" /></button>
                  <button type="button" onClick={() => commandCamera('zoomOut')} aria-label={t('planet.zoomOut')} title={t('planet.zoomOut')} data-tip={t('planet.zoomOut')}><Minus size={18} aria-hidden="true" /></button>
                  <button type="button" onClick={() => commandCamera('reset')} aria-label={t('planet.reset')} title={t('planet.reset')} data-tip={t('planet.reset')}><RotateCcw size={16} aria-hidden="true" /></button>
                </div>
              </>}
              <div className="planet-stage-bottom">
                {!isMap && <div className="planet-stage-actions">
                  {water && !selectedCountry && <button type="button" className="planet-pill planet-back-to-countries" onClick={() => commandCamera('reset')}><RotateCcw size={15} aria-hidden="true" />{t('w6c.backToCountries')}</button>}
                  {canPlay && <button type="button" className={'planet-round' + (playing ? ' is-active' : '')} aria-pressed={playing} aria-label={playTitle} title={playTitle} data-tip={playTitle} onClick={togglePlay}>
                    {playing ? <Pause size={17} aria-hidden="true" /> : <Play size={17} aria-hidden="true" />}</button>}
                  {coverageAvailable && <button type="button" className={'planet-round' + (coverage ? ' is-active' : '')} aria-pressed={coverage} aria-label={t('w6c.coverage.toggle')} title={t('w6c.coverage.toggle')} data-tip={t('w6c.coverage.toggle')}
                    onClick={() => { setLayer(coverage ? 'metric' : 'coverage'); setPlaying(false); }}><Layers3 size={17} aria-hidden="true" /></button>}
                  {shareable && <button type="button" className={'planet-round' + (shared ? ' is-active' : '')} aria-label={shareTitle} title={shareTitle} data-tip={shareTitle} onClick={shareView}>
                    {shared ? <Check size={17} aria-hidden="true" /> : <Share2 size={17} aria-hidden="true" />}</button>}
                </div>}
                {placeCard && !selectedCountry && <div className="planet-country-card planet-place-card is-selected" role="status">
                  <div className="planet-country-heading"><div><h3>{placeCard.name}</h3></div><button type="button" onClick={() => setPlaceCard(null)} aria-label={t('planet.clearSelection')}><X size={17} aria-hidden="true" /></button></div>
                  <p className="planet-place-text"><span className="planet-soon">{t('w6c.place.soon')}</span>{t('w6c.place.noData')}</p>
                  <div className="planet-country-actions"><a className="planet-open-country" href={placeMail}>{t('w6c.place.ask')}<ArrowUpRight size={15} aria-hidden="true" /></a></div>
                </div>}
                <div ref={countryCard} className={'planet-country-card' + (selectedCountry ? ' is-selected' : '')} tabIndex={-1} aria-live="polite" data-selected-country={selectedCountry?.code || ''}>
                  {selectedCountry && <>
                    <div className="planet-country-heading"><div><CountryFlag code={selectedCountry.code} className="planet-flag-lg" /><h3>{countryName(selectedCountry, locale)}</h3></div><button type="button" onClick={clearSelection} aria-label={t('planet.clearSelection')}><X size={17} aria-hidden="true" /></button></div>
                    {hasMetric && (hasValue(selectedValue) ? <div className="planet-value-line"><strong aria-label={t('planet.value')}>{fmt(selectedValue)}</strong><span>{displayUnit}</span></div> : <p className="planet-no-data"><span className="planet-soon">{t('w6c.place.soon')}</span>{t('planet.noData')}</p>)}
                    {hasMetric && selectedRank && rankTotal > 1 && <p className="planet-rank">{t('w2.planet.rank', { rank: selectedRank, total: rankTotal })}</p>}
                    <div className="planet-country-actions"><button type="button" className="planet-open-country" disabled={!selectedCountry.slug || typeof onSelect !== 'function'} onClick={() => onSelect?.(selectedCountry, selectedDetail)}>{t(selectedDetail?.indicator_code ? 'planet.openIndicator' : 'planet.openCountry')}<ArrowUpRight size={15} aria-hidden="true" /></button>
                      {conceptSlug && !coverage && <button type="button" className="planet-pin-country" aria-pressed={selectedPinned} disabled={!canPin} onClick={toggleComparison} title={t(selectedPinned ? 'planet.removeComparison' : 'planet.addComparison', { country: countryName(selectedCountry, locale) })} aria-describedby={comparisonFull ? 'planet-' + id + '-comparison-full' : undefined}>{selectedPinned ? <Check size={15} aria-hidden="true" /> : <Plus size={15} aria-hidden="true" />}{t(selectedPinned ? 'planet.inComparison' : 'planet.addComparison')}</button>}
                    </div>
                    {conceptSlug && !coverage && comparisonFull && <p className="planet-comparison-limit" id={'planet-' + id + '-comparison-full'}>{t('planet.comparisonFull')}</p>}
                    <div className="planet-country-meta">
                      <div className="planet-country-observation"><span>{metricName}</span><span>{selectedPeriod}{tagLabel && <em className="planet-tag">{tagLabel}</em>}</span></div>
                      {selectedDetail?.source && <div className="planet-source"><SourceLink href={selectedDetail.source_url}>{localizeSource(selectedDetail.source, locale)}</SourceLink></div>}
                      {selectedCountry.slug && <PlanetLink className="planet-all-indicators" href={countryPath(selectedCountry.slug)}>{t('planet.allIndicators')}<ArrowUpRight size={12} aria-hidden="true" /></PlanetLink>}
                    </div>
                  </>}
                </div>
              </div>
            </div>
            {showKey && <div className="planet-key">
              <div className="planet-key-title"><strong>{metricName}</strong>{(periodLabel || tagLabel) && <span>{periodLabel}{tagLabel && <em className="planet-tag">{tagLabel}</em>}</span>}</div>
              <div className="planet-key-bar" style={{ backgroundImage: keyGradient }} aria-hidden="true" />
              {extent && <div className="planet-key-ends">
                <span><small>{t(ranked ? 'w6c.key.worse' : 'w2.planet.keyLow')}</small>{fmt(keyLeft)} {rowUnit || displayUnit}</span>
                <span><small>{t(ranked ? 'w6c.key.better' : 'w2.planet.keyHigh')}</small>{fmt(keyRight)} {rowUnit || displayUnit}</span>
              </div>}
              <p className="planet-key-order">{t(coverage ? 'w6c.key.ruleCoverage' : ranked ? 'w6c.key.rule' : 'w6c.key.ruleValue')}</p>
              <p className="planet-key-note"><i aria-hidden="true" />{t('w6c.key.noData', { count: catalogCount })}</p>
              <details className="planet-scale">
                <summary>{t('planet.legend')}<ChevronDown size={14} aria-hidden="true" /></summary>
                <div className="planet-legend" aria-label={t('planet.legend')}>
                  <p>{t(colorModel.kind === 'diverging' ? 'world.map.scaleZero' : 'world.map.scaleMedian')}</p>
                  <div className="planet-legend-bins">{colorModel.bins.map((bin, index) => <div key={index}><i style={{ backgroundColor: bin.color }} aria-hidden="true" /><span>{t(bin.labelKey)}</span><strong>{legendBinRange(bin, locale)} {displayUnit}</strong></div>)}</div>
                  <small><i aria-hidden="true" />{t('planet.noDataLegend')}</small>
                </div>
              </details>
            </div>}
          </div>
          <aside className="planet-info" aria-label={t('planet.country')}>
            <div className="planet-list-heading"><div><h4>{t('planet.countries')}</h4>{metricName && <p>{metricName}{displayUnit && !rowUnit ? ', ' + displayUnit : ''}</p>}</div><span>{periodLabel}</span></div>
            <div ref={countryList} className={'planet-country-list' + (compactList ? ' is-compact' : '')} role="group" tabIndex={-1} aria-label={t('planet.countries')}>
              {rankedCountries.map(({ country, value, rank }) => <button key={country.code} type="button" className={selectedCode === country.code ? 'is-selected' : ''} aria-pressed={selectedCode === country.code} onClick={() => activateCountry(country.code, true)}
                title={selectedCode === country.code ? t('planet.pressToOpen') : undefined}>
                <span className="planet-list-rank">{rank || '—'}</span><span className="planet-list-name"><CountryFlag code={country.code} />{countryName(country, locale)}</span>
                <strong>{hasValue(value) ? <>{fmt(value)}{rowUnit && <small>{rowUnit}</small>}</> : <em>{t('planet.noDataLegend')}</em>}</strong><ChevronRight size={14} aria-hidden="true" />
              </button>)}
            </div>
            {rankedCountries.length > COMPACT_LIST_ROWS + 1 && <button type="button" className="planet-list-more" aria-expanded={listExpanded} onClick={() => setListExpanded((open) => !open)}>
              {listExpanded ? t('w2.planet.showLess') : t('w2.planet.showAll', { count: rankedCountries.length })}<ChevronDown size={14} aria-hidden="true" />
            </button>}
            <div className="planet-list-footer">{hasValue(median) && hasMetric && <span>{footerLabel}: <strong>{fmt(median)} {rowUnit || displayUnit}</strong>{trend && <svg className="planet-trend" viewBox="0 0 64 20" role="img" aria-label={t('w6c.trend.label', { from: trend.from, to: trend.to })}><polyline points={trend.line} /><circle cx={trend.last[0]} cy={trend.last[1]} r="2.2" /></svg>}</span>}{ratingHref && <PlanetLink href={ratingHref}>{t('planet.fullRating')}<ArrowUpRight size={13} aria-hidden="true" /></PlanetLink>}</div>
          </aside>
        </div>
      </section>
    </div>
  );
}
