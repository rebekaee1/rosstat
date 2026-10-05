import './PlanetView.css';

const LIST_ROWS = [78, 64, 70, 58, 66, 52, 60, 56];

/**
 * Картинка карточки планеты на время загрузки: те же размеры и та же раскладка, что у настоящей карточки, поэтому
 * страница не прыгает при подмене. Вместо пустой бледной плиты человек сразу видит раскрашенный шар (золото и синева,
 * как у настоящей карты), строку поиска страны с годом, полосу легенды и рейтинг стран из бегущих строк.
 * Лёгкий модуль без three и без данных: его можно показывать с первого кадра.
 */
export default function PlanetPlaceholder() {
  return (
    <div className="planet-host" aria-busy="true">
      <div className="planet-view planet-view--placeholder">
        <div className="planet-shell has-key">
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
              <div className="planet-orb planet-orb--preview" aria-hidden="true" />
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
