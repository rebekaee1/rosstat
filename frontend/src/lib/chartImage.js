import { toPng } from 'html-to-image';
import { trackBusy } from './chunkRecovery';

// Экспорт DOM-узла графика в PNG. Используется карточкой индикатора,
// страницей сравнения и региональным блоком. Скачивание картинки везде по
// сайту гейтится регистрацией (гостю — окно входа, а не файл), поэтому до
// функции доходят только зарегистрированные — watermark им не ставится
// (решение владельца пересмотрено 2026-07-08, созвон «На правки 13»; до этого
// знак стоял у всех без исключения). Параметр `watermark` оставлен на случай
// будущего негейтированного места экспорта.
//
// Фон берётся из реального computed-стиля узла (тема светлая,
// `--color-surface: #FFFFFF`), а не хардкодом — иначе экспорт уезжал в старый
// тёмный фон, и чёрные подписи осей/заголовок становились нечитаемыми
// (баг светлой темы). Watermark подобран под светлый фон.

const FALLBACK_BG = '#FFFFFF';
const WATERMARK_TEXT = 'forecasteconomy.com';

/** Берёт непрозрачный фон узла; если прозрачный — поднимается по родителям. */
function resolveBackground(node) {
  let el = node;
  for (let i = 0; el && i < 6; i += 1) {
    const bg = getComputedStyle(el).backgroundColor;
    if (bg && bg !== 'transparent' && !/rgba?\(\s*0\s*,\s*0\s*,\s*0\s*,\s*0\s*\)/.test(bg)) {
      return bg;
    }
    el = el.parentElement;
  }
  return FALLBACK_BG;
}

/**
 * Грань бренда: ромб 1:2,1 (как у знака сайта), две половины разного света и белый блик. Рисуется векторно.
 * `size` — высота ромба в пикселях картинки.
 */
function drawFacet(ctx, cx, cy, size) {
  const hh = size / 2;
  const hw = size / 4.2;
  ctx.save();
  ctx.shadowColor = 'rgba(60, 48, 24, 0.35)';
  ctx.shadowBlur = size * 0.35;
  ctx.shadowOffsetY = size * 0.12;
  // Левая половина светлее, правая темнее: так читается как огранённый камень.
  ctx.beginPath();
  ctx.moveTo(cx, cy - hh);
  ctx.lineTo(cx - hw, cy);
  ctx.lineTo(cx, cy + hh);
  ctx.closePath();
  const left = ctx.createLinearGradient(cx - hw, cy - hh, cx, cy + hh);
  left.addColorStop(0, '#FFF3CF');
  left.addColorStop(1, '#D8B561');
  ctx.fillStyle = left;
  ctx.fill();
  ctx.shadowColor = 'transparent';
  ctx.beginPath();
  ctx.moveTo(cx, cy - hh);
  ctx.lineTo(cx + hw, cy);
  ctx.lineTo(cx, cy + hh);
  ctx.closePath();
  const right = ctx.createLinearGradient(cx, cy - hh, cx + hw, cy + hh);
  right.addColorStop(0, '#C9A24D');
  right.addColorStop(1, '#8F6B24');
  ctx.fillStyle = right;
  ctx.fill();
  ctx.beginPath();
  ctx.moveTo(cx - hw * 0.45, cy - hh * 0.25);
  ctx.lineTo(cx - hw * 0.1, cy - hh * 0.62);
  ctx.lineTo(cx - hw * 0.02, cy - hh * 0.2);
  ctx.closePath();
  ctx.fillStyle = 'rgba(255, 255, 255, 0.6)';
  ctx.fill();
  ctx.restore();
}

/**
 * Водяной знак: грань и адрес сайта в правом нижнем углу, прозрачность 0,35. Крупной диагональной плитки больше нет:
 * знак не спорит с графиком и не похож на штамп.
 */
function drawWatermark(ctx, w, h) {
  ctx.save();
  ctx.globalAlpha = 0.35;
  const tagPx = Math.max(14, Math.round(w / 56));
  ctx.font = `700 ${tagPx}px Manrope, Inter, system-ui, sans-serif`;
  ctx.textAlign = 'right';
  ctx.textBaseline = 'middle';
  const x = w - tagPx;
  const y = h - tagPx * 1.4;
  ctx.fillStyle = '#6B5224';
  ctx.fillText(WATERMARK_TEXT, x, y);
  const textW = ctx.measureText(WATERMARK_TEXT).width;
  drawFacet(ctx, x - textW - tagPx * 0.9, y, tagPx * 1.5);
  ctx.restore();
}

