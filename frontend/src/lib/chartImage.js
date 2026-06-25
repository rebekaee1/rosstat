import { toPng } from 'html-to-image';

// Экспорт DOM-узла графика в PNG. Используется и карточкой индикатора
// (per-indicator), и страницей сравнения. Watermark — управляемый флаг:
// для гостя сравнения и для авторизованного single-chart он включён, для
// сравнения зарегистрированного пользователя — выключен (см. вызовы).
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
export async function exportNodeToPng(node, { filename = 'chart.png', watermark = true, background } = {}) {
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
  const canvas = document.createElement('canvas');
  canvas.width = img.naturalWidth;
  canvas.height = img.naturalHeight;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(img, 0, 0);
  if (watermark) drawWatermark(ctx, canvas.width, canvas.height);
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/png'));
  if (!blob) return false;
  triggerDownload(blob, filename);
  return true;
}
