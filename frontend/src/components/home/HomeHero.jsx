import { useEffect, useMemo, useRef } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import IndicatorSearch from '../IndicatorSearch';
import HomeDataScope from './HomeDataScope';
import HomeToday from './HomeToday';
import { HOME_EXAMPLE_COUNT, searchExamples } from '../../lib/searchExamples';
import { buildQuickLinks } from '../../lib/homeQuickLinks';
import { useWorldCompareSnapshot } from '../../lib/worldApi';
import { track, events } from '../../lib/track';
import { useLocale, useT } from '../../i18n';
import '../../styles/shell.css';
import '../../styles/planet-hero.css';
import '../../styles/z3-home.css';
import '../../styles/k7-home.css';

/**
 * Hero главной. Слева (на компьютере): заголовок, поиск и быстрые ссылки, «Мир сейчас» с четырьмя живыми фактами
 * и числа платформы: колонка не пустеет рядом с высокой карточкой планеты. Справа: живая планета `planet`.
 * На телефоне порядок другой: текст и поиск, планета, «Мир сейчас», числа платформы.
 * Ряд «Популярные страны» с круга 8 здесь не стоит: он повторял каталог стран ниже и дважды звал «Показать все страны»
 * (компонент HomePopularCountries остаётся в каталоге компонентов, пока не выяснены все потребители).
 * Единственный источник разметки hero: HomeWorkbench её не дублирует.
 */
export default function HomeHero({ planet = null }) {
  const t = useT();
  const { locale } = useLocale();
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
  // Те же срезы, что у планеты и каталога стран: общий кэш, лишних запросов нет.
  const gdp = useWorldCompareSnapshot('gdp-usd');
  const inflation = useWorldCompareSnapshot('hicp-index');
  const quickLinks = useMemo(
    () => buildQuickLinks({ locale, gdp: gdp.data, inflation: inflation.data }),
    [locale, gdp.data, inflation.data],
  );
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
            {planet ? (
              <>
                <span className="fe-hero-lead--full">{t('w6c.hero.subtitle')}</span>
                <span className="fe-hero-lead--short">{t('z3.hero.leadShort')}</span>
              </>
            ) : t('home.hero.subtitle')}
          </p>
          <div className="fe-hero-search relative z-20 mt-5 max-w-xl">
            <IndicatorSearch variant="inline" examples={examples} initialQuery={seededQuery} />
          </div>
          {planet ? (
            <nav className="fe-quick fe-fade-x" aria-label={t('z3.quick.aria')}>
              <ul className="fe-quick__row scrollbar-hide">
                {quickLinks.map((link) => (
                  <li key={link.id}>
                    <Link
                      to={link.to}
                      onClick={() => track(events.HOME_COUNTRIES_CTA, { target: 'quick-link', id: link.id })}
                      className="fe-quick__chip fe-press"
                    >
                      {t(link.labelKey)}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>
          ) : null}
        </div>
        {planet && <div className="fe-hero-planet">{planet}</div>}
        {planet ? <HomeToday /> : null}
        {planet ? <div className="fe-hero-scope"><HomeDataScope /></div> : <HomeDataScope />}
      </div>
    </header>
  );
}
