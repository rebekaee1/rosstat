import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { ChevronDown } from 'lucide-react';
import { homeScopeCountriesCount } from '../../lib/homeWorkbench';
import { compactIndicatorCount, historyYears, startYear } from '../../lib/homeStats';
import { pluralRu, useWorldCountries } from '../../lib/worldApi';
import { russiaCategoriesPath, worldRatingPath, WORLD_RATING_DEFAULT_CONCEPT } from '../../lib/sitePaths';
import { useLocale, useT } from '../../i18n';
import '../../styles/shell.css';

const groupDigits = (locale) => {
  const formatter = new Intl.NumberFormat(locale === 'en' ? 'en-US' : 'ru-RU');
  return (n) => formatter.format(Math.round(n));
};

/**
 * Плитка числа: крупное значение сверху, пояснение фразой снизу (читается как предложение:
 * «268 тыс. показателей», «55 стран, и список растёт»). Если задан `to`, вся плитка нажимается.
 */
function Stat({ to, label, children }) {
  // Допустимая для <dl> разметка: группа dt + dd. Ссылка живёт внутри dd и растягивается на всю плитку.
  return (
    <div className="fe-scope-stat">
      <dd className="fe-stat-num">
        {to ? <Link to={to} className="fe-scope-stat__link fe-press">{children}</Link> : children}
      </dd>
      <dt className="fe-scope-stat__label">{label}</dt>
    </div>
  );
}

/**
 * Правая колонка hero: три числа платформы (показатели, страны, глубина истории), свёрнутая строка с
 * названиями источников и раскрывающиеся «Подробнее». Числа сразу итоговые, без «бега»: пока каталог не
 * ответил, на их месте «…», а не устаревший запасной набор. Те же значения показывает каталог стран.
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
  const years = historyYears(since);
  const pending = countriesQ.isLoading;
  const isEn = locale === 'en';

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
  const wait = <span className="fe-stat-wait" aria-label={t('common.loading')}>…</span>;

  const countriesLabel = t('w6b.scope.countries');
  const yearsWord = isEn
    ? t('w6b.scope.yearsWord')
    : pluralRu(years || 0, [t('w6b.scope.yearsWord_one'), t('w6b.scope.yearsWord_few'), t('w6b.scope.yearsWord_many')]);

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
          <Stat
            to={isEn ? worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT) : russiaCategoriesPath()}
            label={t('w6b.scope.indicators')}
          >
            {pending ? wait : indicators ? (
              <>
                {numberFormat(indicators.value)}
                {indicators.unit ? (
                  <span className="fe-stat-unit">{t(`homehero.stat.${indicators.unit}`)}</span>
                ) : null}
              </>
            ) : dash}
          </Stat>
          <Stat to="/#countries" label={countriesLabel}>
            {pending ? wait : countriesCount != null ? numberFormat(countriesCount) : dash}
          </Stat>
          <Stat label={t('w6b.scope.history', { years: yearsWord, since: since || '' })}>
            {years ? (
              <>
                <span className="fe-stat-unit fe-stat-unit--lead">{t('w6b.scope.upTo')}</span>
                {numberFormat(years)}
              </>
            ) : dash}
          </Stat>
        </dl>

        <details className="fe-scope-more">
          <summary className="fe-scope-more__summary">
            <span className="fe-scope-more__text">
              <span className="fe-scope-more__lead">{t('w6b.scope.officialOnly')}</span>
              <span className="fe-scope-more__names">{t('w6b.scope.sourcesShort')}</span>
            </span>
            <ChevronDown size={16} aria-hidden="true" className="fe-scope-more__chevron" />
          </summary>
          <div className="fe-scope-more__body">
            {!isEn && (Number.isFinite(russiaMacro) || Number.isFinite(russiaRegional)) && (
              <ul className="fe-scope-more__list">
                {Number.isFinite(russiaMacro) && russiaMacro > 0 && (
                  <li><strong>{numberFormat(russiaMacro)}</strong> {t('home.scope.stat.macro.label')}</li>
                )}
                {Number.isFinite(russiaRegional) && russiaRegional > 0 && (
                  <li><strong>{numberFormat(russiaRegional)}</strong> {t('home.scope.stat.regions.label')}</li>
                )}
              </ul>
            )}
            {isEn && usIndicators > 0 && usStates > 0 && (
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
