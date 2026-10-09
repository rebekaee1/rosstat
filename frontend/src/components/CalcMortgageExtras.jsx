// Круг 11 (E): досрочное погашение ипотеки. Доплата каждый месяц и/или одно крупное погашение;
// видно, на сколько короче станет кредит и сколько процентов не придётся платить. Расчёт на клиенте (lib/mortgageSchedule.js).
import { PiggyBank } from 'lucide-react';
import { revealStyle } from '../lib/calcUi';
import { fitAmountText, formatRubles, years as yearsPhrase } from '../lib/calcFormat';
import { CalcStatGrid, CalcStatTile } from './CalcStatTile';
import CalcMoneyField from './CalcMoneyField';
import CalcSlider from './CalcSlider';
import Chip from './Chip';
import { useLocale, useT } from '../i18n';
import '../styles/calc-ui.css';

const EXTRA_MAX = 1_000_000_000;

const fit = (n) => fitAmountText(formatRubles(n), n, { maxChars: 14 });

/** «3 года 4 мес.» / «3 years 4 mo.» */
function termText(months, t, locale) {
  const whole = Math.floor(months / 12);
  const rest = months % 12;
  const yearsText = whole > 0 ? (locale === 'en' ? t('calc.years', { n: whole }) : yearsPhrase(whole)) : '';
  const monthsText = rest > 0 ? t('c9d.calc.monthsShort', { n: rest }) : '';
  return [yearsText, monthsText].filter(Boolean).join(' ') || t('c9d.calc.monthsShort', { n: 0 });
}

/**
 * value: { monthly, lump, lumpMonth, lumpMode }; onChange(patch). base и early — графики без доплат и с ними.
 * gain: { monthsSaved, interestSaved }.
 */
export default function CalcMortgageExtras({ value, onChange, termMonths, base, early, gain, index = 6 }) {
  const t = useT();
  const { locale } = useLocale();
  const active = value.monthly > 0 || value.lump > 0;
  const lumpMonth = Math.min(Math.max(1, value.lumpMonth), Math.max(1, termMonths));

  return (
    <section
      style={revealStyle(index)}
      className="fe-reveal fe-panel rounded-[2rem] shadow-sm shadow-black/[0.03] p-5 md:p-6 mb-6"
      data-block="calc-early-repayment"
    >
      <div className="flex items-center gap-2 mb-1">
        <PiggyBank className="w-4 h-4 text-champagne" aria-hidden="true" />
        <h3 className="text-base font-semibold text-text-primary">{t('c11e.early.title')}</h3>
      </div>
      <p className="text-xs text-text-secondary mb-4">{t('c11e.early.hint')}</p>

      <div className="grid gap-5 sm:grid-cols-2">
        <CalcMoneyField
          id="mortgage-extra-monthly"
          label={t('c11e.early.monthly')}
          unitName={t('calc.ui.unitRubles')}
          value={value.monthly}
          onChange={(monthly) => onChange({ monthly })}
          prefix="₽"
          size="md"
          allowZero
          max={EXTRA_MAX}
          placeholder="0"
        />
        <CalcMoneyField
          id="mortgage-extra-lump"
          label={t('c11e.early.lump')}
          unitName={t('calc.ui.unitRubles')}
          value={value.lump}
          onChange={(lump) => onChange({ lump })}
          prefix="₽"
          size="md"
          allowZero
          max={EXTRA_MAX}
          placeholder="0"
        />
      </div>

      {value.lump > 0 && (
        <div className="mt-5 grid gap-4">
          <CalcSlider
            label={t('c11e.early.lumpMonth')}
            value={lumpMonth}
            onChange={(next) => onChange({ lumpMonth: next })}
            min={1}
            max={Math.max(1, termMonths)}
            display={t('c11e.early.lumpMonthShown', { n: lumpMonth })}
          />
          <div className="flex flex-wrap gap-1.5" role="group" aria-label={t('c11e.early.modeAria')}>
            <Chip active={value.lumpMode === 'term'} onClick={() => onChange({ lumpMode: 'term' })}>
              {t('c11e.early.modeTerm')}
            </Chip>
            <Chip active={value.lumpMode === 'payment'} onClick={() => onChange({ lumpMode: 'payment' })}>
              {t('c11e.early.modePayment')}
            </Chip>
          </div>
        </div>
      )}

      {active && early.months > 0 && (
        <div className="mt-5" data-testid="early-result">
          <CalcStatGrid className="w5-tiles--three">
            <CalcStatTile index={0} label={t('c11e.early.newTerm')} value={termText(early.months, t, locale)} />
            <CalcStatTile index={1} label={t('c11e.early.saved')} value={fit(gain.interestSaved)} accent />
            <CalcStatTile index={2} label={t('c11e.early.earlier')} value={termText(gain.monthsSaved, t, locale)} />
          </CalcStatGrid>
          <p className="mt-3 text-xs leading-relaxed text-text-secondary">
            {value.lump > 0 && value.lumpMode === 'payment'
              ? t('c11e.early.noteNewPayment', { payment: formatRubles(early.rows[Math.min(early.rows.length, lumpMonth + 1) - 1]?.payment ?? early.payment), old: formatRubles(base.payment) })
              : t('c11e.early.noteSamePayment', { payment: formatRubles(base.payment) })}
          </p>
        </div>
      )}
    </section>
  );
}
