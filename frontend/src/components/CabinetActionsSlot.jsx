// Слот кнопок кабинета («В избранное» и «Следить») на страницах показателей, стран и регионов (круг 11, F).
// Сами кнопки пишет зона кабинета (SaveButton, WatchButton); страница лишь называет предмет и оставляет место.
// Кнопки приходят двумя путями: пропом `renderActions` (страница, тест) или контекстом `CabinetActionsContext`
// (одна обёртка у корня приложения). Нет ни того ни другого: слот пуст и ничего не занимает.
// Рисуются только после монтирования, чтобы разметка сервера и первый кадр в браузере совпадали (SSR и гидратация).
import { useContext, useSyncExternalStore } from 'react';
import { CabinetActionsContext } from '../lib/cabinetActionsContext';
import '../styles/z4-indicator.css';

const subscribeNever = () => () => {};
/** false при серверной отрисовке и гидратации, true в браузере после неё. */
function useMounted() {
  return useSyncExternalStore(subscribeNever, () => true, () => false);
}

/**
 * @param {{ subject: { kind: string, itemKey: string, title?: string, payload?: object, watch?: { subjectKind: string, subjectKey: string } | null } | null,
 *   renderActions?: ((subject: object) => import('react').ReactNode) | null, className?: string }} props
 */
export default function CabinetActionsSlot({ subject, renderActions = null, className = '' }) {
  const fromContext = useContext(CabinetActionsContext);
  const render = renderActions || fromContext;
  const mounted = useMounted();
  if (!render || !subject || !mounted) return null;
  const node = render(subject);
  if (!node) return null;
  return (
    <div className={`fe-cabinet-actions${className ? ` ${className}` : ''}`} data-testid="cabinet-actions">
      {node}
    </div>
  );
}
