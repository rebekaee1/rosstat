import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

/** Quick-link images can target a chart that arrives after the data request. */
export default function ScrollToAnchor() {
  const { pathname, hash } = useLocation();
  useEffect(() => {
    if (!hash || hash === '#') return undefined;
    let id;
    try { id = decodeURIComponent(hash.slice(1)); } catch { return undefined; }
    let observer;
    let frame;
    let timer;
    const reveal = () => {
      const target = document.getElementById(id);
      if (!target) return false;
      observer?.disconnect();
      clearTimeout(timer);
      frame = requestAnimationFrame(() => target.scrollIntoView({ block: 'start', behavior: 'auto' }));
      return true;
    };
    if (!reveal()) {
      observer = new MutationObserver(reveal);
      observer.observe(document.getElementById('root') || document.body, { childList: true, subtree: true });
      timer = setTimeout(() => observer.disconnect(), 15000);
    }
    return () => {
      observer?.disconnect();
      cancelAnimationFrame(frame);
      clearTimeout(timer);
    };
  }, [pathname, hash]);
  return null;
}
