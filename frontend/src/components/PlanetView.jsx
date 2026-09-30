import {
  Component, Suspense, lazy, useCallback, useEffect, useId, useMemo, useRef, useState,
} from 'react';
import {
  ArrowUpRight, Check, ChevronDown, Globe2, GitCompare, Layers3,
  LoaderCircle, Minus, Move, Plus, RotateCcw, Search, X,
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
import SourceLink from './SourceLink';
import './PlanetView.css';

const WorldMap = lazy(() => import('./WorldMap'));

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
  countries = [], valuesByCode = null, detailsByCode = null,
  unit = '', metricName = '', periodLabel = '',
  colorMode = 'relative', colorDirection = null, defaultScope = 'world',
  initialMode = 'earth', onSelect,
  years = [], year = null, onYearChange, conceptSlug = '',
  rankingItems = [], benchmark = null, ratingHref = '',
}) {
  const t = useT();
  const { locale } = useLocale();
  const id = useId().replaceAll(':', '');
  const [mode, setMode] = useState(initialMode === 'data' ? 'data' : 'earth');
  const [sceneStatus, setSceneStatus] = useState('loading');
  const [sceneGeneration, setSceneGeneration] = useState(0);
  const [PlanetScene, setPlanetScene] = useState(() => lazy(() => import('./PlanetScene')));
  const [selectedCode, setSelectedCode] = useState(null);
  const [hoverCode, setHoverCode] = useState(null);
  const [query, setQuery] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const [activeOption, setActiveOption] = useState(0);
  const [cameraCommand, setCameraCommand] = useState(null);
  const [comparisonCodes, setComparisonCodes] = useState([]);
  const [touchNavigation, setTouchNavigation] = useState(() => window.matchMedia?.('(pointer: coarse)').matches || false);
  const [interactiveTouch, setInteractiveTouch] = useState(false);
  const commandId = useRef(0);
  const searchInput = useRef(null);
  const searchResults = useRef(null);
  const countryCard = useRef(null);
  const focusCountryCard = useRef(false);

  useEffect(() => {
    const preference = window.matchMedia?.('(pointer: coarse)');
    if (!preference) return undefined;
    const update = () => { setTouchNavigation(preference.matches); setInteractiveTouch(false); };
    preference.addEventListener('change', update);
    return () => preference.removeEventListener('change', update);
  }, []);

  const countryByCode = useMemo(() => {
    const result = new Map(countries.map((country) => [country.code, country]));
    const entries = detailsByCode instanceof Map
      ? detailsByCode.entries() : Object.entries(detailsByCode || {});
    for (const [key, detail] of entries) {
      const code = detail?.country_code || key;
      if (!result.has(code) && detail?.country_slug) {
        result.set(code, { code, slug: detail.country_slug, name: detail.country_name || code, name_en: detail.country_name_en });
      }
    }
    return result;
  }, [countries, detailsByCode]);
  const availableCountries = useMemo(() => [...countryByCode.values()].sort((a, b) =>
    countryName(a, locale).localeCompare(countryName(b, locale), locale)), [countryByCode, locale]);
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
  const colorModel = useMemo(() => buildWorldColorModel(valuesByCode, { mode: colorMode, direction: colorDirection }), [valuesByCode, colorMode, colorDirection]);
  const extent = useMemo(() => valueExtent(valuesByCode), [valuesByCode]);
  const mapDetails = useMemo(() => detailsByCode instanceof Map ? detailsByCode : new Map(Object.entries(detailsByCode || {})), [detailsByCode]);
  const periodFormat = useMemo(() => resolveWorldPeriodFormat(worldPeriodDates(detailsByCode)), [detailsByCode]);
  const valueForCountry = useCallback((country) => collectionValue(valuesByCode, country.code)
    ?? collectionValue(detailsByCode, country.code)?.value, [valuesByCode, detailsByCode]);
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

  const commandCamera = useCallback((type, countryCode, instant = false) => {
    commandId.current += 1;
    setHoverCode(null);
    setCameraCommand({ id: commandId.current, type, countryCode, instant });
  }, []);
  const selectCountry = useCallback((code, moveFocus = false, instant = false) => {
    const country = countryByCode.get(code) || countryByCode.get(countryAlias(code));
    if (!country) return;
    if (moveFocus) { focusCountryCard.current = true; searchInput.current?.blur(); }
    setSelectedCode(country.code); setSearchOpen(false); setQuery('');
    commandCamera('focus', country.code, instant);
  }, [commandCamera, countryByCode]);
  const handleReady = useCallback(() => setSceneStatus('ready'), []);
  const handleError = useCallback((error) => {
    console.warn('Planet rendering failed:', error);
    setSceneStatus('error'); setHoverCode(null); setInteractiveTouch(false);
  }, []);
  const selectedCountry = countryByCode.get(selectedCode) || null;
  useEffect(() => {
    if (focusCountryCard.current && selectedCountry && countryCard.current) {
      focusCountryCard.current = false;
      countryCard.current.focus({ preventScroll: true });
    }
  }, [selectedCountry, cameraCommand]);
  const selectedDetail = selectedCountry ? collectionValue(detailsByCode, selectedCountry.code) || null : null;
  const selectedValue = selectedCountry ? valueForCountry(selectedCountry) : null;
  const selectedPeriod = formatWorldPeriod(selectedDetail?.date, periodFormat) || periodLabel;
  const hoveredCountry = countryByCode.get(hoverCode) || countryByCode.get(countryAlias(hoverCode));
  const displayUnit = localizeWorldUnit(unit, locale);
  const hasMetric = Boolean(metricName || valuesByCode != null);
  const isMap = sceneStatus === 'error';
  const activeCountry = searchCountries[Math.min(activeOption, searchCountries.length - 1)];
  const optionId = (code) => 'planet-' + id + '-country-' + code;
  const comparisonCountries = comparisonCodes.map((code) => countryByCode.get(code)).filter(Boolean);
  const compareReady = Boolean(conceptSlug) && comparisonCountries.length === 2 && comparisonCountries.every((country) => hasValue(valueForCountry(country)));
  const comparisonHref = compareReady ? comparePath() + '?' + new URLSearchParams({ codes: comparisonCountries.map((country) => 'w:' + country.slug + ':' + conceptSlug).join(',') }) : '';
  const selectedPinned = comparisonCodes.includes(selectedCode);
  const canPin = selectedCountry?.slug && conceptSlug && hasValue(selectedValue) && (selectedPinned || comparisonCodes.length < 2);
  const median = benchmark?.value ?? colorModel.median;

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
    setSelectedCode(null); setHoverCode(null); commandCamera('reset');
  }
  function toggleComparison() {
    setComparisonCodes((codes) => codes.includes(selectedCode) ? codes.filter((code) => code !== selectedCode)
      : codes.length < 2 ? [...codes, selectedCode] : codes);
  }

  return (
    <section className="planet-view" aria-labelledby={'planet-' + id + '-title'} data-planet-view="true">
      <h3 id={'planet-' + id + '-title'} className="sr-only">{t('planet.title')}</h3>
      <div className="planet-toolbar">
        <div className="planet-search" onBlur={(event) => {
          if (!event.currentTarget.contains(event.relatedTarget)) setSearchOpen(false);
        }}>
          <label className="sr-only" htmlFor={'planet-' + id + '-search'}>{t('planet.search')}</label>
          <div className="planet-search-field">
            <Search size={18} aria-hidden="true" />
            <input ref={searchInput} id={'planet-' + id + '-search'} type="text" role="combobox" autoComplete="off" autoCapitalize="none" autoCorrect="off" enterKeyHint="search"
              placeholder={t('planet.searchPlaceholder')} value={query} aria-expanded={searchOpen} aria-autocomplete="list"
              aria-controls={searchOpen && searchCountries.length > 0 ? 'planet-' + id + '-results' : undefined}
              aria-activedescendant={searchOpen && activeCountry ? optionId(activeCountry.code) : undefined}
              onFocus={() => { setSearchOpen(true); setActiveOption(0); }}
              onChange={(event) => { setQuery(event.target.value); setActiveOption(0); setSearchOpen(true); }} onKeyDown={handleSearchKey} />
            <button type="button" aria-label={t('planet.search')} aria-expanded={searchOpen} onClick={() => {
              if (searchOpen) setSearchOpen(false); else { setSearchOpen(true); searchInput.current?.focus(); }
            }}><ChevronDown size={16} aria-hidden="true" /></button>
          </div>
          {searchOpen && <div className="planet-search-dropdown">
            {searchCountries.length ? <div ref={searchResults} id={'planet-' + id + '-results'} role="listbox" aria-label={t('planet.searchResults')}>
              {searchCountries.map((country, index) => <button key={country.code} id={optionId(country.code)} type="button" role="option" tabIndex={-1} aria-selected={index === activeOption}
                onMouseDown={(event) => event.preventDefault()} onMouseEnter={() => setActiveOption(index)} onClick={() => selectCountry(country.code, true)}>
                <span>{countryName(country, locale)}<small>{country.code}</small></span>
                <strong>{hasValue(valueForCountry(country)) ? formatWorldValue(valueForCountry(country), undefined, locale) : t('planet.noDataLegend')}</strong>
              </button>)}
            </div> : <p role="status">{t('planet.noMatches')}</p>}
          </div>}
        </div>
        <div className="planet-display-controls">
          {years.length > 1 && year != null && typeof onYearChange === 'function' && <label className="planet-year">
            <span>{t('common.year')}</span><select aria-label={t('map.timeline.yearOnMap')} value={year} onChange={(event) => onYearChange(Number(event.target.value))}>
              {[...years].reverse().map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>}
          {hasMetric && !isMap && <div className="planet-layer-switch" role="group" aria-label={t('planet.layerLabel')}>
            <button type="button" aria-pressed={mode === 'earth'} onClick={() => { setMode('earth'); setHoverCode(null); }}><Globe2 size={15} aria-hidden="true" />{t('planet.earth')}</button>
            <button type="button" aria-pressed={mode === 'data'} onClick={() => { setMode('data'); setHoverCode(null); }}><Layers3 size={15} aria-hidden="true" />{t('planet.data')}</button>
          </div>}
        </div>
      </div>
      {comparisonCountries.length > 0 && <div className="planet-comparison" aria-label={t('planet.comparison')}>
        <GitCompare size={16} aria-hidden="true" />
        {comparisonCountries.map((country) => <button type="button" key={country.code} onClick={() => setComparisonCodes((codes) => codes.filter((code) => code !== country.code))}
          aria-label={t('planet.removeComparison', { country: countryName(country, locale) })}>{countryName(country, locale)}<X size={13} aria-hidden="true" /></button>)}
        {compareReady ? <a href={comparisonHref}>{t('planet.showComparison')}<ArrowUpRight size={14} aria-hidden="true" /></a> : <span>{t(comparisonCountries.length === 2 ? 'planet.noData' : 'planet.chooseSecond')}</span>}
      </div>}
      <div className="planet-shell">
        <div className="planet-geography">
          <div className={'planet-stage' + (isMap ? ' planet-stage--map' : '')} data-scene-ready={!isMap && sceneStatus === 'ready' ? 'true' : 'false'} data-planet-mode={mode}>
            {isMap ? <div className="planet-map-fallback">
              <div className="planet-fallback-message" role="status"><span>{t('planet.unavailable')}</span><button type="button" onClick={retryScene}>{t('planet.retry')}</button></div>
              <Suspense fallback={<div className="planet-loading">{t('planet.loading')}</div>}><WorldMap countries={availableCountries} valuesByCode={valuesByCode} detailsByCode={mapDetails} unit={unit} metricName={metricName} periodLabel={periodLabel} colorMode={colorMode} colorDirection={colorDirection} defaultScope={defaultScope} onSelect={(country) => selectCountry(country.code, true)} /></Suspense>
            </div> : <>
              <SceneBoundary key={sceneGeneration} onError={handleError}><Suspense fallback={null}>
                <PlanetScene countries={availableCountries} valuesByCode={valuesByCode} colorModel={colorModel} mode={mode} selectedCode={selectedCountry?.code || null}
                  onHover={setHoverCode} onSelect={selectCountry} onReady={handleReady} onError={handleError} cameraCommand={cameraCommand} defaultScope={defaultScope}
                  interactive={!touchNavigation || interactiveTouch} touchNavigation={touchNavigation} />
              </Suspense></SceneBoundary>
              {sceneStatus === 'loading' && <div className="planet-loading" role="status"><LoaderCircle size={19} aria-hidden="true" />{t('planet.loading')}</div>}
              <div className="planet-camera-controls">
                <button type="button" onClick={() => commandCamera('zoomIn')} aria-label={t('planet.zoomIn')} title={t('planet.zoomIn')}><Plus size={18} aria-hidden="true" /></button>
                <button type="button" onClick={() => commandCamera('zoomOut')} aria-label={t('planet.zoomOut')} title={t('planet.zoomOut')}><Minus size={18} aria-hidden="true" /></button>
                <button type="button" onClick={() => commandCamera('reset')} aria-label={t('planet.reset')} title={t('planet.reset')}><RotateCcw size={16} aria-hidden="true" /></button>
              </div>
              {touchNavigation && <button type="button" className={'planet-navigation-toggle' + (interactiveTouch ? ' is-active' : '')} aria-pressed={interactiveTouch} onClick={() => setInteractiveTouch((active) => !active)}>
                {interactiveTouch ? <Check size={15} aria-hidden="true" /> : <Move size={15} aria-hidden="true" />}{t(interactiveTouch ? 'planet.doneRotating' : 'planet.rotate')}
              </button>}
              {hoveredCountry && <div className="planet-hover-label"><span>{countryName(hoveredCountry, locale)}</span><strong>{hasValue(valueForCountry(hoveredCountry)) ? formatWorldValue(valueForCountry(hoveredCountry), undefined, locale) + ' ' + displayUnit : t('planet.noDataLegend')}</strong></div>}
              {!touchNavigation && <p className="planet-stage-caption">{t('planet.gesture')}</p>}
            </>}
          </div>
          {!isMap && mode === 'data' && hasMetric && <details className="planet-scale">
            <summary>{t('planet.legend')}{extent && <span>{formatWorldValue(extent.min, undefined, locale)}–{formatWorldValue(extent.max, undefined, locale)} {displayUnit}</span>}<ChevronDown size={14} aria-hidden="true" /></summary>
            <div className="planet-legend" aria-label={t('planet.legend')}>
              <p>{t(colorModel.kind === 'diverging' ? 'world.map.scaleZero' : 'world.map.scaleMedian')}</p>
              <div className="planet-legend-bins">{colorModel.bins.map((bin, index) => <div key={index}><i style={{ backgroundColor: bin.color }} aria-hidden="true" /><span>{t(bin.labelKey)}</span><strong>{legendBinRange(bin, locale)} {displayUnit}</strong></div>)}</div>
              <small><i aria-hidden="true" />{t('planet.noDataLegend')}</small>
            </div>
          </details>}
        </div>
        <aside className="planet-info" aria-label={t('planet.country')}>
          <div ref={countryCard} className={'planet-country-card' + (selectedCountry ? ' is-selected' : '')} tabIndex={-1} aria-live="polite" data-selected-country={selectedCountry?.code || ''}>
            {selectedCountry && <>
              <div className="planet-country-heading"><div><span>{selectedCountry.code}</span><h3>{countryName(selectedCountry, locale)}</h3></div><button type="button" onClick={clearSelection} aria-label={t('planet.clearSelection')}><X size={17} aria-hidden="true" /></button></div>
              <div className="planet-country-observation"><span>{metricName}</span><span>{selectedPeriod}</span></div>
              {hasMetric && (hasValue(selectedValue) ? <div className="planet-value-line"><strong aria-label={t('planet.value')}>{formatWorldValue(selectedValue, undefined, locale)}</strong><span>{displayUnit}</span></div> : <p className="planet-no-data">{t('planet.noData')}</p>)}
              {selectedDetail?.source && <div className="planet-source"><SourceLink href={selectedDetail.source_url}>{localizeSource(selectedDetail.source, locale)}</SourceLink></div>}
              <div className="planet-country-actions"><button type="button" className="planet-open-country" disabled={!selectedCountry.slug || typeof onSelect !== 'function'} onClick={() => onSelect?.(selectedCountry, selectedDetail)}>{t(selectedDetail?.indicator_code ? 'planet.openIndicator' : 'planet.openCountry')}<ArrowUpRight size={15} aria-hidden="true" /></button>
                {conceptSlug && <button type="button" className="planet-pin-country" aria-pressed={selectedPinned} disabled={!canPin} onClick={toggleComparison} title={t('planet.addComparison')}><GitCompare size={15} aria-hidden="true" />{t(selectedPinned ? 'planet.inComparison' : 'planet.addComparison')}</button>}
              </div>
              {selectedCountry.slug && <a className="planet-all-indicators" href={countryPath(selectedCountry.slug)}>{t('planet.allIndicators')}<ArrowUpRight size={12} aria-hidden="true" /></a>}
            </>}
          </div>
          <div className="planet-list-heading"><h4>{metricName || t('planet.countries')}</h4><span>{periodLabel}{displayUnit ? ', ' + displayUnit : ''}</span></div>
          <div className="planet-country-list" role="group" aria-label={t('planet.countries')}>
            {rankedCountries.map(({ country, value, rank }) => <button key={country.code} type="button" className={selectedCode === country.code ? 'is-selected' : ''} aria-pressed={selectedCode === country.code} onClick={() => selectCountry(country.code, true)}>
              <span className="planet-list-rank">{rank || '—'}</span><span className="planet-list-name">{countryName(country, locale)}</span><strong>{hasValue(value) ? formatWorldValue(value, undefined, locale) : t('planet.noDataLegend')}</strong>
            </button>)}
          </div>
          <div className="planet-list-footer">{hasValue(median) && hasMetric && <span>{benchmark?.label || t('planet.median')}: <strong>{formatWorldValue(median, undefined, locale)} {displayUnit}</strong></span>}{ratingHref && <a href={ratingHref}>{t('planet.fullRating')}<ArrowUpRight size={13} aria-hidden="true" /></a>}</div>
        </aside>
      </div>
      <p className="planet-attribution">{t('planet.imageryCredit')} <a href="https://www.solarsystemscope.com/textures/" target="_blank" rel="noopener noreferrer">Solar System Scope</a>, <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener noreferrer">CC BY 4.0</a>. {t('planet.imageryAdapted')}</p>
    </section>
  );
}
