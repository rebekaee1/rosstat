import { useEffect } from 'react';

// Круг 8 (R8-D): последние курсы лежат в памяти телефона.
const SAVED_KEY = 'fe.cur.saved.v1';

/** Последние полученные курсы лежат в памяти телефона: при обрыве связи в аэропорту человек видит их с датой, а не пустую страницу. */
export function readSavedRates() {
  try {
    const raw = JSON.parse(window.localStorage.getItem(SAVED_KEY) || 'null');
    return raw && Array.isArray(raw.items) && raw.items.length ? raw : null;
  } catch { return null; }
}

export function useSaveRates(indicators) {
  useEffect(() => {
    if (!Array.isArray(indicators) || indicators.length < 3) return;
    try {
      const items = indicators.map((i) => ({
        code: i.code, name: i.name, name_en: i.name_en, unit: i.unit,
        current_value: i.current_value, current_date: i.current_date, change: i.change,
      }));
      window.localStorage.setItem(SAVED_KEY, JSON.stringify({ at: new Date().toISOString(), items }));
    } catch { /* память телефона закрыта или полна: страница работает и без неё */ }
  }, [indicators]);
}
