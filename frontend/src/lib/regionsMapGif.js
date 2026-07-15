// Клиентская генерация GIF: choropleth по годам из heatmap-series.
// Рисует на offscreen canvas теми же путями/квантилями, что и RegionsMap —
// живую карту не дёргаем. Watermark не ставится (скачивание только для
// зарегистрированных; бренд на live-UI — отдельно, data-no-export).
import { GIFEncoder, quantize, applyPalette } from 'gifenc';
import mapData from './regionsMap.json';
import { colorsBySlug, valueExtent, MAP_SCALE, MAP_NO_DATA } from './regionsMapColors';
import { formatRegionValue } from './regionsApi';

export const GIF_FRAME_MS = 650;

/** Логический размер кадра; canvas × DPR → реальные пиксели. */
export const GIF_LOGICAL_W = 960;
export const GIF_LOGICAL_H = 560;
export const GIF_DPR = 2;

const PAD = 20;
const TOP_H = 44;
const BOTTOM_H = 56;
const YEAR_SIZE = 56;
const TITLE_SIZE = 15;
const LEGEND_LABEL_SIZE = 12;

function parseViewBox(vb) {
  const [x, y, w, h] = vb.split(' ').map(Number);
  return { x, y, w, h };
}

function truncateTitle(ctx, title, maxWidth) {
  if (!title) return '';
  if (ctx.measureText(title).width <= maxWidth) return title;
  const ell = '…';
  let lo = 0;
  let hi = title.length;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (ctx.measureText(title.slice(0, mid) + ell).width <= maxWidth) lo = mid;
    else hi = mid - 1;
  }
  return title.slice(0, lo) + ell;
}

/**
 * Полная перерисовка кадра: фон → карта → год по центру → легенда.
 * Предыдущий кадр не композится (dispose:2 + clearRect).
 */
