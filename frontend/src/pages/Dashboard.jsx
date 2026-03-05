import { useEffect, useRef } from 'react';
import gsap from 'gsap';
import { useIndicators } from '../lib/hooks';
import useDocumentMeta from '../lib/useMeta';
import IndicatorTile from '../components/IndicatorTile';
import { TileSkeleton } from '../components/Skeleton';

export default function Dashboard() {
  const heroRef = useRef(null);
  const { data: indicators, isLoading } = useIndicators();

  useDocumentMeta({
    title: 'Прогноз инфляции и ИПЦ России',
    description:
      'Аналитическая платформа экономических индикаторов России. ' +
      'Исторические ряды ИПЦ с 1991 года, OLS-прогноз инфляции на 12 месяцев, ' +
      'ИПЦ по категориям: продовольствие, непродовольственные товары, услуги.',
    path: '/',
  });

  useEffect(() => {
    const elements = heroRef.current?.querySelectorAll('[data-animate]');
    if (elements?.length) {
      gsap.fromTo(elements,
        { y: 40, opacity: 0 },
        { y: 0, opacity: 1, duration: 1, ease: 'power3.out', stagger: 0.1 }
      );
    }
  }, []);

  return (
    <div className="max-w-7xl mx-auto px-4 md:px-8 pt-32 pb-20">
      <section ref={heroRef} className="mb-16 md:mb-24">
        <div className="max-w-2xl">
          <div data-animate className="flex items-center gap-3 mb-6">
            <div className="h-[1px] w-8 bg-champagne"></div>
            <p className="text-[10px] uppercase tracking-[0.3em] text-champagne font-semibold">
              Макроэкономический терминал
            </p>
          </div>
          
          <h1 data-animate className="text-4xl md:text-5xl lg:text-6xl font-bold tracking-tight leading-[1.05] mb-6">
            Экономика <br className="hidden md:block"/>
            <span className="font-display italic text-champagne font-normal pr-2">в реальном времени.</span>
          </h1>
          
          <p data-animate className="text-sm md:text-base text-text-secondary leading-relaxed max-w-lg">
            Высокоточная аналитика на основе открытых данных Росстата. 
            Исторические ряды с 1991 года и предиктивное моделирование OLS.
          </p>
        </div>
      </section>

      <section>
        <div className="flex items-center gap-4 mb-8">
          <h2 className="text-xs uppercase tracking-[0.2em] text-text-secondary font-semibold">
            Активные потоки данных
          </h2>
          <div className="h-[1px] flex-1 bg-border-subtle"></div>
        </div>

        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {[...Array(6)].map((_, i) => <TileSkeleton key={i} />)}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {indicators?.map((ind, i) => (
              <IndicatorTile key={ind.code} indicator={ind} delay={i} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
