import { describe, it, expect } from 'vitest';
import { annuityPayment, buildSchedule, compareRates, earlyRepaymentGain, scheduleGrid } from './mortgageSchedule';

describe('annuityPayment', () => {
  it('6,4 млн на 20 лет под 18% даёт платёж около 98,8 тыс.', () => {
    expect(annuityPayment(6_400_000, 18, 240)).toBe(98_772);
  });
  it('нулевая ставка делит равными частями', () => {
    expect(annuityPayment(1_200_000, 0, 120)).toBe(10_000);
  });
  it('пустой ввод даёт ноль', () => {
    expect(annuityPayment(0, 10, 12)).toBe(0);
    expect(annuityPayment(1000, 10, 0)).toBe(0);
  });
});

describe('buildSchedule', () => {
  it('график без доплат: срок и остаток сходятся к нулю', () => {
    const s = buildSchedule({ principal: 3_000_000, ratePct: 12, months: 120 });
    expect(s.months).toBe(120);
    expect(s.rows[119].balance).toBe(0);
    expect(s.years).toHaveLength(10);
    const principalSum = s.rows.reduce((sum, row) => sum + row.principalPaid, 0);
    expect(Math.abs(principalSum - 3_000_000)).toBeLessThanOrEqual(120);
  });

  it('доплата каждый месяц сокращает срок и проценты', () => {
    const base = buildSchedule({ principal: 3_000_000, ratePct: 12, months: 240 });
    const fast = buildSchedule({ principal: 3_000_000, ratePct: 12, months: 240, monthlyExtra: 10_000 });
    const gain = earlyRepaymentGain(base, fast);
    expect(fast.months).toBeLessThan(base.months);
    expect(gain.monthsSaved).toBeGreaterThan(24);
    expect(gain.interestSaved).toBeGreaterThan(1_000_000);
    expect(fast.rows[fast.rows.length - 1].balance).toBe(0);
  });

  it('разовое погашение: «срок» оставляет платёж, «платёж» оставляет срок', () => {
    const term = buildSchedule({ principal: 3_000_000, ratePct: 12, months: 240, lumpAmount: 500_000, lumpMonth: 12, lumpMode: 'term' });
    const pay = buildSchedule({ principal: 3_000_000, ratePct: 12, months: 240, lumpAmount: 500_000, lumpMonth: 12, lumpMode: 'payment' });
    const base = buildSchedule({ principal: 3_000_000, ratePct: 12, months: 240 });
    expect(term.months).toBeLessThan(240);
    expect(term.rows[20].payment).toBe(base.rows[20].payment);
    expect(pay.months).toBeGreaterThanOrEqual(239);
    expect(pay.rows[30].payment).toBeLessThan(base.rows[30].payment);
  });

  it('доплата больше долга закрывает кредит в первый же месяц', () => {
    const s = buildSchedule({ principal: 100_000, ratePct: 10, months: 12, lumpAmount: 10_000_000, lumpMonth: 1 });
    expect(s.months).toBe(1);
    expect(s.rows[0].balance).toBe(0);
  });
});

describe('compareRates', () => {
  it('ставка выше даёт больший платёж и переплату', () => {
    const c = compareRates({ principal: 6_400_000, months: 240, rateA: 12, rateB: 14 });
    expect(c.paymentDiff).toBeGreaterThan(0);
    expect(c.overpayDiff).toBeGreaterThan(0);
    expect(c.a.total).toBe(c.a.payment * 240);
  });
});

describe('scheduleGrid', () => {
  it('ключи колонок совпадают с ключами строк', () => {
    const s = buildSchedule({ principal: 1_000_000, ratePct: 10, months: 24 });
    const labels = { year: 'Год', month: 'Месяц', payment: 'Платёж', principal: 'Долг', interest: 'Проценты', extra: 'Досрочно', balance: 'Остаток' };
    const g = scheduleGrid(s, { granularity: 'month', labels });
    expect(g.rows).toHaveLength(24);
    expect(Object.keys(g.rows[0])).toEqual(g.columns.map((c) => c.key));
    expect(scheduleGrid(s, { granularity: 'year', labels }).rows).toHaveLength(2);
  });
});