export function drawFrame(ctx, {
  colorMap,
  year,
  title,
  extent,
  unit = '',
  width = GIF_LOGICAL_W,
  height = GIF_LOGICAL_H,
  dpr = 1,
}) {
  const W = width;
  const H = height;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = '#FFFFFF';
  ctx.fillRect(0, 0, W, H);

  const mapTop = TOP_H;
  const mapBottom = H - BOTTOM_H;
  const mapH = mapBottom - mapTop;

  const vb = parseViewBox(mapData.viewBox);
  const scale = Math.min((W - PAD * 2) / vb.w, mapH / vb.h);
  const ox = (W - vb.w * scale) / 2 - vb.x * scale;
  const oy = mapTop + (mapH - vb.h * scale) / 2 - vb.y * scale;

  // Подложка-«шов» своим цветом — как seal-слой в SVG.
  ctx.save();
  ctx.translate(ox, oy);
  ctx.scale(scale, scale);
  for (const r of mapData.regions) {
    const color = colorMap.get(r.slug) ?? MAP_NO_DATA;
    const path = new Path2D(r.path);
    ctx.fillStyle = color;
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.6;
    ctx.lineJoin = 'round';
    ctx.fill(path);
    ctx.stroke(path);
  }
  for (const r of mapData.regions) {
    const color = colorMap.get(r.slug) ?? MAP_NO_DATA;
    const path = new Path2D(r.path);
    ctx.fillStyle = color;
    ctx.strokeStyle = 'rgba(26,26,46,0.22)';
    ctx.lineWidth = 0.55 / scale;
    ctx.lineJoin = 'round';
    ctx.fill(path);
    ctx.stroke(path);
  }
  for (const m of mapData.markers) {
    const color = colorMap.get(m.slug) ?? MAP_NO_DATA;
    ctx.beginPath();
    ctx.arc(m.cx, m.cy, 7.5 / scale, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
    ctx.strokeStyle = 'rgba(26,26,46,0.45)';
    ctx.lineWidth = 1.5 / scale;
    ctx.stroke();
  }
  ctx.restore();

  // Заголовок показателя — сверху, без года (год только по центру).
  if (title) {
    ctx.fillStyle = '#3A3A4A';
    ctx.font = `500 ${TITLE_SIZE}px Inter, system-ui, sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(truncateTitle(ctx, title, W - PAD * 2), W / 2, TOP_H / 2);
  }

  // Один год — по центру области карты (не в углу, не дубль).
  const yearCx = W / 2;
  const yearCy = mapTop + mapH * 0.48;
  ctx.font = `700 ${YEAR_SIZE}px Inter, system-ui, sans-serif`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.lineJoin = 'round';
  ctx.lineWidth = 6;
  ctx.strokeStyle = 'rgba(255,255,255,0.92)';
  ctx.strokeText(String(year), yearCx, yearCy);
  ctx.fillStyle = '#1A1A2E';
  ctx.fillText(String(year), yearCx, yearCy);

  drawLegend(ctx, {
    extent,
    unit,
    width: W,
    height: H,
    bottomH: BOTTOM_H,
    pad: PAD,
  });
}

function drawLegend(ctx, { extent, unit, width: W, height: H, bottomH, pad }) {
  const barH = 10;
  const barW = Math.min(320, W - pad * 2 - 120);
  const barX = (W - barW) / 2;
  const barY = H - bottomH + 18;
  const segW = barW / MAP_SCALE.length;

  for (let i = 0; i < MAP_SCALE.length; i += 1) {
    ctx.fillStyle = MAP_SCALE[i];
    ctx.fillRect(barX + i * segW, barY, segW + 0.5, barH);
  }
  ctx.strokeStyle = 'rgba(26,26,46,0.2)';
  ctx.lineWidth = 1;
  ctx.strokeRect(barX, barY, barW, barH);

  ctx.fillStyle = '#5A5A6A';
  ctx.font = `500 ${LEGEND_LABEL_SIZE}px Inter, system-ui, sans-serif`;
  ctx.textBaseline = 'top';
  const labelY = barY + barH + 6;

  if (extent) {
    const minL = formatRegionValue(extent.min);
    const maxL = formatRegionValue(extent.max);
    const unitSuffix = unit ? ` ${unit}` : '';
    ctx.textAlign = 'left';
    ctx.fillText(minL, barX, labelY);
    ctx.textAlign = 'right';
    ctx.fillText(`${maxL}${unitSuffix}`, barX + barW, labelY);
  } else {
    ctx.textAlign = 'left';
    ctx.fillText('нет данных', barX, labelY);
  }
}

/**
 * Собирает GIF по годам series (ответ /regions/heatmap-series/{code}).
 * @param {{ years: number[], values_by_year: Record<string, Record<string, number>>, indicator?: { name?: string, unit?: string } }} series
 * @param {{ frameMs?: number, onProgress?: (i: number, n: number) => void }} [opts]
 * @returns {Promise<Blob>}
 */
export async function buildRegionsMapGif(series, { frameMs = GIF_FRAME_MS, onProgress } = {}) {
  const years = series?.years || [];
  if (years.length < 2) throw new Error('need_at_least_two_years');

  const dpr = GIF_DPR;
  const W = GIF_LOGICAL_W;
  const H = GIF_LOGICAL_H;
  const pxW = W * dpr;
  const pxH = H * dpr;

  const canvas = document.createElement('canvas');
  canvas.width = pxW;
  canvas.height = pxH;
  const ctx = canvas.getContext('2d', { willReadFrequently: true, alpha: false });
  const title = series.indicator?.name || '';
  const unit = series.indicator?.unit || '';

  const gif = GIFEncoder();
  // gifenc: delay в миллисекундах (внутри /10 → 1/100 с).
  const delayMs = Math.max(20, Math.round(frameMs));

  for (let i = 0; i < years.length; i += 1) {
    const year = years[i];
    const slice = series.values_by_year[String(year)] || {};
    const colorMap = colorsBySlug(slice);
    const extent = valueExtent(slice);
    drawFrame(ctx, {
      colorMap, year, title, extent, unit, width: W, height: H, dpr,
    });

    const { data } = ctx.getImageData(0, 0, pxW, pxH);
    // rgb565 — лучшее качество среди форматов gifenc для плоских цветов карты.
    const palette = quantize(data, 256, { format: 'rgb565' });
    const index = applyPalette(data, palette, 'rgb565');
    // dispose:2 — восстановить фон перед следующим кадром (нет ghosting годов).
    gif.writeFrame(index, pxW, pxH, {
      palette,
      delay: delayMs,
      dispose: 2,
      repeat: 0,
    });
    onProgress?.(i + 1, years.length);
    await new Promise((r) => setTimeout(r, 0));
  }

  gif.finish();
  // Копия в новый ArrayBuffer — стабильный Blob в браузере и в тестах.
  const raw = gif.bytes();
  const copy = new Uint8Array(raw.byteLength);
  copy.set(raw);
  return new Blob([copy.buffer], { type: 'image/gif' });
}

export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename.endsWith('.gif') ? filename : `${filename}.gif`;
  a.type = 'image/gif';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 100);
}
