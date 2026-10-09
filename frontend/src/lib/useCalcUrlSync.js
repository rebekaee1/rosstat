// Круг 11 (E): параметры калькулятора живут в адресе, чтобы смена языка (другой хост), «Поделиться» и сохранённый в кабинете
// расчёт открывали тот же расчёт. Чистый заход адрес не трогает: запись начинается, когда человек что-то изменил.
import { useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';

/** Целое из параметра адреса в границах; не число или вне границ — запасное значение. */
export function intParam(searchParams, key, { min = -Infinity, max = Infinity, fallback }) {
  const raw = searchParams.get(key);
  if (raw == null || raw === '') return fallback;
  const n = Number.parseInt(raw, 10);
  if (!Number.isFinite(n) || n < min || n > max) return fallback;
  return n;
}

/** Число с дробью (ставка 10.5). */
export function floatParam(searchParams, key, { min = -Infinity, max = Infinity, fallback }) {
  const raw = searchParams.get(key);
  if (raw == null || raw === '') return fallback;
  const n = Number.parseFloat(String(raw).replace(',', '.'));
  if (!Number.isFinite(n) || n < min || n > max) return fallback;
  return n;
}

/**
 * values: плоский объект строк/чисел (null и пустая строка пропускаются). Возвращает ничего.
 * Адрес обновляется без новой записи в истории и с задержкой, чтобы бегунок не писал его на каждый пиксель.
 */
export default function useCalcUrlSync(values, { delay = 400, enabled = true } = {}) {
  const [, setSearchParams] = useSearchParams();
  const snapshot = JSON.stringify(values);
  const initial = useRef(snapshot);
  const setterRef = useRef(setSearchParams);
  useEffect(() => { setterRef.current = setSearchParams; });
  useEffect(() => {
    if (!enabled || snapshot === initial.current) return undefined;
    const timer = window.setTimeout(() => {
      const next = new URLSearchParams();
      Object.entries(JSON.parse(snapshot)).forEach(([key, value]) => {
        if (value != null && value !== '') next.set(key, String(value));
      });
      setterRef.current(next, { replace: true });
    }, delay);
    return () => window.clearTimeout(timer);
  }, [snapshot, delay, enabled]);
}
