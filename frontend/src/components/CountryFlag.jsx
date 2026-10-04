import { countryFlag } from '../lib/countryFlag';
import { cn } from '../lib/format';

/** Флаг-эмодзи вместо ISO-кода. Декоративен: название страны всегда стоит рядом. Пустой код — ничего не рисуем. */
export default function CountryFlag({ code, className }) {
  const flag = countryFlag(code);
  if (!flag) return null;
  return <span className={cn('fe-flag', className)} aria-hidden="true">{flag}</span>;
}
