import { useCallback, useRef, useState } from 'react';
import { Bell, BellRing } from 'lucide-react';
import { useT } from '../../i18n';
import { cn } from '../../lib/format';
import { authLink } from '../../lib/authReturn';
import { useWatch } from '../../lib/useCabinet';
import ActionTip from './ActionTip';
import '../../styles/c11b-cabinet.css';

/**
 * «Следить» / «Слежу»: колокольчик у показателя и в календаре. Когда у ряда появляется новое значение, на кнопке
 * «Кабинет» зажигается отметка «Новое», а в кабинете появляется строка. Писем и уведомлений не отправляется.
 * Подключение одной строкой:
 *
 *     <WatchButton subjectKind="indicator" subjectKey={code} />
 *
 * Свойства:
 *  - `subjectKind`  indicator (федеральный показатель) | world (мировой ряд, `WorldIndicator.code`) | region (региональный показатель)
 *  - `subjectKey`   код ряда
 *  - `title`        название ряда только для подсказки скринридеру
 *  - `variant`      'icon' (колокольчик, по умолчанию) | 'button' (колокольчик и подпись «Следить»)
 * Нет кабинета или ряд не публичный: кнопки нет. Гостю кнопка есть, нажатие предлагает войти.
 */
export default function WatchButton({
  subjectKind, subjectKey, title, variant = 'icon', className, label, watchingLabel, onChange,
}) {
  const t = useT();
  const { enabled, authed, watching, loaded, toggle, limit } = useWatch(subjectKind, subjectKey);
  const [busy, setBusy] = useState(false);
  const [tip, setTip] = useState(null);
  const closeTip = useCallback(() => setTip(null), []);
  const busyRef = useRef(false);

  if (!enabled || !subjectKey) return null;

  const name = title || '';
  const aria = watching
    ? (name ? t('c11b.watch.offAria', { name }) : t('c11b.watch.offAriaPlain'))
    : (name ? t('c11b.watch.onAria', { name }) : t('c11b.watch.onAriaPlain'));
  const Icon = watching ? BellRing : Bell;

  const onClick = async () => {
    if (busyRef.current) return;
    if (!authed) {
      setTip({ text: t('c11b.tip.watchGuest'), to: authLink('/login'), toLabel: t('c11b.tip.signIn') });
      return;
    }
    busyRef.current = true;
    setBusy(true);
    setTip(null);
    const was = watching;
    const res = await toggle();
    busyRef.current = false;
    setBusy(false);
    if (!res.ok) {
      const text = res.reason === 'limit_reached' ? t('c11b.watch.limit', { n: limit ?? 50 })
        : res.reason === 'subject_not_found' ? t('c11b.err.subjectGone')
          : res.reason === 'network' ? t('c11b.err.network') : t('c11b.err.generic');
      setTip({ tone: 'warn', text });
      return;
    }
    onChange?.(!was);
    if (!was) setTip({ text: t('c11b.tip.watchOn'), to: '/account?tab=watches', toLabel: t('c11b.tip.openCabinet') });
  };

  const text = watching ? (watchingLabel || t('c11b.watch.on')) : (label || t('c11b.watch.off'));
  return (
    <span className={cn('c11b-wrap', className)} data-no-export="true">
      <button
        type="button"
        className={cn('fe-chip fe-press c11b-act', variant === 'button' ? 'c11b-act--text' : 'c11b-act--icon', watching && 'c11b-on')}
        aria-pressed={watching}
        aria-busy={busy || !loaded || undefined}
        aria-label={variant === 'button' ? undefined : aria}
        title={aria}
        onClick={onClick}
        disabled={busy || (authed && !loaded)}
        data-c11b="watch"
      >
        <Icon size={16} aria-hidden="true" />
        {variant === 'button' ? <span className="c11b-act__label">{text}</span> : null}
      </button>
      <ActionTip tip={tip} onClose={closeTip} />
    </span>
  );
}
