// Выпадающий список валюты для конвертера: флаг (или значок) и название, быстрый поиск,
// управление с клавиатуры. Вместо системного <select>: он не вписывался в оформление сайта и не показывал флаги.
import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react';
import { Check, ChevronDown, Search } from 'lucide-react';
import { cn } from '../lib/format';
import '../styles/z8-tools.css';

/** Значок валюты: доллар и монеты знаком, остальные валюты флагом. Вместо чужого флага у «USD». */
export function CoinBadge({ flag, symbol, className }) {
  return (
    <span className={cn('fe-z8-coin', className)} aria-hidden="true">
      {flag || symbol || ''}
    </span>
  );
}

/**
 * options: [{ value, name, flag, symbol, search }]; `search` — строка для поиска в нижнем регистре.
 */
export default function CurrencySelect({
  label, value, options, onChange, searchPlaceholder = '', emptyText = '', className,
}) {
  const uid = useId();
  const labelId = `${uid}-label`;
  const buttonId = `${uid}-button`;
  const listId = `${uid}-list`;
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const rootRef = useRef(null);
  const buttonRef = useRef(null);
  const inputRef = useRef(null);

  const current = options.find((option) => option.value === value) || options[0];
  const needle = query.trim().toLowerCase();
  const shown = useMemo(
    () => (needle ? options.filter((option) => (option.search || option.name.toLowerCase()).includes(needle)) : options),
    [options, needle],
  );
  const activeIndex = Math.max(0, Math.min(active, shown.length - 1));

  const close = useCallback((returnFocus = false) => {
    setOpen(false);
    setQuery('');
    if (returnFocus) buttonRef.current?.focus();
  }, []);

  const openList = () => {
    const at = options.findIndex((option) => option.value === value);
    setActive(Math.max(0, at));
    setOpen(true);
  };

  const choose = (option) => {
    if (option) onChange(option.value);
    close(true);
  };

  // Клик мимо закрывает список; на телефоне поле поиска не получает фокус сразу, чтобы не выезжала клавиатура.
  useEffect(() => {
    if (!open) return undefined;
    const onDown = (event) => {
      if (rootRef.current && !rootRef.current.contains(event.target)) close(false);
    };
    document.addEventListener('pointerdown', onDown);
    const fine = typeof window.matchMedia === 'function' && window.matchMedia('(pointer: fine)').matches;
    if (fine) inputRef.current?.focus();
    return () => document.removeEventListener('pointerdown', onDown);
  }, [open, close]);

  const onKeyDown = (event) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      close(true);
    } else if (event.key === 'ArrowDown') {
      event.preventDefault();
      setActive(Math.min(activeIndex + 1, shown.length - 1));
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setActive(Math.max(activeIndex - 1, 0));
    } else if (event.key === 'Enter') {
      event.preventDefault();
      choose(shown[activeIndex]);
    } else if (event.key === 'Tab') {
      close(false);
    }
  };

  return (
    <div ref={rootRef} className={cn('fe-z8-select', open && 'is-open', className)}>
      <span id={labelId} className="fe-z8-select__label">{label}</span>
      <button
        ref={buttonRef}
        id={buttonId}
        type="button"
        className="fe-z8-select__button fe-press"
        role="combobox"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        aria-labelledby={`${labelId} ${buttonId}`}
        data-value={value}
        onClick={() => (open ? close(false) : openList())}
        onKeyDown={(event) => {
          if (!open && (event.key === 'ArrowDown' || event.key === 'ArrowUp')) {
            event.preventDefault();
            openList();
          }
        }}
      >
        <CoinBadge flag={current?.flag} symbol={current?.symbol} />
        <span className="fe-z8-select__name">{current?.name}</span>
        <ChevronDown className="fe-z8-select__chev" size={16} aria-hidden="true" />
      </button>
      {open && (
        <div className="fe-z8-select__panel" onKeyDown={onKeyDown}>
          <label className="fe-z8-select__search">
            <Search size={15} aria-hidden="true" />
            <input
              ref={inputRef}
              type="search"
              value={query}
              onChange={(event) => { setQuery(event.target.value); setActive(0); }}
              placeholder={searchPlaceholder}
              aria-label={searchPlaceholder}
              autoComplete="off"
              aria-controls={listId}
            />
          </label>
          <ul id={listId} role="listbox" aria-labelledby={labelId} className="fe-z8-select__list">
            {shown.map((option, index) => (
              <li
                key={option.value}
                role="option"
                aria-selected={option.value === value}
                className={cn('fe-z8-select__option', index === activeIndex && 'is-active', option.value === value && 'is-current')}
                onPointerEnter={() => setActive(index)}
                onClick={() => choose(option)}
              >
                <CoinBadge flag={option.flag} symbol={option.symbol} />
                <span className="fe-z8-select__optname">{option.name}</span>
                {option.value === value ? <Check size={16} aria-hidden="true" /> : null}
              </li>
            ))}
            {shown.length === 0 && <li className="fe-z8-select__empty" role="presentation">{emptyText}</li>}
          </ul>
        </div>
      )}
    </div>
  );
}
