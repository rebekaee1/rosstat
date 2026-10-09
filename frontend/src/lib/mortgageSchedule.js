// Круг 11 (E): график платежей по ипотеке и досрочное погашение. Чистая математика без React, считается на клиенте.
// Платёж округляется до рубля один раз, как в самом калькуляторе (посетитель проверяет «платёж × месяцы»).

/** Аннуитетный платёж (рубли, целое). Ставка в процентах годовых. */
export function annuityPayment(principal, ratePct, months) {
  const n = Math.round(months);
  if (!(principal > 0) || !(n > 0)) return 0;
  const r = Number(ratePct) / 12 / 100;
  const exact = r > 0 ? (principal * r) / (1 - (1 + r) ** -n) : principal / n;
  return Math.round(exact);
}

/**
 * Полный график платежей.
 * @param {object} p
 * @param {number} p.principal   сумма кредита, ₽
 * @param {number} p.ratePct     ставка, % годовых
 * @param {number} p.months      срок, месяцев
 * @param {number} [p.monthlyExtra]  сколько доплачивать сверх платежа каждый месяц (срок сокращается)
 * @param {number} [p.lumpAmount]    разовое досрочное погашение
 * @param {number} [p.lumpMonth]     после какого по счёту платежа оно вносится (1…months)
 * @param {'term'|'payment'} [p.lumpMode]  'term': платёж прежний, срок короче; 'payment': срок прежний, платёж меньше
 * @returns {{ payment: number, rows: Array, months: number, totalInterest: number, totalPaid: number,
 *            years: Array }}
 */
export function buildSchedule({
  principal, ratePct, months, monthlyExtra = 0, lumpAmount = 0, lumpMonth = 0, lumpMode = 'term',
}) {
  const n = Math.round(months);
  const empty = { payment: 0, rows: [], months: 0, totalInterest: 0, totalPaid: 0, years: [] };
  if (!(principal > 0) || !(n > 0)) return empty;
  const r = Number(ratePct) / 12 / 100;
  let payment = annuityPayment(principal, ratePct, n);
  const extra = Math.max(0, Math.round(monthlyExtra) || 0);
  const lump = Math.max(0, Math.round(lumpAmount) || 0);
  const lumpAt = Math.min(n, Math.max(0, Math.round(lumpMonth) || 0));

  const rows = [];
  let balance = principal;
  let totalInterest = 0;
  let totalPaid = 0;
  let month = 0;
  // Запас на случай платежа, не покрывающего проценты (при ставке 0 и странных входах цикл всё равно конечен).
  const hardStop = n + 1;
  while (balance > 0.5 && month < hardStop) {
    month += 1;
    const interest = balance * r;
    let regular = Math.min(payment, balance + interest);
    let principalPaid = regular - interest;
    let added = 0;
    if (extra > 0) added += Math.min(extra, Math.max(0, balance - principalPaid));
    balance = Math.max(0, balance - principalPaid - added);
    if (lump > 0 && lumpAt > 0 && month === lumpAt && balance > 0) {
      const lumpPaid = Math.min(lump, balance);
      added += lumpPaid;
      balance -= lumpPaid;
      if (lumpMode === 'payment' && balance > 0 && n - month > 0) {
        payment = annuityPayment(balance, ratePct, n - month);
      }
    }
    if (month === hardStop - 1 && balance > 0 && balance < payment + 1) {
      // Последний месяц срока закрывает остаток целиком (округление платежа до рубля).
      regular += balance;
      principalPaid += balance;
      balance = 0;
    }
    totalInterest += interest;
    totalPaid += regular + added;
    rows.push({
      month,
      payment: Math.round(regular + added),
      principalPaid: Math.round(principalPaid + added),
      interestPaid: Math.round(interest),
      extra: Math.round(added),
      balance: Math.round(balance),
    });
  }

  const years = [];
  rows.forEach((row) => {
    const y = Math.ceil(row.month / 12);
    let bucket = years[y - 1];
    if (!bucket) {
      bucket = { year: y, payment: 0, principalPaid: 0, interestPaid: 0, extra: 0, balance: 0 };
      years[y - 1] = bucket;
    }
    bucket.payment += row.payment;
    bucket.principalPaid += row.principalPaid;
    bucket.interestPaid += row.interestPaid;
    bucket.extra += row.extra;
    bucket.balance = row.balance;
  });

  return {
    payment: annuityPayment(principal, ratePct, n),
    firstPayment: rows[0]?.payment ?? 0,
    lastPayment: rows[rows.length - 1]?.payment ?? 0,
    rows,
    months: rows.length,
    totalInterest: Math.round(totalInterest),
    totalPaid: Math.round(totalPaid),
    years: years.filter(Boolean),
  };
}

/** Что даёт досрочное погашение: сколько месяцев и процентов экономится по сравнению с графиком без него. */
export function earlyRepaymentGain(base, withExtra) {
  if (!base?.rows?.length || !withExtra?.rows?.length) return { monthsSaved: 0, interestSaved: 0 };
  return {
    monthsSaved: Math.max(0, base.months - withExtra.months),
    interestSaved: Math.max(0, base.totalInterest - withExtra.totalInterest),
  };
}

/**
 * Сравнение двух ставок при одинаковых сумме и сроке. Итоги считаются как в самом калькуляторе:
 * платёж, округлённый до рубля, умноженный на число месяцев.
 */
export function compareRates({ principal, months, rateA, rateB }) {
  const n = Math.round(months);
  const side = (rate) => {
    const payment = annuityPayment(principal, rate, n);
    const total = payment * n;
    return { rate, payment, total, overpay: total - principal };
  };
  const a = side(rateA);
  const b = side(rateB);
  return { a, b, paymentDiff: b.payment - a.payment, overpayDiff: b.overpay - a.overpay };
}

/** Таблица для выгрузки: ключи колонок совпадают с ключами строк (контракт POST /export/grid). */
export function scheduleGrid(schedule, { granularity = 'month', labels }) {
  const columns = granularity === 'year'
    ? [
      { key: 'year', label: labels.year },
      { key: 'payment', label: labels.payment, unit: '₽' },
      { key: 'principalPaid', label: labels.principal, unit: '₽' },
      { key: 'interestPaid', label: labels.interest, unit: '₽' },
      { key: 'extra', label: labels.extra, unit: '₽' },
      { key: 'balance', label: labels.balance, unit: '₽' },
    ]
    : [
      { key: 'month', label: labels.month },
      { key: 'payment', label: labels.payment, unit: '₽' },
      { key: 'principalPaid', label: labels.principal, unit: '₽' },
      { key: 'interestPaid', label: labels.interest, unit: '₽' },
      { key: 'extra', label: labels.extra, unit: '₽' },
      { key: 'balance', label: labels.balance, unit: '₽' },
    ];
  const source = granularity === 'year' ? schedule.years : schedule.rows;
  const rows = source.map((row) => Object.fromEntries(columns.map((c) => [c.key, row[c.key]])));
  return { columns, rows };
}
