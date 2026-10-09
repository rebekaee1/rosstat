import { useCallback, useRef, useState } from 'react';
import { Star } from 'lucide-react';
import { useT } from '../../i18n';
import { cn } from '../../lib/format';
import { authLink } from '../../lib/authReturn';
import { useSaved } from '../../lib/useSavedItems';
import ActionTip from './ActionTip';
import '../../styles/c11b-cabinet.css';

/**
 * «Сохранить» / «Сохранено»: звёздочка у показателя, страны, региона, сравнения, расчёта.
 * Подключение из любой зоны одной строкой:
 *
 *     <SaveButton kind="indicator" itemKey={code} title={name} />
 *
 * Показывается только если кабинет включён (`GET /cabinet/config`), после монтирования (в SSR разметки нет).
 * Гость сохраняет в браузере и получает приглашение войти; вошедший сохраняет в кабинете.
 *
 * Свойства:
 *  - `kind`      indicator | world | country | region | comparison | calc | rating_view
 *  - `itemKey`   что однозначно называет объект (код показателя, slug страны, строка адреса сравнения); не `key`: он занят React
 *  - `title`     имя для списка (человеческое, без кодов); без него в списке останется ключ
 *  - `payload`   необязательно: { path, subtitle, names }; `path` по умолчанию текущая страница; поля `lower`/`upper` запрещены
 *  - `variant`   'icon' (звёздочка, по умолчанию) | 'button' (звёздочка и подпись «Сохранить»)
 *  - `onChange`  вызывается с новым состоянием (true/false) после успешного действия
 */
export default function SaveButton({
  kind, itemKey, title, payload, variant = 'icon', className, label, savedLabel, onChange,
}) {
  const t = useT();
  const { enabled, authed, saved, toggle, limit } = useSaved(kind, itemKey);
  const [busy, setBusy] = useState(false);
  const [tip, setTip] = useState(null);
  const closeTip = useCallback(() => setTip(null), []);
  const busyRef = useRef(false);

  if (!enabled || !itemKey) return null;

  const name = title || '';
  const aria = saved
    ? (name ? t('c11b.save.removeAria', { name }) : t('c11b.save.removeAriaPlain'))
    : (name ? t('c11b.save.addAria', { name }) : t('c11b.save.addAriaPlain'));

  const onClick = async () => {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setTip(null);
    const was = saved;
    const res = await toggle({ title, payload });
    busyRef.current = false;
    setBusy(false);
    if (!res.ok) {
      setTip({
        tone: 'warn',
        text: res.reason === 'limit_reached'
          ? t('c11b.save.limit', { n: limit ?? 200 })
          : res.reason === 'network' ? t('c11b.err.network') : t('c11b.err.generic'),
      });
      return;
    }
    onChange?.(!was);
    // Гостю: напомнить, что запись лежит только в этом браузере, и позвать войти.
    if (res.local && !was && !authed) {
      setTip({ text: t('c11b.tip.guestSaved'), to: authLink('/login'), toLabel: t('c11b.tip.signIn') });
    }
  };

  const text = saved ? (savedLabel || t('c11b.save.saved')) : (label || t('c11b.save.add'));
  return (
    <span className={cn('c11b-wrap', className)} data-no-export="true">
      <button
        type="button"
        className={cn('fe-chip fe-press c11b-act', variant === 'button' ? 'c11b-act--text' : 'c11b-act--icon', saved && 'c11b-on')}
        aria-pressed={saved}
        aria-busy={busy || undefined}
        aria-label={variant === 'button' ? undefined : aria}
        title={aria}
        onClick={onClick}
        disabled={busy}
        data-c11b="save"
      >
        <Star size={16} aria-hidden="true" fill={saved ? 'currentColor' : 'none'} />
        {variant === 'button' ? <span className="c11b-act__label">{text}</span> : null}
      </button>
      <ActionTip tip={tip} onClose={closeTip} />
    </span>
  );
}
