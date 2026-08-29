import IndicatorSearch from '../IndicatorSearch';
import HomeDataScope from './HomeDataScope';
import { useT } from '../../i18n';

/**
 * Hero главной: слева заголовок, вводный текст и поиск по индикатору
 * (как на страницах стран), справа — состав платформы в цифрах.
 * На lg+ нижний margin снят: карту поднимает HomeWorkbench отрицательным
 * margin'ом, пересекаясь с нижней частью scope-карточки.
 */
export default function HomeHero() {
  const t = useT();
  return (
    <header
      data-block="home-hero"
      className="relative z-20 mb-5 pointer-events-none md:mb-6 lg:mb-0"
    >
      {/*
        pointer-events-none на header: на lg+ карта поднимается под scope и
        проходит через «воздух» слева от карточки. Без этого пустая область
        сетки hero перехватывает клики по заголовку/пикеру workbench.
      */}
      <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1.15fr)_minmax(18rem,0.85fr)] lg:gap-8">
        <div className="relative z-20 min-w-0 pointer-events-auto">
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.28em] text-champagne">
            {t('home.hero.eyebrow')}
          </p>
          <h1 className="max-w-3xl text-2xl font-semibold leading-[1.2] tracking-tight text-text-primary md:text-3xl lg:text-[2rem]">
            {t('home.hero.title')}
          </h1>
          <p className="mt-2.5 max-w-2xl text-sm leading-relaxed text-text-secondary md:text-[15px]">
            {t('home.hero.subtitle')}
          </p>
          <div className="relative z-20 mt-5 max-w-xl">
            <IndicatorSearch variant="inline" />
          </div>
        </div>

        <div className="pointer-events-auto">
          <HomeDataScope />
        </div>
      </div>
    </header>
  );
}
