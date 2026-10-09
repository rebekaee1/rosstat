import { useFeedCount } from '../../lib/useCabinet';
import { useT } from '../../i18n';
import { cn } from '../../lib/format';
import '../../styles/c11b-cabinet.css';

/**
 * Отметка «Новое» на кнопке «Кабинет» в шапке: показывается, только если кабинет включён, человек вошёл
 * и у отслеживаемых рядов вышло значение, которого он ещё не видел. Иначе не рисуется совсем.
 * Подключение одной строкой внутри кнопки или ссылки «Кабинет»:  `<FeedBadge />`
 *
 *  - `variant="dot"` (по умолчанию): синяя точка с числом; `variant="pill"`: плашка со словом «Новое».
 *  - Положение задаёт родитель; для угла кнопки есть класс `c11b-new--corner` (родителю нужен `position: relative`).
 */
export default function FeedBadge({ variant = 'dot', corner = false, className }) {
  const t = useT();
  const count = useFeedCount();
  if (!count) return null;
  const text = t('c11b.feed.badgeAria', { n: count });
  return (
    <span
      className={cn('c11b-new', variant === 'pill' && 'c11b-new--pill', corner && 'c11b-new--corner', className)}
      role="status"
      aria-label={text}
      title={text}
      data-c11b="feed-badge"
    >
      {variant === 'pill' ? t('c11b.feed.new') : (count > 9 ? '9+' : count)}
    </span>
  );
}
