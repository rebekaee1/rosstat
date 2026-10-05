import { countryFlag } from '../lib/countryFlag';
import { cn } from '../lib/format';
import { flagArt } from './brand/flagArt';
import '../styles/k2-brand.css';

/**
 * Флаг страны. Декоративен: название страны всегда стоит рядом. Пустой код — ничего не рисуем.
 * По умолчанию флаг-эмодзи (строки списков, кнопки).
 * glass — «стеклянная капля» 36–44 px (K2.8): векторный флаг в круге с бликом сверху и тенью снизу, за ним
 * размытое пятно цвета флага; без кольца. size — сторона капли в px (по умолчанию 40). Если векторного флага
 * для кода нет, внутри капли остаётся эмодзи.
 */
export default function CountryFlag({ code, className, glass = false, size }) {
  const flag = countryFlag(code);
  if (!flag) return null;
  if (!glass) return <span className={cn('fe-flag', className)} aria-hidden="true">{flag}</span>;
  const art = flagArt(code);
  const style = {};
  if (size) style['--fe-flag-size'] = `${Math.min(44, Math.max(36, size))}px`;
  if (art) style['--fe-flag-glow'] = art.glow;
  return (
    <span className={cn('fe-flag fe-flag--glass', className)} style={style} aria-hidden="true">
      <span className="fe-flag__drop">
        {art ? (
          <svg
            className="fe-flag__art"
            viewBox="0 0 60 40"
            preserveAspectRatio="xMidYMid slice"
            focusable="false"
            dangerouslySetInnerHTML={{ __html: art.svg }}
          />
        ) : (
          <span className="fe-flag__emoji">{flag}</span>
        )}
      </span>
    </span>
  );
}
