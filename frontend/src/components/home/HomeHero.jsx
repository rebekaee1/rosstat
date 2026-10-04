import { useMemo } from 'react';
import IndicatorSearch from '../IndicatorSearch';
import HomeDataScope from './HomeDataScope';
import HomePopularCountries from './HomePopularCountries';
import { HOME_EXAMPLE_COUNT, searchExamples } from '../../lib/searchExamples';
import { useT } from '../../i18n';
import '../../styles/shell.css';

/**
 * Hero главной. Слева: короткий тёплый заголовок, лид про официальные данные, поиск с примерами запросов.
 * Справа: три живых числа платформы. Ниже — «Популярные страны» одной полосой, чтобы каталог был у начала страницы.
 * Единственный источник разметки hero: HomeWorkbench не дублирует её.
 */
export default function HomeHero() {
  const t = useT();
  const examples = useMemo(() => searchExamples(t, HOME_EXAMPLE_COUNT), [t]);
  return (
    <header
      data-block="home-hero"
      className="relative z-20 mb-4 md:mb-5"
    >
      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1.15fr)_minmax(18rem,0.85fr)] lg:gap-8">
        <div className="relative z-20 min-w-0 fe-reveal">
          <p className="fe-hero-eyebrow">{t('home.hero.eyebrow')}</p>
          <h1 className="max-w-3xl text-2xl font-semibold leading-[1.2] tracking-tight text-text-primary md:text-3xl lg:text-[2rem]">
            {t('home.hero.title')}
          </h1>
          <p className="mt-2.5 max-w-2xl text-sm leading-relaxed text-text-secondary md:text-[15px]">
            {t('home.hero.subtitle')}
          </p>
          <div className="relative z-20 mt-5 max-w-xl">
            <IndicatorSearch variant="inline" examples={examples} />
          </div>
        </div>

        <HomeDataScope />
      </div>
      <HomePopularCountries />
    </header>
  );
}
