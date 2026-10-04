import { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';

/**
 * Полоса прогресса при переходе между страницами. React Router оборачивает переход в startTransition:
 * пока подгружается чанк новой страницы, остаётся старая, и клик «молчит». Поэтому старт определяем по
 * клику на внутреннюю ссылку (capture, с задержкой 120 мс — быстрые переходы полосу не показывают),
 * конец — по смене адреса или через 8 с.
 */
export default function PageProgress() {
  const location = useLocation();
  const [pendingKey, setPendingKey] = useState(null);
  const key = `${location.pathname}${location.search}`;

  useEffect(() => {
    let timer = null;
    let guard = null;
    const stop = () => { clearTimeout(timer); clearTimeout(guard); timer = null; guard = null; };
    const onClick = (event) => {
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const anchor = event.target instanceof Element ? event.target.closest('a[href]') : null;
      if (!anchor || (anchor.target && anchor.target !== '_self') || anchor.hasAttribute('download')) return;
      let url;
      try { url = new URL(anchor.href, window.location.href); } catch { return; }
      if (url.origin !== window.location.origin) return;
      if (url.pathname === window.location.pathname && url.search === window.location.search) return;
      stop();
      timer = setTimeout(() => setPendingKey(`${window.location.pathname}${window.location.search}`), 120);
      guard = setTimeout(() => setPendingKey(null), 8000);
    };
    document.addEventListener('click', onClick, true);
    return () => { document.removeEventListener('click', onClick, true); stop(); };
  }, []);

  // Показываем, только пока адрес тот же, что был при старте: смена адреса гасит полосу без setState в эффекте.
  if (pendingKey === null || pendingKey !== key) return null;
  return <span className="fe-page-progress" aria-hidden="true" data-testid="page-progress" />;
}
