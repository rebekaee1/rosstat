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

function drawWatermark(ctx, w, h) {
  ctx.save();
  // Диагональная плитка — мягкая, не мешает читать график (тёмная под светлый фон).
  ctx.globalAlpha = 0.05;
  ctx.fillStyle = '#1A1A2E';
  const fontPx = Math.max(18, Math.round(w / 36));
  ctx.font = `600 ${fontPx}px Inter, system-ui, sans-serif`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.translate(w / 2, h / 2);
  ctx.rotate(-Math.atan2(h, w));
  const stepX = ctx.measureText(WATERMARK_TEXT).width + fontPx * 3;
  const stepY = fontPx * 4;
  const diag = Math.ceil(Math.sqrt(w * w + h * h));
  for (let y = -diag; y < diag; y += stepY) {
    for (let x = -diag; x < diag; x += stepX) {
      ctx.fillText(WATERMARK_TEXT, x, y);
    }
  }
  ctx.restore();

  // Чёткая подпись-«копирайт» в правом нижнем углу — всегда читаемая (champagne-muted под светлый фон).
  ctx.save();
  ctx.globalAlpha = 0.9;
  const tagPx = Math.max(14, Math.round(w / 64));
  ctx.font = `600 ${tagPx}px Inter, system-ui, sans-serif`;
  ctx.textAlign = 'right';
  ctx.textBaseline = 'bottom';
  ctx.fillStyle = 'rgba(139, 115, 48, 0.95)';
  ctx.fillText(WATERMARK_TEXT, w - tagPx, h - tagPx);
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

// Знак бренда (как favicon.svg): буква F и золотая точка; рисуется векторно, без загрузки файла.
const MARK_F = 'M12 38V17Q12 5 25 5H38V13H26Q21 13 21 19V20H35V28H21V38Z';
const MARK_DOT = 'M33 30H39V38H33Z';

/**
 * Фирменная рамка вокруг снимка графика: знак и слово бренда сверху, название и подпись,
 * тонкая золотая линия, внизу источник и адрес сайта. Цвета фиксированные (картинка живёт вне сайта и темы).
 */
function composeFramedCanvas(img, { title = '', subtitle = '', source = '', site = WATERMARK_TEXT } = {}) {
  const unit = 2; // один css-пиксель в итоговой картинке: снимок сделан с pixelRatio 2
  const pad = 28 * unit;
  const headH = (title ? 96 : 62) * unit;
  const footH = 52 * unit;
  const radius = 18 * unit;
  const width = img.naturalWidth + pad * 2;
  const height = img.naturalHeight + headH + footH + pad * 0.5;
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(width);
  canvas.height = Math.round(height);
  const ctx = canvas.getContext('2d');

  const paper = ctx.createLinearGradient(0, 0, canvas.width, canvas.height);
  paper.addColorStop(0, '#FBF8F1');
  paper.addColorStop(1, '#F1EDE3');
  ctx.fillStyle = paper;
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  // Тонкая золотая линия сверху.
  const gold = ctx.createLinearGradient(0, 0, canvas.width, 0);
  gold.addColorStop(0, 'rgba(173,138,72,0)');
  gold.addColorStop(0.2, '#C9A24D');
  gold.addColorStop(0.8, '#AD8A48');
  gold.addColorStop(1, 'rgba(173,138,72,0)');
  ctx.fillStyle = gold;
  ctx.fillRect(0, 0, canvas.width, 3 * unit);

  // Знак и слово бренда.
  const markSize = 30 * unit;
  ctx.save();
  ctx.translate(pad, 20 * unit);
  ctx.scale(markSize / 48, markSize / 48);
  if (typeof Path2D === 'function') {
    ctx.fillStyle = '#202A3C';
    ctx.fill(new Path2D(MARK_F));
    ctx.fillStyle = '#AD8A48';
    ctx.fill(new Path2D(MARK_DOT));
  }
  ctx.restore();
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
    ctx.fillStyle = '#59697F';
    ctx.textAlign = 'right';
    ctx.fillText(fitText(ctx, subtitle, textMax * 0.5), canvas.width - pad, wordY);
    ctx.textAlign = 'left';
  }

  // Снимок графика в скруглённой белой плашке.
  const cardX = pad;
  const cardY = headH;
  ctx.save();
  ctx.shadowColor = 'rgba(32,42,60,0.18)';
  ctx.shadowBlur = 24 * unit;
  ctx.shadowOffsetY = 8 * unit;
  ctx.fillStyle = '#FFFFFF';
  roundedRectPath(ctx, cardX, cardY, img.naturalWidth, img.naturalHeight, radius);
  ctx.fill();
  ctx.restore();
  ctx.save();
  roundedRectPath(ctx, cardX, cardY, img.naturalWidth, img.naturalHeight, radius);
  ctx.clip();
  ctx.drawImage(img, cardX, cardY);
  ctx.restore();

  // Подвал: источник слева, адрес сайта справа.
  const footY = headH + img.naturalHeight + footH / 2 + 2 * unit;
  ctx.font = `500 ${13 * unit}px Manrope, system-ui, sans-serif`;
  ctx.fillStyle = '#59697F';
  ctx.textAlign = 'left';
  if (source) ctx.fillText(fitText(ctx, source, textMax * 0.62), pad, footY);
  ctx.textAlign = 'right';
  ctx.font = `700 ${13 * unit}px Manrope, system-ui, sans-serif`;
  ctx.fillStyle = '#80642F';
  ctx.fillText(site, canvas.width - pad, footY);
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