/** Скруглённый прямоугольник без зависимостей от `ctx.roundRect` (его нет в старых Safari). */
function roundedRectPath(ctx, x, y, w, h, r) {
  const rr = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + rr, y);
  ctx.arcTo(x + w, y, x + w, y + h, rr);
  ctx.arcTo(x + w, y + h, x, y + h, rr);
  ctx.arcTo(x, y + h, x, y, rr);
  ctx.arcTo(x, y, x + w, y, rr);
  ctx.closePath();
}

/** Режет строку по ширине: подпись в картинке не должна вылезать за край. */
function fitText(ctx, text, maxWidth) {
  const source = String(text || '');
  if (ctx.measureText(source).width <= maxWidth) return source;
  let out = source;
  while (out.length > 1 && ctx.measureText(`${out}…`).width > maxWidth) out = out.slice(0, -1);
  return `${out.trimEnd()}…`;
}

// Знак бренда (как favicon.svg): буква F; грань на месте точки рисует drawFacet. Всё векторно, без загрузки файла.
const MARK_F = 'M12 38V17Q12 5 25 5H38V13H26Q21 13 21 19V20H35V28H21V38Z';

/**
 * Фирменная картинка графика (K4.7): ивори-поле с тёплыми каустиками, график на стеклянной плите (блик сверху, мягкая тень),
 * знак и слово бренда с гранью, название и подпись, внизу источник и адрес сайта. Линий и рамок нет: плиту отделяют
 * светлота, блик и тень. Цвета фиксированные (картинка живёт вне сайта и темы).
 */
