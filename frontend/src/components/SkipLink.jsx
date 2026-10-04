import { useT } from '../i18n';

/** Первая цель табуляции: переход к основному содержимому в обход шапки и бегущей строки. */
export default function SkipLink() {
  const t = useT();
  return <a href="#main-content" className="fe-skip-link">{t('a11y.skipToContent')}</a>;
}
