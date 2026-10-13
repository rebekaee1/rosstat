// Где открыть выпадающее меню, чтобы оно не уходило за край окна (круг 11, зона C).

/** Ширина меню на компьютере (px): min-w 15rem плюс поля. */
export const MENU_WIDTH = 248;
const EDGE = 8;

/**
 * @param {{left:number,right:number,top:number,bottom:number}} rect прямоугольник кнопки
 * @returns {{left:number, up:boolean}} left — сдвиг меню от левого края кнопки (px; 0, если помещается), up — открыть вверх
 */
export function placeMenu(rect, {
  width = MENU_WIDTH, height = 160, viewportW, viewportH,
} = {}) {
  // Меню начинается у левого края кнопки; если справа не хватает места, выравнивается по правому краю кнопки.
  // Раньше меню всегда держалось за правый край: у кнопки слева («Скачать данные» под графиком сравнения)
  // оно уезжало на десятки пикселей влево от кнопки и налезало на соседний блок (круг 13).
  const maxLeft = Math.max(EDGE, viewportW - EDGE - width);
  const wantLeft = rect.left + width > viewportW - EDGE ? rect.right - width : rect.left;
  const left = Math.min(Math.max(wantLeft, EDGE), maxLeft) - rect.left;
  const below = viewportH - rect.bottom;
  const above = rect.top;
  const up = below < height + EDGE && above > below;
  return { left, up };
}
