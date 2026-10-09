import { useEffect } from 'react';
import { useT } from '../i18n';

/**
 * Первая цель табуляции: переход к основному содержимому в обход шапки и бегущей строки.
 * Круг 11, G (U32): ссылка показывается только тому, кто листает клавиатурой. После касания, клика или программного перехода (смена
 * страницы, смена языка) браузер всё равно может поставить на неё `:focus-visible` и она торчала над лентой курсов; теперь пока не нажат
 * Tab, документ несёт `html[data-fe-pointer]`, и CSS (index.css) оставляет ссылку за краем окна.
 */
export default function SkipLink() {
  const t = useT();
  useEffect(() => {
    const root = document.documentElement;
    root.setAttribute('data-fe-pointer', 'true');
    const onKey = (event) => { if (event.key === 'Tab') root.removeAttribute('data-fe-pointer'); };
    const onPointer = () => root.setAttribute('data-fe-pointer', 'true');
    document.addEventListener('keydown', onKey, true);
    document.addEventListener('pointerdown', onPointer, true);
    document.addEventListener('touchstart', onPointer, { capture: true, passive: true });
    return () => {
      document.removeEventListener('keydown', onKey, true);
      document.removeEventListener('pointerdown', onPointer, true);
      document.removeEventListener('touchstart', onPointer, true);
      root.removeAttribute('data-fe-pointer');
    };
  }, []);
  return <a href="#main-content" className="fe-skip-link">{t('a11y.skipToContent')}</a>;
}
