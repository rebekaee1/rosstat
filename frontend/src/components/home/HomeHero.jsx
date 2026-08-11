import IndicatorSearch from '../IndicatorSearch';

export default function HomeHero() {
  return (
    <header data-block="home-hero" className="mb-8 md:mb-10">
      <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.28em] text-champagne">
        Forecast Economy
      </p>
      <h1 className="max-w-3xl text-xl font-semibold leading-snug tracking-tight text-text-primary md:text-2xl">
        Экономические данные России, регионов и стран — в одной рабочей среде
      </h1>
      <p className="mt-2 max-w-2xl text-sm leading-relaxed text-text-secondary md:text-[15px]">
        Официальная статистика, актуальные значения и переход к полной карточке показателя.
        Сейчас доступны Россия, субъекты РФ и европейское покрытие по странам.
      </p>
      <div className="mt-5">
        <IndicatorSearch
          variant="inline"
          inlinePlaceholder="Найти показатель — инфляция, ВВП, ставка, безработица…"
        />
      </div>
    </header>
  );
}
