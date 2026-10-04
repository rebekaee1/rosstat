import { useMemo } from 'react';
import { ChevronDown } from 'lucide-react';
import { homeScopeCountriesCount } from '../../lib/homeWorkbench';
import { compactIndicatorCount, startYear } from '../../lib/homeStats';
import { useWorldCountries } from '../../lib/worldApi';
import { useLocale, useT } from '../../i18n';
import AnimatedCount from './AnimatedCount';
import '../../styles/shell.css';

const groupDigits = (locale) => {
  const formatter = new Intl.NumberFormat(locale === 'en' ? 'en-US' : 'ru-RU');
  return (n) => formatter.format(Math.round(n));
};
const plainYear = (n) => String(Math.round(n));

function Stat({ label, children }) {
  // Подпись — короткое слово в одну строку над числом: три колонки равны по ширине, числа стоят на одной линии.
  return (
    <div className="fe-scope-stat">
      <dt className="fe-scope-stat__label">{label}</dt>
      <dd className="fe-stat-num">{children}</dd>
    </div>
  );
}

/**
 * Правая колонка hero: три живых числа (показатели, страны, глубина истории), строка про официальные источники
 * и раскрывающиеся «Подробнее» с составом по России и полным списком источников.
 * Числа берутся из того же ответа каталога, что и карточки стран.
 */
export default function HomeDataScope() {
  const t = useT();
  const { locale } = useLocale();
  const countriesQ = useWorldCountries();
  const data = countriesQ.data;
  const numberFormat = useMemo(() => groupDigits(locale), [locale]);

  const countriesCount = homeScopeCountriesCount(data);
  const indicators = compactIndicatorCount(data?.world_indicators_count);
  const since = startYear(t('home.scope.period.value'));
  const endYear = new Date().getFullYear();
  const pending = countriesQ.isLoading;

  const russiaMacro = Number(data?.russia_macro_indicators_count);
  const russiaRegional = (() => {
    const direct = Number(data?.russia_regional_indicators_count);
    if (Number.isFinite(direct) && direct > 0) return direct;
    // Старый кэшированный ответ каталога мог не содержать отдельного поля.
    const russia = data?.countries?.find((country) => country.code === 'RU' || country.slug === 'russia');
    const total = Number(russia?.indicators_count);
    return Number.isFinite(total) && Number.isFinite(russiaMacro) && total >= russiaMacro
      ? total - russiaMacro
      : NaN;
  })();
  const usIndicators = Number(data?.us_state_indicators_count);
  const usStates = Number(data?.us_states_count);

  const dash = <span aria-label={t('homehero.stat.unknown')}>—</span>;
  const skeleton = <span className="fe-stat-skeleton skeleton" aria-hidden="true" />;

  return (
    <aside
      data-block="home-data-scope"
      className="fe-scope fe-reveal relative z-30 overflow-hidden"
      style={{ '--fe-delay': '0.08s' }}
      aria-labelledby="home-data-scope-title"
    >
      <div className="pointer-events-none absolute -right-12 -top-14 h-36 w-36 rounded-full bg-champagne/10 blur-3xl" />
      <div className="relative">
        <h2 id="home-data-scope-title" className="fe-scope-title">
          {t('home.scope.title')}
        </h2>

        <dl className="fe-scope-stats">
          <Stat label={t('shell3.stat.indicators')}>
            {pending ? skeleton : indicators ? (
              <>
                <AnimatedCount value={indicators.value} format={numberFormat} />
                {indicators.unit ? (
                  <span className="fe-stat-unit">{t(`homehero.stat.${indicators.unit}`)}</span>
                ) : null}
              </>
            ) : dash}
          </Stat>
          <Stat label={t('shell3.stat.countries')}>
            {pending ? skeleton : countriesCount != null
              ? <AnimatedCount value={countriesCount} format={numberFormat} />
              : dash}
          </Stat>
          <Stat label={t('shell3.stat.since')}>
            {since
              ? <AnimatedCount value={since} from={endYear} format={plainYear} duration={1100} />
              : dash}
          </Stat>
        </dl>

        <details className="fe-scope-more">
          <summary className="fe-scope-more__summary">
            {t('homehero.trust')}
            <ChevronDown size={16} aria-hidden="true" className="fe-scope-more__chevron" />
          </summary>
          <div className="fe-scope-more__body">
            {locale !== 'en' && (Number.isFinite(russiaMacro) || Number.isFinite(russiaRegional)) && (
              <ul className="fe-scope-more__list">
                {Number.isFinite(russiaMacro) && russiaMacro > 0 && (
                  <li><strong>{numberFormat(russiaMacro)}</strong> {t('home.scope.stat.macro.label')}</li>
                )}
                {Number.isFinite(russiaRegional) && russiaRegional > 0 && (
                  <li><strong>{numberFormat(russiaRegional)}</strong> {t('home.scope.stat.regions.label')}</li>
                )}
              </ul>
            )}
            {locale === 'en' && usIndicators > 0 && usStates > 0 && (
              <p>
                {t('home.scope.usStates', { indicators: numberFormat(usIndicators), states: usStates })}
              </p>
            )}
            <p className="fe-scope-more__label">{t('home.scope.sources.label')}</p>
            <p>{t('home.scope.sources.list')}</p>
            <p className="fe-scope-more__update">
              <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-champagne" aria-hidden="true" />
              {t('home.scope.update')}
            </p>
          </div>
        </details>
      </div>
    </aside>
  );
}
