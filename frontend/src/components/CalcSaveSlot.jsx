// Круг 11 (E, подключение — интеграция): кнопка «Сохранить расчёт» в карточке результата калькулятора.
// Кнопка общая (`components/cabinet/SaveButton.jsx`, вид записи `calc`). Пока кабинет выключен на сервере или ответа
// о нём нет, слот не рисует ничего, даже пустой обёртки с отступом. Страница может передать свой `renderSave`.
import { useMemo } from 'react';
import { useT } from '../i18n';
import { useCabinetConfig } from '../lib/useCabinet';
import { calcSavedPath } from '../lib/cabinetWiring';
import SaveButton from './cabinet/SaveButton';

/**
 * kind: 'calc'; itemKey: стабильная строка расчёта («inflation:russia:1991-2026:100000»);
 * payload: параметры расчёта (`page` и поля адреса); адрес для «Открыть» собирается из них (`payload.path`).
 */
export default function CalcSaveSlot({ itemKey, title, payload, renderSave, className }) {
  const t = useT();
  const { enabled } = useCabinetConfig();
  const props = useMemo(() => {
    const path = payload?.path || calcSavedPath(payload);
    return { kind: 'calc', itemKey, title, payload: path ? { ...payload, path } : payload };
  }, [itemKey, title, payload]);
  if (typeof renderSave === 'function') return renderSave(props);
  if (!enabled || !itemKey) return null;
  return (
    <div className={className} data-testid="calc-save-slot">
      <SaveButton {...props} variant="button" label={t('c11i.calc.save')} />
    </div>
  );
}
