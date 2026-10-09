// «Ключевая ставка ЦБ — 14 %»: короткая пилюля обычным регистром под заголовком калькуляторов
// (раньше была частью надбровки капсом через дефис и ломалась на две строки).
import { Link } from 'react-router-dom';
import { russiaIndicatorPath } from '../lib/sitePaths';
import { useLocale, useT } from '../i18n';
import '../styles/w5-tools.css';

export default function CalcKeyRate({ rate, pending = false }) {
  const t = useT();
  const { locale } = useLocale();
  const known = rate != null && Number.isFinite(Number(rate));
  // Круг 11 (E): пока ставка грузится, место под пилюлю уже занято, и форма не уезжает вниз, когда она появится.
  if (!known) return pending ? <span className="w5-keyrate w5-keyrate--ghost" aria-hidden="true" /> : null;
  const shown = Number(rate).toLocaleString(locale === 'en' ? 'en-US' : 'ru-RU', { maximumFractionDigits: 2 });
  return (
    <Link to={russiaIndicatorPath('key-rate')} className="w5-keyrate fe-press">
      <span className="w5-keyrate__dot" aria-hidden="true" />
      {t('w5.calc.keyRate', { rate: shown })}
    </Link>
  );
}
