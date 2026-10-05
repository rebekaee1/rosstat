import { useEffect, useMemo, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import IndicatorSearch from '../IndicatorSearch';
import HomeDataScope from './HomeDataScope';
import HomePopularCountries from './HomePopularCountries';
import { HOME_EXAMPLE_COUNT, searchExamples } from '../../lib/searchExamples';
import { useT } from '../../i18n';
import '../../styles/shell.css';
import '../../styles/planet-hero.css';

/**
 * Hero главной. Слева: короткий тёплый заголовок, лид одной строкой, поиск с примерами запросов, под ним три числа
 * платформы. Справа (на телефоне — сразу под поиском): живая планета, `planet`, на первом экране.
 * Ниже — «Популярные страны» одной полосой, чтобы каталог был у начала страницы.
 * Единственный источник разметки hero: HomeWorkbench не дублирует её.
 */
export default function HomeHero({ planet = null }) {
  const t = useT();
  const [params, setParams] = useSearchParams();
  // `?q=` нужен один раз, чтобы открыть поиск; после этого убираем его из адреса (иначе поиск «возвращается» при смене языка).
  const seededQuery = useRef(params.get('q')).current;
  useEffect(() => {
    if (!params.get('q')) return;
    const next = new URLSearchParams(params);
    next.delete('q');
    setParams(next, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const examples = useMemo(() => searchExamples(t, HOME_EXAMPLE_COUNT), [t]);
  return (
    <header
      data-block="home-hero"
      className="relative z-20 mb-4 md:mb-5"
    >
      <div className={planet ? 'fe-hero-grid' : 'grid items-start gap-4 lg:grid-cols-[minmax(0,1.15fr)_minmax(18rem,0.85fr)] lg:gap-8'}>
        <div className={'relative z-20 min-w-0 fe-reveal' + (planet ? ' fe-hero-text' : '')}>
          <p className="fe-hero-eyebrow">{t('home.hero.eyebrow')}</p>
          <h1 className="max-w-3xl text-2xl font-semibold leading-[1.2] tracking-tight text-text-primary md:text-3xl lg:text-[2rem]">
            {t('home.hero.title')}
          </h1>
          <p className="mt-2.5 max-w-2xl text-sm leading-relaxed text-text-secondary md:text-[15px]">
            {planet ? t('w6c.hero.subtitle') : t('home.hero.subtitle')}
          </p>
          <div className="relative z-20 mt-5 max-w-xl">
            <IndicatorSearch variant="inline" examples={examples} initialQuery={seededQuery} />
          </div>
        </div>

        {planet && <div className="fe-hero-planet">{planet}</div>}
        {planet ? <div className="fe-hero-scope"><HomeDataScope /></div> : <HomeDataScope />}
      </div>
      <HomePopularCountries />
    </header>
  );
}
