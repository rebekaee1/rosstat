import './PlanetView.css';

/**
 * Статичная картинка шара на время загрузки: те же размеры, что у настоящей сцены, поэтому страница не прыгает.
 * Лёгкий модуль без three и без данных: его можно показывать с первого кадра.
 */
export default function PlanetPlaceholder() {
  return (
    <div className="planet-host" aria-busy="true">
      <div className="planet-view planet-view--placeholder">
        <div className="planet-shell">
          <div className="planet-geography">
            <div className="planet-stage" data-scene-ready="false">
              <div className="planet-orb" aria-hidden="true" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
