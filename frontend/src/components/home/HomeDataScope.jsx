import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { BarChart3, Globe2, History } from 'lucide-react';
import { homeScopeCountriesCount } from '../../lib/homeWorkbench';
import { compactIndicatorCount, historyYears, startYear } from '../../lib/homeStats';
import { pluralRu, useWorldCountries } from '../../lib/worldApi';
import { russiaCategoriesPath, worldRatingPath, WORLD_RATING_DEFAULT_CONCEPT } from '../../lib/sitePaths';
import { useLocale, useT } from '../../i18n';
import CountUp from './CountUp';
import '../../styles/shell.css';
import '../../styles/z3-home.css';

const groupDigits = (locale) => {
  const formatter = new Intl.NumberFormat(locale === 'en' ? 'en-US' : 'ru-RU');
  return (n) => formatter.format(Math.round(n));
};

/**
 * Плитка числа: значок и крупное золотое число сверху, пояснение фразой снизу (читается как предложение:
 * «268 тыс. показателей», «55 стран, и список растёт»). Если задан `to`, вся плитка нажимается.
 */
function Stat({ to, label, icon: Icon, children }) {
  // Допустимая для <dl> разметка: группа dt + dd. Ссылка живёт внутри dd и растягивается на всю плитку.
  return (
    <div className="fe-scope-stat">
      <dd className="fe-stat-num">
        {Icon ? <span className="fe-scope-stat__icon" aria-hidden="true"><Icon size={16} /></span> : null}
        {to ? <Link to={to} className="fe-scope-stat__link fe-press">{children}</Link> : children}
      </dd>
      <dt className="fe-scope-stat__label">{label}</dt>
    </div>
  );
}

/**
 * Полоса «Платформа в цифрах»: три числа (показатели, страны, глубина истории), больше ничего. Круг 8: убраны строка
 * «обновляется по мере публикации» и раскрывающийся абзац «Только официальные источники» (оба текста есть в подвале и на «О проекте»):
 * главная была «чуть нагруженной». Числа набегают один раз, когда блок попал в экран (без IntersectionObserver и при «уменьшить движение» сразу итоговые);
 * итоговый текст всегда лежит в разметке. Пока каталог не ответил, на месте числа «…», а не устаревший запасной набор.
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

  const dash = <span aria-label={t('homehero.stat.unknown')}>—</span>;
  const wait = <span className="fe-stat-wait" aria-label={t('common.loading')}>…</span>;

  const countriesLabel = t('w6b.scope.countries');
  const yearsWord = isEn
    ? t('w6b.scope.yearsWord')
    : pluralRu(years || 0, [t('w6b.scope.yearsWord_one'), t('w6b.scope.yearsWord_few'), t('w6b.scope.yearsWord_many')]);

  return (
    <aside
      data-block="home-data-scope"
      className="fe-scope fe-reveal fe-glint fe-cursor-light relative z-30 overflow-hidden"
      style={{ '--fe-delay': '0.08s' }}
      aria-labelledby="home-data-scope-title"
    >
      <span className="fe-scope__f" aria-hidden="true" />
      <div className="relative">
        <h2 id="home-data-scope-title" className="fe-scope-title">
          {t('home.scope.title')}
        </h2>

        <dl className="fe-scope-stats">
          <Stat
            to={isEn ? worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT) : russiaCategoriesPath()}
            label={t('w6b.scope.indicators')}
            icon={BarChart3}
          >
            {pending ? wait : indicators ? (
              <>
                <CountUp value={indicators.value} format={numberFormat} group="scope" />
                {indicators.unit ? (
                  <span className="fe-stat-unit">{t(`homehero.stat.${indicators.unit}`)}</span>
                ) : null}
              </>
            ) : dash}
          </Stat>
          <Stat to="/#countries" label={countriesLabel} icon={Globe2}>
            {pending ? wait : countriesCount != null ? <CountUp value={countriesCount} format={numberFormat} group="scope" /> : dash}
          </Stat>
          <Stat label={t('w6b.scope.history', { years: yearsWord, since: since || '' })} icon={History}>
            {years ? (
              <>
                <span className="fe-stat-unit fe-stat-unit--lead">{t('w6b.scope.upTo')}</span>
                <CountUp value={years} format={numberFormat} group="scope" />
              </>
            ) : dash}
          </Stat>
        </dl>

      </div>
    </aside>
  );
}
