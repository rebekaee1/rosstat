// Клиентская генерация GIF: choropleth по годам из heatmap-series.
// Рисует на offscreen canvas теми же путями/квантилями, что и RegionsMap —
// живую карту не дёргаем. Watermark не ставится (скачивание только для
// зарегистрированных; бренд на live-UI — отдельно, data-no-export).
import { GIFEncoder, quantize, applyPalette } from 'gifenc';
import mapData from './regionsMap.json';
import { colorsBySlug, MAP_NO_DATA } from './regionsMapColors';

export const GIF_FRAME_MS = 650;
const W = 720;
const H = 420;
const PAD = 16;

function parseViewBox(vb) {
  const [x, y, w, h] = vb.split(' ').map(Number);
  return { x, y, w, h };
}

function drawFrame(ctx, { colorMap, year, title }) {
  const vb = parseViewBox(mapData.viewBox);
  ctx.fillStyle = '#FFFFFF';
  ctx.fillRect(0, 0, W, H);

  const scale = Math.min((W - PAD * 2) / vb.w, (H - PAD * 2 - 36) / vb.h);
  const ox = (W - vb.w * scale) / 2 - vb.x * scale;
  const oy = PAD + 28 - vb.y * scale;

  ctx.save();
  ctx.translate(ox, oy);
  ctx.scale(scale, scale);

  for (const r of mapData.regions) {
    const color = colorMap.get(r.slug) ?? MAP_NO_DATA;
    const path = new Path2D(r.path);
    ctx.fillStyle = color;
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.4;
    ctx.fill(path);
    ctx.stroke(path);
  }
  for (const r of mapData.regions) {
    const color = colorMap.get(r.slug) ?? MAP_NO_DATA;
    const path = new Path2D(r.path);
    ctx.fillStyle = color;
    ctx.strokeStyle = 'rgba(26,26,46,0.18)';
    ctx.lineWidth = 0.5 / scale;
    ctx.fill(path);
    ctx.stroke(path);
  }
  for (const m of mapData.markers) {
    const color = colorMap.get(m.slug) ?? MAP_NO_DATA;
    ctx.beginPath();
    ctx.arc(m.cx, m.cy, 7 / scale, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
    ctx.strokeStyle = 'rgba(26,26,46,0.45)';
    ctx.lineWidth = 1.4 / scale;
    ctx.stroke();
  }
  ctx.restore();

  ctx.fillStyle = '#1A1A2E';
  ctx.font = '600 15px Inter, system-ui, sans-serif';
  ctx.textAlign = 'left';
  ctx.textBaseline = 'top';
  const label = title ? `${title} · ${year}` : String(year);
  ctx.fillText(label, PAD, 10);

  ctx.fillStyle = '#B8942F';
  ctx.font = '700 22px Inter, system-ui, sans-serif';
  ctx.textAlign = 'right';
  ctx.fillText(String(year), W - PAD, 8);
}

/**
 * Собирает GIF по годам series (ответ /regions/heatmap-series/{code}).
 * @param {{ years: number[], values_by_year: Record<string, Record<string, number>>, indicator?: { name?: string } }} series
 * @param {{ frameMs?: number, onProgress?: (i: number, n: number) => void }} [opts]
 * @returns {Promise<Blob>}
 */
export async function buildRegionsMapGif(series, { frameMs = GIF_FRAME_MS, onProgress } = {}) {
  const years = series?.years || [];
  if (years.length < 2) throw new Error('need_at_least_two_years');

  const canvas = document.createElement('canvas');
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  const title = series.indicator?.name || '';

  const gif = GIFEncoder();
  const delay = Math.max(2, Math.round(frameMs / 10)); // GIF delay в 1/100 с

  for (let i = 0; i < years.length; i += 1) {
    const year = years[i];
    const slice = series.values_by_year[String(year)] || {};
    const colorMap = colorsBySlug(slice);
    drawFrame(ctx, { colorMap, year, title });
    const { data } = ctx.getImageData(0, 0, W, H);
    const palette = quantize(data, 256);
    const index = applyPalette(data, palette);
    gif.writeFrame(index, W, H, { palette, delay });
    onProgress?.(i + 1, years.length);
    // Даём UI дышать между кадрами (длинные ряды 1990–2024).
    await new Promise((r) => setTimeout(r, 0));
  }

  gif.finish();
  return new Blob([gif.bytes()], { type: 'image/gif' });
}

export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 100);
}
