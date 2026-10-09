import { useLayoutEffect } from 'react';

/**
 * Выпадающая панель, закреплённая под кнопкой (`position: absolute; right: 0; top: 100%`), не должна уходить за край окна
 * (круг 11, G, U12: меню «Скачать» на iPad уходило за левый край, на телефоне нижний пункт срезала панель Safari).
 * Хук ничего не знает о том, как панель позиционирована: после открытия он меряет её и поправляет:
 *   по горизонтали  сдвигает на нужное число пикселей внутрь окна (`transform: translateX`), запас `margin` от края;
 *   по вертикали    если снизу не хватает места, а сверху больше, ставит панель над кнопкой (`bottom: 100%`); если не хватает и там,
 *                   прокручивает страницу ровно настолько, чтобы панель поместилась.
 * Нижний край окна считается без нижней панели телефона и плашек: их высоту читаем из `--fe-bottom-clear` на корне документа.
 * Поправки живут на элементе (inline style) и снимаются при закрытии, поэтому следующее открытие меряется заново.
 *
 *   const panelRef = useRef(null);
 *   useKeepInViewport(panelRef, open);
 *   {open && <div ref={panelRef} className="absolute right-0 top-full …">…</div>}
 */
export function planViewportFit(rect, view, { margin = 12 } = {}) {
  const plan = { dx: 0, flipUp: false, scrollBy: 0 };
  if (rect.left < margin) plan.dx = margin - rect.left;
  else if (rect.right > view.width - margin) plan.dx = view.width - margin - rect.right;
  const bottomLimit = view.height - view.bottomClear - margin;
  if (rect.bottom > bottomLimit) {
    const height = rect.bottom - rect.top;
    // Над кнопкой нужно место под всю панель и зазор до неё; сверху окно ограничено лентой и шапкой (view.top).
    const roomAbove = view.anchorTop - view.top - (view.gap || 0) - margin;
    if (roomAbove >= height) plan.flipUp = true;
    else plan.scrollBy = Math.ceil(rect.bottom - bottomLimit);
  }
  return plan;
}

function readBottomClear() {
  try {
    const raw = getComputedStyle(document.documentElement).getPropertyValue('--fe-bottom-clear');
    // calc(...) приходит строкой; число пикселей берём из измерения скрытого узла.
    if (!raw) return 0;
    const probe = document.createElement('div');
    probe.style.cssText = `position:fixed;left:-9999px;bottom:0;height:${raw.trim()};width:1px;visibility:hidden;pointer-events:none`;
    document.body.appendChild(probe);
    const h = probe.getBoundingClientRect().height;
    probe.remove();
    return Number.isFinite(h) ? h : 0;
  } catch {
    return 0;
  }
}

export function useKeepInViewport(ref, open, { margin = 12 } = {}) {
  useLayoutEffect(() => {
    const el = ref.current;
    if (!open || !el || typeof window === 'undefined') return undefined;
    el.style.transform = '';
    el.style.top = '';
    el.style.bottom = '';
    el.style.marginTop = '';
    const rect = el.getBoundingClientRect();
    const vv = window.visualViewport;
    const gap = parseFloat(getComputedStyle(el).marginTop) || 0;
    const rootStyle = getComputedStyle(document.documentElement);
    const shellTop = (parseFloat(rootStyle.getPropertyValue('--fe-ticker-h')) || 0) + (parseFloat(rootStyle.getPropertyValue('--fe-header-h')) || 0);
    const anchor = el.offsetParent ? el.offsetParent.getBoundingClientRect() : null;
    const plan = planViewportFit(
      { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom },
      {
        width: document.documentElement.clientWidth || window.innerWidth,
        height: vv ? vv.height : window.innerHeight,
        top: shellTop,
        gap,
        anchorTop: anchor ? anchor.top : rect.top - gap,
        bottomClear: readBottomClear(),
      },
      { margin },
    );
    if (plan.dx) el.style.transform = `translateX(${Math.round(plan.dx)}px)`;
    if (plan.flipUp) {
      el.style.top = 'auto';
      el.style.bottom = '100%';
      el.style.marginTop = '0px';
      el.style.marginBottom = `${gap}px`;
    } else if (plan.scrollBy > 0) {
      window.scrollBy({ top: plan.scrollBy, behavior: 'instant' });
    }
    return () => {
      el.style.transform = '';
      el.style.top = '';
      el.style.bottom = '';
      el.style.marginTop = '';
      el.style.marginBottom = '';
    };
  }, [ref, open, margin]);
}
