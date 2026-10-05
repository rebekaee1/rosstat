import { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { useT } from '../i18n';
import { navLabelFor } from '../lib/navLabel';

/**
 * Отклик на нажатие при переходе между страницами. React Router оборачивает переход в startTransition:
 * пока подгружается чанк новой страницы, остаётся старая, и клик «молчит». Поэтому старт определяем по
 * клику на внутреннюю ссылку (capture) и сразу показываем полосу сверху и плашку «Открываем: …» с названием
 * того, что нажали (волна 6, 1.2). Плашка проявляется через 80 мс, чтобы мгновенные переходы её не мигали.
 * Конец — по смене адреса или через 8 с.
 */
export default function PageProgress() {
  const t = useT();
  const location = useLocation();
  const [pending, setPending] = useState(null);
  const key = `${location.pathname}${location.search}`;

  useEffect(() => {
    let guard = null;
    const stop = () => { clearTimeout(guard); guard = null; };
    const onClick = (event) => {
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const anchor = event.target instanceof Element ? event.target.closest('a[href]') : null;
      if (!anchor || (anchor.target && anchor.target !== '_self') || anchor.hasAttribute('download')) return;
      let url;
      try { url = new URL(anchor.href, window.location.href); } catch { return; }
      if (url.origin !== window.location.origin) return;
      if (url.pathname === window.location.pathname && url.search === window.location.search) return;
      stop();
      setPending({ key: `${window.location.pathname}${window.location.search}`, label: navLabelFor(anchor) });
      guard = setTimeout(() => setPending(null), 8000);
    };
    document.addEventListener('click', onClick, true);
    return () => { document.removeEventListener('click', onClick, true); stop(); };
  }, []);

  // Показываем, только пока адрес тот же, что был при старте: смена адреса гасит полосу без setState в эффекте.
  if (!pending || pending.key !== key) return null;
  return (
    <>
      <span className="fe-page-progress" aria-hidden="true" data-testid="page-progress" />
      <div className="fe-nav-hint" role="status" aria-live="polite" data-testid="nav-hint">
        <span className="fe-nav-hint__dot" aria-hidden="true" />
        <span className="fe-nav-hint__text">
          {pending.label ? t('w6a.nav.opening', { label: pending.label }) : t('w6a.nav.openingPage')}
        </span>
      </div>
    </>
  );
}
