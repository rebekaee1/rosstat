import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { useIndicators } from '../lib/hooks';
import useDocumentMeta from '../lib/useMeta';
import { getPageSeo } from '../lib/pageMeta';
import HomeHero from '../components/home/HomeHero';
import HomeWorkbench from '../components/home/HomeWorkbench';
import HomeCountryList from '../components/home/HomeCountryList';
import { useWorldRatingConcepts } from '../lib/worldApi';
import { useLocale } from '../i18n';

export default function Dashboard() {
  const { locale } = useLocale();
  const { hash } = useLocation();
  const { data: indicators } = useIndicators();
  const ratingConcepts = useWorldRatingConcepts();

  const homeSeo = getPageSeo('home', locale);
  useDocumentMeta({
    title: homeSeo.title,
    description: homeSeo.description,
    path: homeSeo.path,
  });

  // Ссылки «Страны» из шапки, футера и SSR ведут на /#countries — в том числе
  // когда мы уже на главной, поэтому реагируем на смену хеша, а не только на монтирование.
  useEffect(() => {
    if (hash !== '#countries') return undefined;
    const timer = window.setTimeout(() => {
      document.getElementById('countries')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 50);
    return () => window.clearTimeout(timer);
  }, [hash]);

  return (
    <div className="mx-auto max-w-7xl overflow-x-clip px-4 pb-28 pt-24 md:px-8">
      <HomeHero />
      <HomeWorkbench ratingConcepts={ratingConcepts} />
      <HomeCountryList russiaSeriesCount={indicators?.length || 0} />
    </div>
  );
}
