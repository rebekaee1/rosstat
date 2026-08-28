import HomeDataScope from './HomeDataScope';
import { useT } from '../../i18n';

/**
 * Hero главной: слева заголовок и вводный текст, справа — состав платформы
 * в цифрах. Карта России переехала на /russia; поиск по индикатору с главной
 * снят — глобальный поиск живёт в navbar.
 */
export default function HomeHero() {
  const t = useT();
  return (
    <header data-block="home-hero" className="mb-6 md:mb-8">
      <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1.15fr)_minmax(18rem,0.85fr)] lg:gap-8">
        <div className="min-w-0">
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.28em] text-champagne">
            {t('home.hero.eyebrow')}
          </p>
          <h1 className="max-w-3xl text-2xl font-semibold leading-[1.2] tracking-tight text-text-primary md:text-3xl lg:text-[2rem]">
            {t('home.hero.title')}
          </h1>
          <p className="mt-2.5 max-w-2xl text-sm leading-relaxed text-text-secondary md:text-[15px]">
            {t('home.hero.subtitle')}
          </p>
        </div>

        <HomeDataScope />
      </div>
    </header>
  );
}
