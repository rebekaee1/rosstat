// Круг 11 (E): место кнопки «Сохранить расчёт» в калькуляторах. Саму кнопку кабинета (SaveButton) пишет зона B;
// пока файла components/cabinet/SaveButton.jsx нет, слот не рисует ничего, а когда он появится, подхватывает его без правок.
// Контракт зоны B: <SaveButton kind itemKey title payload />. Страница калькулятора может передать свой `renderSave`.
import { useMemo } from 'react';

const found = import.meta.glob('./cabinet/SaveButton.jsx', { eager: true });
const SaveButton = Object.values(found)[0]?.default || null;

/**
 * kind: 'calc'; itemKey: стабильная строка расчёта («inflation:russia:1991-2026:100000»);
 * payload: параметры из адреса страницы (то, что нужно, чтобы открыть тот же расчёт).
 */
export default function CalcSaveSlot({ itemKey, title, payload, renderSave, className }) {
  const props = useMemo(() => ({ kind: 'calc', itemKey, title, payload }), [itemKey, title, payload]);
  if (typeof renderSave === 'function') return renderSave(props);
  if (!SaveButton) return null;
  return (
    <div className={className} data-testid="calc-save-slot">
      <SaveButton {...props} />
    </div>
  );
}
