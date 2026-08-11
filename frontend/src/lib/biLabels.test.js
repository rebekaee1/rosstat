import { describe, expect, it } from 'vitest';
import {
  blockLabel, channelLabel, cityLabel, collapsePhrases, engineLabel,
  languageLabel, pageSectionRu, timezoneLabel,
} from './biLabels';

describe('biLabels — словарь ярлыков BI', () => {
  it('блоки: статические и region-section-N', () => {
    expect(blockLabel('chart')).toBe('График индикатора');
    expect(blockLabel('region-section-6')).toBe('Раздел региона: Культура, отдых и туризм');
    expect(blockLabel('region-section-99')).toBe('Раздел карточки региона №99');
    expect(blockLabel('home-workbench')).toBe('Рабочий стол главной');
    expect(blockLabel('home-russia-today')).toBe('Россия сегодня');
    expect(blockLabel('unknown-slug')).toBe('unknown-slug');
  });

  it('поисковики: идентификаторы Метрики → имена', () => {
    expect(engineLabel('yandex_search')).toBe('Яндекс');
    expect(engineLabel('google')).toBe('Google');
    expect(engineLabel('')).toBe('(не определён)');
  });

  it('языки через Intl.DisplayNames', () => {
    expect(languageLabel('ru-RU').toLowerCase()).toContain('русский');
    expect(languageLabel('')).toBe('(не определён)');
  });

  it('таймзоны: инвертированный знак Etc/GMT и города', () => {
    expect(timezoneLabel('Etc/GMT-3')).toBe('UTC+3');
    expect(timezoneLabel('Europe/Moscow')).toBe('Москва');
    expect(timezoneLabel('Asia/Yekaterinburg')).toBe('Екатеринбург');
  });

  it('города: транслит Метрики → русские имена', () => {
    expect(cityLabel('Saint Petersburg')).toBe('Санкт-Петербург');
    expect(cityLabel('Himki')).toBe('Химки');
    expect(cityLabel('Nairobi')).toBe('Nairobi');
  });

  it('каналы: пустое значение не уходит сырым', () => {
    expect(channelLabel('')).toBe('(не определён)');
    expect(channelLabel('search')).toBe('Поисковые системы');
  });

  it('разделы страниц — зеркало page_section бэкенда', () => {
    expect(pageSectionRu('/indicator/cpi?mode=weekly')).toBe('Индикаторы');
    expect(pageSectionRu('/region/moskva/1')).toBe('Карточки регионов');
    expect(pageSectionRu('/regions?view=map')).toBe('Каталог регионов');
    expect(pageSectionRu('/regions/map/uroven-bezrabotitsy')).toBe('Карта регионов');
    expect(pageSectionRu('/')).toBe('Главная');
  });

  it('collapsePhrases: недопечатки схлопываются в полную фразу', () => {
    const rows = collapsePhrases({ 'человек': 5, 'чело': 2, 'bvghn': 1, 'ип': 4 });
    expect(rows.find((r) => r.phrase === 'человек').count).toBe(7);
    expect(rows.find((r) => r.phrase === 'чело')).toBeUndefined();
    // короче minLen=3 — отброшено
    expect(rows.find((r) => r.phrase === 'ип')).toBeUndefined();
    expect(rows.find((r) => r.phrase === 'bvghn').count).toBe(1);
  });
});
