// Где открыть выпадающее меню, чтобы оно не уходило за край окна (круг 11, зона C).

/** Ширина меню на компьютере (px): min-w 15rem плюс поля. */
export const MENU_WIDTH = 248;
const EDGE = 8;

/**
 * @param {{left:number,right:number,top:number,bottom:number}} rect прямоугольник кнопки
 * @returns {{left:number, up:boolean}} left — сдвиг меню от левого края кнопки (px), up — открыть вверх
 */
export function placeMenu(rect, {
  width = MENU_WIDTH, height = 160, viewportW, viewportH,
} = {}) {
  const maxLeft = Math.max(EDGE, viewportW - EDGE - width);
  const wantLeft = rect.right - width;
  const left = Math.min(Math.max(wantLeft, EDGE), maxLeft) - rect.left;
  const below = viewportH - rect.bottom;
  const above = rect.top;
  const up = below < height + EDGE && above > below;
  return { left, up };
}
