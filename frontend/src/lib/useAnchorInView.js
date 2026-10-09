import { useEffect, useState } from 'react';

/**
 * Пока раздел страницы с этим id занимает середину окна, хук отдаёт true (круг 11, G, U33). Нужен пункту меню «Страны»: он ведёт на каталог
 * стран на главной (якорь), и без этой подсветки нажатие выглядело как обновление страницы.
 *
 * `enabled` — следить стоит только на той странице, где раздел есть (на главной). Раздел может появиться позже первого кадра
 * (ленивый блок), поэтому поиск повторяется несколько раз и останавливается, когда нашли или страница сменилась.
 * Без IntersectionObserver (старые браузеры, тесты) всегда false: подсветка по адресу (`#countries`) работает и так.
 */
export function useAnchorInView(id, enabled = true) {
  const [inView, setInView] = useState(false);

  useEffect(() => {
    if (!enabled || typeof window === 'undefined' || typeof IntersectionObserver !== 'function') {
      return undefined;
    }
    let observer = null;
    let timer = 0;
    let tries = 0;
    const attach = () => {
      const el = document.getElementById(id);
      if (!el) {
        tries += 1;
        if (tries < 12) timer = window.setTimeout(attach, 600);
        return;
      }
      // Полоса в середине окна толщиной 10 %: раздел «активен», когда он пересекает её.
      observer = new IntersectionObserver(
        (entries) => { const last = entries[entries.length - 1]; if (last) setInView(last.isIntersecting); },
        { rootMargin: '-45% 0px -45% 0px', threshold: 0 },
      );
      observer.observe(el);
    };
    attach();
    return () => {
      window.clearTimeout(timer);
      observer?.disconnect();
      setInView(false);
    };
  }, [id, enabled]);

  return inView;
}
