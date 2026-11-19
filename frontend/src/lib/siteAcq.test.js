import { describe, it, expect } from 'vitest';
import { PAGE_TOPIC, FIRST_SCREEN_CODES, botStartUrl, isDelayed, lineCopy, nextPeriodMonth, releaseCodeOf } from './siteAcq';

const TODAY = new Date('2026-11-19T12:00:00Z');

describe('siteAcq: темы и ссылки (совет 19.11.2026)', () => {
  it('страницы ведут в темы публичного бота; ИПЦ — в инфляцию за год', () => {
    expect(PAGE_TOPIC.cpi).toBe('inflation');
    expect(PAGE_TOPIC['fuel-diesel']).toBe('diesel');
    expect(PAGE_TOPIC['usd-rub']).toBe('usd');
    expect(PAGE_TOPIC['wages-nominal']).toBeUndefined();
    expect(PAGE_TOPIC.population).toBeUndefined();
    expect(FIRST_SCREEN_CODES.has('wages-nominal')).toBe(true);
    expect(FIRST_SCREEN_CODES.has('ipi')).toBe(false);
  });

  it('ссылка в бота — site_<тема>, без бота или темы ссылки нет', () => {
    expect(botStartUrl('ForecastEconomyBot', 'inflation')).toBe('https://t.me/ForecastEconomyBot?start=site_inflation');
    expect(botStartUrl('', 'gold')).toBeNull();
    expect(botStartUrl('ForecastEconomyBot', null)).toBeNull();
  });

  it('календарь берётся по коду, к которому привязаны события', () => {
    expect(releaseCodeOf('cpi')).toBe('cpi');
    expect(releaseCodeOf('cpi-yoy')).toBe('cpi');
    expect(releaseCodeOf('gold-price')).toBeNull();
  });
});

describe('siteAcq: задержка источника', () => {
  it('ИПЦ на сентябре 19.11 не задерживается: октябрь выйдет 25.11 по календарю', () => {
    expect(isDelayed({ frequency: 'monthly', lastDate: '2026-09-01', nextRelease: '2026-11-25', today: TODAY })).toBe(false);
  });
  it('недельное топливо: 10 дней — норма, 15 дней — задержка', () => {
    expect(isDelayed({ frequency: 'weekly', lastDate: '2026-11-09', today: TODAY })).toBe(false);
    expect(isDelayed({ frequency: 'weekly', lastDate: '2026-11-04', today: TODAY })).toBe(true);
  });
  it('старый месячный ряд без выхода в ближайшие 14 дней — задержка; сервер «stale» — задержка всегда', () => {
    expect(isDelayed({ frequency: 'monthly', lastDate: '2026-06-01', nextRelease: '2027-01-20', today: TODAY })).toBe(true);
    expect(isDelayed({ freshness: { level: 'stale' }, frequency: 'daily', lastDate: '2026-11-19', today: TODAY })).toBe(true);
  });
});

describe('siteAcq: текст строки', () => {
  it('ИПЦ: месяц после последней точки и дата выхода', () => {
    const c = lineCopy({ code: 'cpi', frequency: 'monthly', lastDate: '2026-09-01', nextRelease: '2026-11-25' });
    expect(c.key).toBe('cpi');
    expect(c.params.month.toISOString().slice(0, 10)).toBe('2026-10-01');
    expect(lineCopy({ code: 'cpi', frequency: 'monthly', lastDate: '2026-09-01', nextRelease: '2026-11-25', nextEstimated: true }).key).toBe('cpiApprox');
  });
  it('ставка ЦБ — дата решения, даже если ряд хранится по дням; без даты строки нет', () => {
    expect(lineCopy({ code: 'key-rate', frequency: 'daily', nextRelease: '2026-12-18' }).key).toBe('keyrate');
    expect(lineCopy({ code: 'key-rate', frequency: 'daily' })).toBeNull();
  });
  it('золото и доллар — каждый рабочий день; топливо — по средам; прочее — дата из календаря', () => {
    expect(lineCopy({ code: 'gold-price', frequency: 'daily' }).key).toBe('daily');
    expect(lineCopy({ code: 'fuel-ai92', frequency: 'weekly' }).key).toBe('fuelWeekly');
    expect(lineCopy({ code: 'deposit-rate', frequency: 'monthly', nextRelease: '2026-12-08' }).key).toBe('next');
    expect(lineCopy({ code: 'wages-nominal', frequency: 'monthly' })).toBeNull();
  });
  it('задержка перекрывает всё', () => {
    expect(lineCopy({ code: 'gold-price', frequency: 'daily', delayed: true }).key).toBe('delayed');
  });
  it('следующий месяц после декабря — январь следующего года', () => {
    expect(nextPeriodMonth('2026-12-01').toISOString().slice(0, 10)).toBe('2027-01-01');
  });
});
