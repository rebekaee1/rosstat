// Состояние подсказки «коснитесь графика»: показывается на сенсорных экранах, пока человек
// ни разу не коснулся графика на этом устройстве. Хранение — localStorage в try/catch.
import { useCallback, useState } from 'react';
import { useCoarsePointer } from './chartHooks';

const STORAGE_KEY = 'fe-chart-touch-hint';

function wasSeen() {
  try { return window.localStorage.getItem(STORAGE_KEY) === '1'; } catch { return false; }
}

export function useChartTouchHint() {
  const coarse = useCoarsePointer();
  const [done, setDone] = useState(wasSeen);
  const dismiss = useCallback(() => {
    setDone((prev) => {
      if (!prev) { try { window.localStorage.setItem(STORAGE_KEY, '1'); } catch { /* ok */ } }
      return true;
    });
  }, []);
  return { visible: coarse && !done, dismiss };
}
