// Карта штатов в профиле страны (круг 10, К5): так же, как у России в профиле показаны регионы. Тёмная компактная карта без кнопок
// масштаба, штаты нажимаются и ведут на страницу штата. Карта лежит в карточке профиля и по высоте не больше трети экрана,
// чтобы профиль целиком помещался на одном экране. Геометрию и названия не дублируем: те же `usStatesMap.json` и ответ каталога штатов,
// что у страницы «Штаты США».
import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import usStatesMap from '../../lib/usStatesMap.json';
import { useWorldRegionsHub } from '../../lib/worldSubnationalApi';
import { countryRegionPath } from '../../lib/sitePaths';
import { track, events } from '../../lib/track';
import { useT } from '../../i18n';
import RegionsMap from '../RegionsMap';
import '../../styles/c10m-map.css';

const MAPS = { 'united-states': usStatesMap };

export default function CountryStatesMap({ slug, countryName = '' }) {
  const t = useT();
  const navigate = useNavigate();
  const hub = useWorldRegionsHub(slug);
  const geometry = MAPS[slug];
  const nameBySlug = useMemo(() => {
    const out = {};
    for (const region of hub.data?.regions || []) out[region.slug] = region.name;
    return out;
  }, [hub.data]);
  if (!geometry) return null;
  return (
    <div className="c10m-states-map" data-block="country-states-map">
      <RegionsMap
        variant="compact"
        theme="dark"
        mapData={geometry}
        valuesBySlug={null}
        nameBySlug={nameBySlug}
        ariaLabel={t('world.regions.mapAria', { country: countryName || slug })}
        onSelect={(stateSlug) => {
          track(events.REGIONS_MAP_SELECT, { region: stateSlug, metric: 'country-profile', world: true });
          navigate(countryRegionPath(slug, stateSlug));
        }}
      />
      <p className="c10m-states-map__hint">{t('c10m.states.hint')}</p>
    </div>
  );
}