function composeFramedCanvas(img, { title = '', subtitle = '', source = '', site = WATERMARK_TEXT } = {}) {
  const unit = 2; // один css-пиксель в итоговой картинке: снимок сделан с pixelRatio 2
  const pad = 28 * unit;
  const slab = 10 * unit; // толщина стеклянной плиты вокруг снимка
  const headH = (title ? 96 : 62) * unit;
  const footH = 52 * unit;
  const radius = 18 * unit;
  const width = img.naturalWidth + pad * 2 + slab * 2;
  const height = img.naturalHeight + headH + footH + slab * 2 + pad * 0.5;
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(width);
  canvas.height = Math.round(height);
  const ctx = canvas.getContext('2d');

  // Поле: бумага ивори и три каустики (золото справа сверху, лёд слева, роза внизу).
  ctx.fillStyle = '#F6F2EA';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  const caustic = (x, y, r, color) => {
    const g = ctx.createRadialGradient(x, y, 0, x, y, r);
    g.addColorStop(0, color);
    g.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
  };
  caustic(canvas.width * 0.88, canvas.height * 0.02, canvas.width * 0.6, 'rgba(246, 231, 190, 0.75)');
  caustic(canvas.width * 0.04, canvas.height * 0.45, canvas.width * 0.5, 'rgba(191, 224, 245, 0.45)');
  caustic(canvas.width * 0.5, canvas.height * 1.02, canvas.width * 0.55, 'rgba(244, 198, 216, 0.28)');

  // Знак и слово бренда: буква F и грань вместо золотой точки.
  const markSize = 30 * unit;
  ctx.save();
  ctx.translate(pad, 20 * unit);
  ctx.scale(markSize / 48, markSize / 48);
  if (typeof Path2D === 'function') {
    ctx.fillStyle = '#202A3C';
    ctx.fill(new Path2D(MARK_F));
  }
  ctx.restore();
  drawFacet(ctx, pad + markSize * (36 / 48), 20 * unit + markSize * (34 / 48), markSize * 0.34);
  ctx.textBaseline = 'middle';
  ctx.textAlign = 'left';
  const wordX = pad + markSize + 10 * unit;
  const wordY = 20 * unit + markSize / 2;
  ctx.font = `700 ${19 * unit}px Manrope, system-ui, sans-serif`;
  ctx.fillStyle = '#202A3C';
  ctx.fillText('forecast', wordX, wordY);
  const forecastW = ctx.measureText('forecast').width;
  ctx.font = `400 ${19 * unit}px Manrope, system-ui, sans-serif`;
  ctx.fillText('economy', wordX + forecastW, wordY);

  // Название и подпись.
  const textMax = canvas.width - pad * 2;
  if (title) {
    ctx.font = `700 ${22 * unit}px Manrope, system-ui, sans-serif`;
    ctx.fillStyle = '#202A3C';
    ctx.fillText(fitText(ctx, title, textMax), pad, 66 * unit);
  }
  if (subtitle) {
    ctx.font = `500 ${13 * unit}px Manrope, system-ui, sans-serif`;
    ctx.fillStyle = '#55627A';
    ctx.textAlign = 'right';
    ctx.fillText(fitText(ctx, subtitle, textMax * 0.5), canvas.width - pad, wordY);
    ctx.textAlign = 'left';
  }

  // Стеклянная плита: полупрозрачная белая, мягкая тень снизу, блик по верхней кромке (заливкой, не линией).
  const plateX = pad;
  const plateY = headH;
  const plateW = img.naturalWidth + slab * 2;
  const plateH = img.naturalHeight + slab * 2;
  ctx.save();
  ctx.shadowColor = 'rgba(60, 48, 24, 0.3)';
  ctx.shadowBlur = 36 * unit;
  ctx.shadowOffsetY = 14 * unit;
  roundedRectPath(ctx, plateX, plateY, plateW, plateH, radius + slab * 0.6);
  ctx.fillStyle = 'rgba(255, 255, 255, 0.62)';
  ctx.fill();
  ctx.restore();
  ctx.save();
  roundedRectPath(ctx, plateX, plateY, plateW, plateH, radius + slab * 0.6);
  ctx.clip();
  const sheen = ctx.createLinearGradient(plateX, plateY, plateX + plateW * 0.55, plateY + plateH * 0.55);
  sheen.addColorStop(0, 'rgba(255, 255, 255, 0.7)');
  sheen.addColorStop(1, 'rgba(255, 255, 255, 0)');
  ctx.fillStyle = sheen;
  ctx.fillRect(plateX, plateY, plateW, plateH);
  const glint = ctx.createLinearGradient(0, plateY, 0, plateY + 6 * unit);
  glint.addColorStop(0, 'rgba(255, 255, 255, 0.95)');
  glint.addColorStop(1, 'rgba(255, 255, 255, 0)');
  ctx.fillStyle = glint;
  ctx.fillRect(plateX, plateY, plateW, 6 * unit);
  ctx.restore();

  // Снимок графика внутри плиты.
  const cardX = plateX + slab;
  const cardY = plateY + slab;
  ctx.save();
  roundedRectPath(ctx, cardX, cardY, img.naturalWidth, img.naturalHeight, radius);
  ctx.clip();
  ctx.drawImage(img, cardX, cardY);
  ctx.restore();

  // Подвал: источник слева, грань и адрес сайта справа.
  const footY = plateY + plateH + footH / 2 + 2 * unit;
  ctx.font = `500 ${13 * unit}px Manrope, system-ui, sans-serif`;
  ctx.fillStyle = '#55627A';
  ctx.textAlign = 'left';
  if (source) ctx.fillText(fitText(ctx, source, textMax * 0.62), pad, footY);
  ctx.textAlign = 'right';
  ctx.font = `700 ${13 * unit}px Manrope, system-ui, sans-serif`;
  ctx.fillStyle = '#7A5F2A';
  ctx.fillText(site, canvas.width - pad, footY);
  const siteW = ctx.measureText(site).width;
  drawFacet(ctx, canvas.width - pad - siteW - 12 * unit, footY, 17 * unit);
  return canvas;
}

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 100);
}

/**
 * Рендерит узел в PNG (опц. с watermark) и сохраняет файл.
 * @returns {Promise<boolean>} успех
 */
async function exportNodeToPngImpl(node, {
  filename = 'chart.png', watermark = false, background, frame = null,
} = {}) {
  if (!node) return false;
  const bg = background || resolveBackground(node);
  const dataUrl = await toPng(node, {
    pixelRatio: 2,
    backgroundColor: bg,
    cacheBust: true,
    // Элементы с data-no-export не попадают в картинку (кнопки тулбара и т.п.).
    filter: (el) => !(el?.dataset && el.dataset.noExport === 'true'),
  });
  const img = new Image();
  await new Promise((resolve, reject) => {
    img.onload = resolve;
    img.onerror = reject;
    img.src = dataUrl;
  });
  let canvas;
  if (frame) {
    // Фирменная рамка: знак, название, источник, адрес сайта (опция `frame`, остальные места экспорта её не передают).
    canvas = composeFramedCanvas(img, frame);
  } else {
    canvas = document.createElement('canvas');
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0);
    if (watermark) drawWatermark(canvas.getContext('2d'), canvas.width, canvas.height);
  }
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/png'));
  if (!blob) return false;
  triggerDownload(blob, filename);
  return true;
}

// Идущий экспорт не должен обрываться автоперезагрузкой после релиза (chunkRecovery).
export const exportNodeToPng = (...args) => trackBusy(exportNodeToPngImpl(...args));
