// Строка якорных ссылок над длинной страницей: «Что это, Для кого, Доверие».
// Один горизонтальный ряд со свайпом (без «рваных» переносов); обычные якоря #id работают без JS.
import { useT } from '../i18n';
import '../styles/w5-pages.css';

export default function SectionNav({ items }) {
  const t = useT();
  return (
    <nav className="w5-secnav" aria-label={t('w5.page.sections')}>
      {items.map((item) => (
        <a key={item.id} href={`#${item.id}`} className="w5-secnav__link fe-press">
          {item.label}
        </a>
      ))}
    </nav>
  );
}
