// Круг 11 (E): выгрузка таблицы калькулятора (график платежей по ипотеке) через POST /export/grid.
// Допуск и лимит гостя те же, что у выгрузки рядов: гость без права скачивать получает событие
// `fe:download-limit`, его подхватывает окно регистрации (components/DownloadLimitModal).
import { exportGrid } from './api';

function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/**
 * grid: { columns:[{key,label,unit?}], rows:[{...}] } (см. scheduleGrid в lib/mortgageSchedule.js).
 * Возвращает 'ok' | 'limit' | 'error'.
 */
export async function downloadGrid({ format = 'csv', filename, title, grid, history }) {
  try {
    // Один вызов `POST /export/grid` на сайт: `exportGrid` из `lib/api.js` (круг 11, интеграция).
    const { blob } = await exportGrid({
      format, filename, title, columns: grid.columns, rows: grid.rows, ...(history ? { history } : {}),
    });
    saveBlob(blob, filename);
    return 'ok';
  } catch (err) {
    if (err?.code === 'download_limit') {
      window.dispatchEvent(new CustomEvent('fe:download-limit'));
      return 'limit';
    }
    return 'error';
  }
}
