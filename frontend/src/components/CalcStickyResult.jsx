// Результат калькулятора, который «липнет» снизу на телефоне и планшете (раунд 3, K8.3).
// Пока человек двигает ползунки и поля, сам блок результата остаётся ниже экрана; плашка показывает то же число
// над нижней кромкой (над доком: отступ задаёт переменная --fe-dock-h) и по нажатию прокручивает к блоку.
// Плашка живёт в document.body: backdrop-filter у родителей сделал бы fixed относительным к ним, а не к окну.
// На широком экране (от 1024 px) результат стоит рядом с формой, плашка скрыта стилями (styles/k8-tools.css).
import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { ArrowDown } from 'lucide-react';
import { useT } from '../i18n';
import '../styles/k8-tools.css';

/**
 * targetRef: ref блока результата; value: готовая строка («57 991 ₽»); active: результат есть и не грузится;
 * label: короткая подпись над числом (по умолчанию «Результат»).
 */
export default function CalcStickyResult({ targetRef, value, active = true, label }) {
  const t = useT();
  const [outOfView, setOutOfView] = useState(false);

  useEffect(() => {
    const node = targetRef?.current;
    // Без наблюдателя плашка не показывается (outOfView остаётся false); при смене active IO отдаёт актуальное значение сразу.
    if (!active || !node || typeof IntersectionObserver !== 'function') return undefined;
    const io = new IntersectionObserver(([entry]) => setOutOfView(!entry.isIntersecting), { threshold: 0.05 });
    io.observe(node);
    return () => io.disconnect();
  }, [targetRef, active]);

  if (!active || !outOfView || !value || typeof document === 'undefined') return null;

  const shownLabel = label || t('k8.sticky.label');
  const goToResult = () => {
    const node = targetRef?.current;
    if (!node || typeof node.scrollIntoView !== 'function') return;
    const reduced = typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    node.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'center' });
  };

  return createPortal(
    <button
      type="button"
      className="fe-k8-sticky"
      data-testid="calc-sticky-result"
      aria-label={t('k8.sticky.aria', { value })}
      onClick={goToResult}
    >
      <span className="min-w-0">
        <span className="fe-k8-sticky__label block">{shownLabel}</span>
        <span className="fe-k8-sticky__value fe-k8-engraved block">{value}</span>
      </span>
      <span className="fe-k8-sticky__go" aria-hidden="true"><ArrowDown size={20} /></span>
    </button>,
    document.body,
  );
}
