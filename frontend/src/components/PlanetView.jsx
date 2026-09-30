import {
  Component, Suspense, lazy, useCallback, useEffect, useId, useMemo, useRef, useState,
} from 'react';
import {
  ArrowUpRight, ChevronDown, Globe2, Layers3, LoaderCircle, Map as MapIcon,
  Minus, Plus, RotateCcw, Search, X,
} from 'lucide-react';
import { useLocale, useT } from '../i18n';
import { localizeSource } from '../i18n/viewModeLabels';
import { formatWorldValue, localizeWorldUnit } from '../lib/worldApi';
import { buildWorldColorModel } from '../lib/worldMapColors';
import { valueExtent } from '../lib/regionsMapColors';
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
  if (bin.min == null) return `≤ ${format(bin.max)}`;
  if (bin.max == null) return `≥ ${format(bin.min)}`;
  return `${format(bin.min)}–${format(bin.max)}`;
}

class SceneBoundary extends Component {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error) {
    this.props.onError(error);
  }

  render() {
    return this.state.failed ? null : this.props.children;
  }
}

export default function PlanetView({
  countries = [],
  valuesByCode = null,
  detailsByCode = null,
  unit = '',
  metricName = '',
  periodLabel = '',
  colorMode = 'relative',
  colorDirection = null,
  defaultScope = 'world',
  initialMode = 'earth',
  onSelect,
}) {
  const t = useT();
  const { locale } = useLocale();
  const id = useId().replaceAll(':', '');
  const [representation, setRepresentation] = useState('planet');
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
  const commandId = useRef(0);
  const searchInput = useRef(null);
  const searchResults = useRef(null);
  const countryCard = useRef(null);
  const focusCountryCard = useRef(false);

  // A map slice can include a country before it appears in the catalogue.
  // Preserve that API row so search and the scene share one navigable pool.
  const countryByCode = useMemo(() => {
    const result = new Map(countries.map((country) => [country.code, country]));
    const entries = detailsByCode instanceof Map
      ? detailsByCode.entries() : Object.entries(detailsByCode || {});
    for (const [key, detail] of entries) {
      const code = detail?.country_code || key;
      if (!result.has(code) && detail?.country_slug) {
        result.set(code, {
          code,
          slug: detail.country_slug,
          name: detail.country_name || code,
          name_en: detail.country_name_en,
        });
      }
    }
    return result;
  }, [countries, detailsByCode]);
  const availableCountries = useMemo(
    () => [...countryByCode.values()].sort((a, b) => countryName(a, locale)
      .localeCompare(countryName(b, locale), locale)),
    [countryByCode, locale],
  );
  const searchCountries = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase(locale);
    if (!needle) return availableCountries;
    return availableCountries.filter((country) => [
      country.name, country.name_en, country.code, country.slug,
    ].some((value) => String(value || '').toLocaleLowerCase(locale).includes(needle)));
  }, [availableCountries, locale, query]);
  const colorModel = useMemo(
    () => buildWorldColorModel(valuesByCode, { mode: colorMode, direction: colorDirection }),
    [valuesByCode, colorMode, colorDirection],
  );
  const extent = useMemo(() => valueExtent(valuesByCode), [valuesByCode]);
  const mapDetails = useMemo(
    () => (detailsByCode instanceof Map ? detailsByCode : new Map(Object.entries(detailsByCode || {}))),
    [detailsByCode],
  );
  const periodFormat = useMemo(
    () => resolveWorldPeriodFormat(worldPeriodDates(detailsByCode)),
    [detailsByCode],
  );

  const commandCamera = useCallback((type, countryCode) => {
    commandId.current += 1;
    setCameraCommand({ id: commandId.current, type, countryCode });
  }, []);
  const selectCountry = useCallback((code, moveFocus = false) => {
    if (!code) {
      setSelectedCode(null);
      return;
    }
    const country = countryByCode.get(code) || countryByCode.get(countryAlias(code));
    if (!country) return;
    if (moveFocus) {
      focusCountryCard.current = true;
      searchInput.current?.blur();
    }
    setSelectedCode(country.code);
    setSearchOpen(false);
    setQuery('');
    commandCamera('focus', country.code);
  }, [commandCamera, countryByCode]);
  const handleReady = useCallback(() => setSceneStatus('ready'), []);
  const handleError = useCallback((error) => {
    console.warn('Planet rendering failed:', error);
    setSceneStatus('error');
    setHoverCode(null);
  }, []);

  const selectedCountry = countryByCode.get(selectedCode) || null;
  useEffect(() => {
    if (focusCountryCard.current && selectedCountry && countryCard.current) {
      focusCountryCard.current = false;
      countryCard.current.focus({ preventScroll: true });
    }
  }, [selectedCountry, cameraCommand]);
  const selectedDetail = selectedCountry
    ? collectionValue(detailsByCode, selectedCountry.code) || null : null;
  const selectedValue = selectedCountry
    ? collectionValue(valuesByCode, selectedCountry.code) ?? selectedDetail?.value : null;
  const selectedPeriod = formatWorldPeriod(selectedDetail?.date, periodFormat) || periodLabel;
  const selectedName = countryName(selectedCountry, locale);
  const hoveredCountry = countryByCode.get(hoverCode) || countryByCode.get(countryAlias(hoverCode));
  const hoveredValue = hoveredCountry ? collectionValue(valuesByCode, hoveredCountry.code) : null;
  const displayUnit = localizeWorldUnit(unit, locale);
  const hasMetric = Boolean(metricName || valuesByCode != null);
  const isMap = representation === 'map' || sceneStatus === 'error';
  const isDropdownOpen = searchOpen;
  const activeCountry = searchCountries[Math.min(activeOption, searchCountries.length - 1)];
  const optionId = (code) => `planet-${id}-country-${code}`;

  function handleSearchKey(event) {
    if (event.key === 'Escape') {
      setSearchOpen(false);
      return;
    }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      if (!searchOpen) {
        setSearchOpen(true);
        setActiveOption(0);
        return;
      }
      const increment = event.key === 'ArrowDown' ? 1 : -1;
      const index = searchCountries.length
        ? (activeOption + increment + searchCountries.length) % searchCountries.length : 0;
      setActiveOption(index);
      const nextCountry = searchCountries[index];
      if (nextCountry) {
        searchResults.current?.querySelector(`[id="${optionId(nextCountry.code)}"]`)
          ?.scrollIntoView?.({ block: 'nearest' });
      }
    }
    if (event.key === 'Enter' && searchOpen && activeCountry) {
      event.preventDefault();
      selectCountry(activeCountry.code, true);
    }
  }

  function showPlanet() {
    if (sceneStatus === 'error') {
      setPlanetScene(() => lazy(() => import('./PlanetScene')));
      setSceneGeneration((previous) => previous + 1);
      setSceneStatus('loading');
    } else if (representation === 'map') {
      setSceneStatus('loading');
    }
    setRepresentation('planet');
  }

  function clearSelection() {
    setSelectedCode(null);
    setHoverCode(null);
    commandCamera('reset');
  }

  return (
    <section className="planet-view" aria-labelledby={`planet-${id}-title`} data-planet-view="true">
      <div className="planet-header">
        <div className="planet-heading">
          <h2 id={`planet-${id}-title`}><Globe2 size={18} aria-hidden="true" />{t('planet.title')}</h2>
          <p>{t('planet.subtitle')}</p>
        </div>
        <div className="planet-view-switch" role="group" aria-label={t('planet.viewLabel')}>
          <button type="button" className={!isMap ? 'is-active' : ''} aria-pressed={!isMap} onClick={showPlanet}>
            <Globe2 size={14} aria-hidden="true" />{t('planet.earth')}
          </button>
          <button type="button" className={isMap ? 'is-active' : ''} aria-pressed={isMap} onClick={() => { setRepresentation('map'); setHoverCode(null); }}>
            <MapIcon size={14} aria-hidden="true" />{t('planet.map')}
          </button>
        </div>
      </div>

      <div className="planet-shell">
        <div className={`planet-stage${isMap ? ' planet-stage--map' : ''}`} data-scene-ready={!isMap && sceneStatus === 'ready' ? 'true' : 'false'} data-planet-mode={mode}>
          {isMap ? (
            <div className="planet-map-fallback">
              {sceneStatus === 'error' && (
                <div className="planet-fallback-message" role="status">
                  <span>{t('planet.unavailable')}</span>
                  <button type="button" onClick={showPlanet}>{t('planet.retry')}</button>
                </div>
              )}
              <Suspense fallback={<div className="planet-map-loading" role="status">{t('common.loading')}</div>}>
                <WorldMap
                  countries={countries}
                  valuesByCode={valuesByCode}
                  detailsByCode={mapDetails}
                  unit={unit}
                  metricName={metricName}
                  periodLabel={periodLabel}
                  colorMode={colorMode}
                  colorDirection={colorDirection}
                  defaultScope={defaultScope}
                  onSelect={(country) => selectCountry(country.code, true)}
                />
              </Suspense>
            </div>
          ) : (
            <>
              <SceneBoundary key={sceneGeneration} onError={handleError}>
                <Suspense fallback={null}>
                  <PlanetScene
                    countries={availableCountries}
                    valuesByCode={valuesByCode}
                    colorModel={colorModel}
                    mode={mode}
                    selectedCode={selectedCountry?.code || null}
                    onHover={setHoverCode}
                    onSelect={selectCountry}
                    onReady={handleReady}
                    onError={handleError}
                    cameraCommand={cameraCommand}
                    defaultScope={defaultScope}
                  />
                </Suspense>
              </SceneBoundary>
              {sceneStatus === 'loading' && (
                <div className="planet-loading" role="status">
                  <LoaderCircle size={19} aria-hidden="true" />{t('planet.loading')}
                </div>
              )}
              {hasMetric && (
                <div className="planet-surface-switch" role="group" aria-label={t('planet.viewLabel')}>
                  <button type="button" className={mode === 'earth' ? 'is-active' : ''} aria-pressed={mode === 'earth'} onClick={() => setMode('earth')}>
                    <Globe2 size={13} aria-hidden="true" />{t('planet.earth')}
                  </button>
                  <button type="button" className={mode === 'data' ? 'is-active' : ''} aria-pressed={mode === 'data'} onClick={() => setMode('data')}>
                    <Layers3 size={13} aria-hidden="true" />{t('planet.data')}
                  </button>
                </div>
              )}
              <div className="planet-camera-controls">
                <button type="button" onClick={() => commandCamera('zoomIn')} aria-label={t('planet.zoomIn')} title={t('planet.zoomIn')}><Plus size={17} aria-hidden="true" /></button>
                <button type="button" onClick={() => commandCamera('zoomOut')} aria-label={t('planet.zoomOut')} title={t('planet.zoomOut')}><Minus size={17} aria-hidden="true" /></button>
                <button type="button" onClick={clearSelection} aria-label={t('planet.reset')} title={t('planet.reset')}><RotateCcw size={15} aria-hidden="true" /></button>
              </div>
              <div className="planet-stage-caption">
                {hoveredCountry ? (
                  <div className="planet-hover-label">
                    <span>{countryName(hoveredCountry, locale)}</span>
                    {hasValue(hoveredValue) && <strong>{formatWorldValue(hoveredValue, undefined, locale)}{displayUnit && <small> {displayUnit}</small>}</strong>}
                  </div>
                ) : <p>{t('planet.gesture')}</p>}
              </div>
            </>
          )}
        </div>

        <aside className="planet-info" aria-label={t('planet.country')}>
          <div className="planet-search" onBlur={(event) => {
            if (!event.currentTarget.contains(event.relatedTarget)) setSearchOpen(false);
          }}>
            <label htmlFor={`planet-${id}-search`}>{t('planet.search')}</label>
            <div className={`planet-search-field${searchOpen ? ' is-open' : ''}`}>
              <Search size={16} aria-hidden="true" />
              <input
                ref={searchInput}
                id={`planet-${id}-search`}
                type="text"
                role="combobox"
                autoComplete="off"
                placeholder={t('planet.searchPlaceholder')}
                value={query}
                aria-expanded={isDropdownOpen}
                aria-autocomplete="list"
                aria-controls={isDropdownOpen && searchCountries.length > 0 ? `planet-${id}-results` : undefined}
                aria-activedescendant={isDropdownOpen && activeCountry ? optionId(activeCountry.code) : undefined}
                onFocus={() => { setSearchOpen(true); setActiveOption(0); }}
                onChange={(event) => { setQuery(event.target.value); setActiveOption(0); setSearchOpen(true); }}
                onKeyDown={handleSearchKey}
              />
              <button type="button" aria-label={t('planet.search')} aria-expanded={searchOpen} onClick={() => {
                if (searchOpen) setSearchOpen(false);
                else searchInput.current?.focus();
              }}><ChevronDown size={14} aria-hidden="true" /></button>
            </div>
            {isDropdownOpen && (
              <div className="planet-search-dropdown">
                {searchCountries.length ? (
                  <div ref={searchResults} id={`planet-${id}-results`} role="listbox" aria-label={t('planet.searchResults')}>
                    {searchCountries.map((country, index) => (
                      <button
                        key={country.code}
                        id={optionId(country.code)}
                        type="button"
                        role="option"
                        tabIndex={-1}
                        aria-selected={index === activeOption}
                        onMouseDown={(event) => event.preventDefault()}
                        onMouseEnter={() => setActiveOption(index)}
                        onClick={() => selectCountry(country.code, true)}
                      ><span>{countryName(country, locale)}</span><small>{country.code}</small></button>
                    ))}
                  </div>
                ) : <p role="status">{t('planet.noMatches')}</p>}
              </div>
            )}
          </div>

          <div ref={countryCard} className="planet-country-card" tabIndex={-1} aria-live="polite" data-selected-country={selectedCountry?.code || ''}>
            {selectedCountry ? (
              <>
                <div className="planet-country-meta">
                  <span>{selectedCountry.code}</span>
                  <button type="button" onClick={clearSelection} aria-label={t('planet.clearSelection')}><X size={15} aria-hidden="true" /></button>
                </div>
                <h3>{selectedName}</h3>
                {(selectedCountry.region || selectedCountry.region_en) && <p className="planet-country-region">{locale === 'en' ? selectedCountry.region_en || selectedCountry.region : selectedCountry.region}</p>}
                {hasMetric && (
                  <div className="planet-country-observation">
                    {metricName && <p className="planet-metric-name">{metricName}</p>}
                    {hasValue(selectedValue) ? (
                      <>
                        <div className="planet-country-value" aria-label={t('planet.value')}>{formatWorldValue(selectedValue, undefined, locale)}</div>
                        {displayUnit && <div className="planet-country-unit">{displayUnit}</div>}
                      </>
                    ) : <p className="planet-no-data">{t('planet.noData')}</p>}
                    {selectedPeriod && <div className="planet-observation-row"><span>{t('planet.period')}</span><strong>{selectedPeriod}</strong></div>}
                    {selectedDetail?.source && <div className="planet-observation-row"><span>{t('planet.source')}</span><SourceLink href={selectedDetail.source_url}>{localizeSource(selectedDetail.source, locale)}</SourceLink></div>}
                  </div>
                )}
                <button
                  type="button"
                  className="planet-open-country"
                  disabled={!selectedCountry.slug || typeof onSelect !== 'function'}
                  onClick={() => onSelect?.(selectedCountry, selectedDetail)}
                >{t(selectedDetail?.indicator_code ? 'planet.openIndicator' : 'planet.openCountry')}<ArrowUpRight size={16} aria-hidden="true" /></button>
              </>
            ) : (
              <div className="planet-empty-selection">
                <div className="planet-empty-icon"><Globe2 size={27} strokeWidth={1.2} aria-hidden="true" /></div>
                <h3>{t('planet.selectTitle')}</h3>
                <p>{t('planet.selectHint')}</p>
              </div>
            )}
          </div>

          {!isMap && mode === 'data' && hasMetric && (
            <div className="planet-legend" aria-label={t('planet.legend')}>
              <p>{metricName || t('planet.legend')}</p>
              {colorModel.bins.length > 0 && (
                <>
                  <div className="planet-legend-scale">{colorModel.bins.map((bin, index) => {
                    const label = `${t(bin.labelKey)}: ${legendBinRange(bin, locale)}${displayUnit ? ` ${displayUnit}` : ''}`;
                    return <span key={index} role="img" aria-label={label} title={label} style={{ backgroundColor: bin.color }} />;
                  })}</div>
                  {extent && <div className="planet-legend-range"><span>{formatWorldValue(extent.min, undefined, locale)}</span><span>{formatWorldValue(extent.max, undefined, locale)}</span></div>}
                  {displayUnit && <div className="planet-legend-unit">{displayUnit}</div>}
                  <div className="planet-legend-labels"><span>{t(colorModel.bins[0].labelKey)}</span><span>{t(colorModel.bins.at(-1).labelKey)}</span></div>
                  <small>{t(colorModel.kind === 'diverging' ? 'world.map.scaleZero' : 'world.map.scaleMedian')}</small>
                </>
              )}
              <div className="planet-legend-no-data"><i aria-hidden="true" />{t('planet.noDataLegend')}</div>
            </div>
          )}
          <div className="planet-coverage"><span aria-hidden="true" />{t('planet.coverage', { count: availableCountries.length })}</div>
        </aside>
      </div>
      <p className="planet-attribution">
        {t('planet.imageryCredit')} <a href="https://www.solarsystemscope.com/textures/" target="_blank" rel="noopener noreferrer">Solar System Scope</a>
        {', '}<a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener noreferrer">CC BY 4.0</a>
        {', '}{t('planet.imageryAdapted')}
      </p>
    </section>
  );
}
