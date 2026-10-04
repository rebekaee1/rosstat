// Оглавление юридической страницы: ссылки-якоря на все заголовки второго уровня статьи.
// Заголовки собираются из готового DOM (RU и EN тела разные), им проставляются id.
// На телефоне блок свёрнут, на широком экране раскрыт.
import { useEffect, useState } from 'react';
import { useLocale } from '../i18n';
import '../styles/w5-pages.css';

export default function LegalToc({ articleRef }) {
  const { locale, t } = useLocale();
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(
    () => typeof window !== 'undefined' && typeof window.matchMedia === 'function'
      && window.matchMedia('(min-width: 768px)').matches,
  );

  useEffect(() => {
    // Заголовки читаем после отрисовки статьи (в следующем кадре), а не синхронно в эффекте.
    const frame = window.requestAnimationFrame(() => {
      const root = articleRef?.current;
      if (!root) return;
      const headings = [...root.querySelectorAll('h2')];
      headings.forEach((heading, index) => {
        if (!heading.id) heading.id = `legal-${index + 1}`;
      });
      setItems(headings.map((heading) => ({ id: heading.id, label: heading.textContent.trim() })));
    });
    return () => window.cancelAnimationFrame(frame);
  }, [articleRef, locale]);

  if (items.length < 3) return null;
  return (
    <details className="w5-toc" open={open} onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary>{t('w5.legal.toc')}</summary>
      <ol>
        {items.map((item) => (
          <li key={item.id}><a href={`#${item.id}`}>{item.label}</a></li>
        ))}
      </ol>
    </details>
  );
}
