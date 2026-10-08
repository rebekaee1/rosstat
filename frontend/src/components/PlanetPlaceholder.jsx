import { useT } from '../i18n';
import { readPlanetViewPreference } from '../lib/planetViewPreference';
import Spinner from './Spinner';
import './PlanetView.css';

const LIST_ROWS = [78, 64, 70, 58, 66, 52, 60, 56];

/**
 * Единое состояние загрузки шара (круг 6): матовая нейтральная сфера с тонкой сеткой меридианов, нарисованная CSS и SVG,
 * без картинки и без цветных континентов. Её диаметр (--planet-sphere) равен диаметру настоящего шара, поэтому при подмене
 * сцена проявляется поверх за 300 мс без скачка размера. Используется и в каркасе карточки, и внутри PlanetView.
 */
export function PlanetOrb() {
  return (
    <div className="planet-orb" aria-hidden="true">
      <svg viewBox="0 0 100 100" focusable="false">
        <ellipse cx="50" cy="50" rx="16" ry="50" />
        <ellipse cx="50" cy="50" rx="33" ry="50" />
        <ellipse cx="50" cy="50" rx="47" ry="50" />
        <path d="M50 0V100" />
        <path d="M0 50Q50 57 100 50" />
        <path d="M6.7 25Q50 31 93.3 25" />
        <path d="M6.7 75Q50 81 93.3 75" />
        <path d="M25 6.7Q50 10 75 6.7" />
        <path d="M25 93.3Q50 97 75 93.3" />
      </svg>
    </div>
  );
}

/**
 * Каркас карточки планеты на время загрузки: те же размеры и та же раскладка, что у настоящей карточки, поэтому
 * страница не прыгает при подмене. Человек сразу видит нейтральный шар с подписью «Загружаем карту…», строку поиска страны
 * с годом, полосу легенды и рейтинг стран из бегущих строк.
 * Лёгкий модуль без three и без данных: его можно показывать с первого кадра.
 * Над сценой стоит каркас переключателя «Карта | Шар», в окне сцены — ровная подложка карты (или шар, если выбран он).
 */
export default function PlanetPlaceholder() {
  const t = useT();
  // По умолчанию окно сцены занимает плоская карта; матовый шар виден только тем, кто выбрал шар.
  const flat = readPlanetViewPreference() === 'map';
  return (
    <div className="planet-host" aria-busy="true">
      <div className="planet-view planet-view--placeholder">
        <div className="planet-shell has-key">
          <div className="planet-viewbar" aria-hidden="true"><span className="planet-ph-view skeleton" /></div>
          <div className="planet-toolbar" aria-hidden="true">
            <div className="planet-search">
              <div className="planet-search-field planet-ph-field"><span className="skeleton planet-ph-line" style={{ width: '46%' }} /></div>
            </div>
            <div className="planet-display-controls">
              <div className="planet-year"><span className="planet-ph-year skeleton" /></div>
            </div>
          </div>
          <div className="planet-geography">
            <div className="planet-stage" data-scene-ready="false">
              {flat ? <div className="planet-map-ph" aria-hidden="true" /> : <PlanetOrb />}
              <div className="planet-loading" role="status"><Spinner size={16} />{t('r6.planet.loading')}</div>
            </div>
            <div className="planet-key" aria-hidden="true">
              <div className="planet-key-head">
                <span className="skeleton planet-ph-line" style={{ width: '34%' }} />
                <span className="skeleton planet-ph-pill" />
              </div>
              <div className="planet-key-scale"><div className="planet-key-bar planet-ph-bar" /></div>
            </div>
          </div>
          <aside className="planet-info" aria-hidden="true">
            <div className="planet-list-heading"><div><span className="skeleton planet-ph-line" style={{ width: '88px' }} /></div></div>
            <div className="planet-country-list planet-ph-list">
              {LIST_ROWS.map((width, index) => (
                <div key={index} className="planet-ph-row">
                  <span className="skeleton planet-ph-dot" />
                  <span className="skeleton planet-ph-line" style={{ width: `${width}%`, maxWidth: '9rem' }} />
                  <span className="skeleton planet-ph-line planet-ph-value" />
                </div>
              ))}
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}
