import { forwardRef } from 'react';
import { cn } from '../lib/format';
import { chipTitleFor } from '../lib/chipLabel';
import { useT } from '../i18n/localeContext';

/** Строковая подпись чипа: до двух строк по словам, без обрезки посреди слова (стили `.fe-chip__label`). */
export function ChipLabel({ children }) {
  return typeof children === 'string' ? <span className="fe-chip__label">{children}</span> : children;
}

/**
 * Единая «пилюля»-переключатель (режимы показателя, частота, диапазон графика).
 * `active` → aria-pressed и графитовая заливка со светлым текстом (круг 6; была золотая); цель нажатия 44 px на сенсорных экранах без раздувания вида на компьютере.
 * Длинная подпись переносится на вторую строку; полное имя доступно в `title`.
 * Круг 11, G: `pending` — чип ждёт ответа (смена режима, период, «Год к году»): подпись тускнеет, по центру тонкое кольцо (появляется через
 * 140 мс), `aria-busy`, повторное нажатие не срабатывает. Размер чипа не меняется: кольцо лежит поверх подписи, а не рядом с ней.
 */
const Chip = forwardRef(function Chip({
  active = false, pending = false, className, children, type = 'button', title, onClick, ...rest
}, ref) {
  const t = useT();
  return (
    <button
      ref={ref}
      type={type}
      aria-pressed={active}
      title={chipTitleFor(children, title)}
      className={cn('fe-chip fe-press', active && 'is-active', className)}
      aria-busy={pending || undefined}
      data-pending={pending ? 'true' : undefined}
      onClick={pending ? (event) => event.preventDefault() : onClick}
      {...rest}
    >
      <ChipLabel>{children}</ChipLabel>
      {pending ? (
        <>
          <span className="fe-chip__spinner" aria-hidden="true" />
          <span className="sr-only">{t('c11g.pending')}</span>
        </>
      ) : null}
    </button>
  );
});

export default Chip;
