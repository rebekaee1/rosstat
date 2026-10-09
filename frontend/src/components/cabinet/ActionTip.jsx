import { useEffect, useLayoutEffect, useRef } from 'react';
import { Link, useInRouterContext } from 'react-router-dom';
import { X } from 'lucide-react';
import { useT } from '../../i18n';

/** Ссылка, которая работает и внутри маршрутизатора, и без него (кнопки подключают в тестах без `Router`). */
export function SoftLink({ to, children, ...rest }) {
  const inRouter = useInRouterContext();
  return inRouter ? <Link to={to} {...rest}>{children}</Link> : <a href={to} {...rest}>{children}</a>;
}

/**
 * Короткая подсказка под кнопкой («Сохранено в этом браузере. Войдите…»). Без размытия и рамки: плотная плита с тенью.
 * Исчезает сама через `ttl` мс; прижимается к тому краю кнопки, где хватает места.
 * `tip`: `{ text, tone?: 'info'|'warn', to?, toLabel? }` или null.
 */
export default function ActionTip({ tip, onClose, ttl = 9000 }) {
  const t = useT();
  const ref = useRef(null);

  useEffect(() => {
    if (!tip || !ttl) return undefined;
    const id = window.setTimeout(() => onClose?.(), ttl);
    return () => window.clearTimeout(id);
  }, [tip, ttl, onClose]);

  useLayoutEffect(() => {
    if (!tip || !ref.current) return;
    try {
      const box = ref.current.parentElement.getBoundingClientRect();
      // Кнопка у левого края окна: подсказка вправо от неё, иначе влево (к правому краю кнопки).
      ref.current.dataset.align = box.right < 300 ? 'start' : 'end';
    } catch { /* без измерений остаётся выравнивание по правому краю */ }
  }, [tip]);

  if (!tip) return null;
  return (
    <span ref={ref} role="status" className={`c11b-tip c11b-tip--${tip.tone || 'info'}`} data-align="end" data-no-export="true">
      <span className="c11b-tip__text">{tip.text}</span>
      {tip.to ? <SoftLink to={tip.to} className="c11b-tip__link">{tip.toLabel}</SoftLink> : null}
      <button type="button" className="c11b-tip__x" onClick={onClose} aria-label={t('common.close')}>
        <X size={14} aria-hidden="true" />
      </button>
    </span>
  );
}
