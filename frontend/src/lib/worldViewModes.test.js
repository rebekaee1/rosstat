import { describe, expect, it } from 'vitest';
import {
  adaptWorldModes,
  buildWorldModeToken,
  collapseCountryIndicators,
  groupModesFromApi,
  normalizeWorldModeToken,
  parseWorldModeToken,
  resolveWorldMode,
  findWorldMode,
  isEmptySeries,
  stripFrequencySuffix,
  worldChartTitle,
  worldModeToLegacyDataToken,
  expandedGroupForWorldMode,
  defaultModeForWorldGroup,
  worldVariantsToPickerGroup,
  indicatorPublicName,
} from './worldViewModes';
import { formatWorldValue } from './worldApi';
import {
  WORLD_MOCK_MODES_FULL,
  WORLD_MOCK_MODES_NO_POP,
  WORLD_MOCK_MODES_LEGACY,
} from './worldMocks';

const nbspToSpace = (s) => s.replace(/[\u00a0\u202f]/g, ' ');

describe('parse / normalize world mode tokens', () => {
  it('парсит составной токен', () => {
    expect(parseWorldModeToken('yoy-quarterly')).toEqual({
      type: 'yoy',
      freq: 'quarterly',
    });
    expect(parseWorldModeToken('level-monthly')).toEqual({
      type: 'level',
      freq: 'monthly',
    });
    expect(parseWorldModeToken('nope')).toBeNull();
  });

  it('нормализует легаси-токены в составные', () => {
    expect(normalizeWorldModeToken('level', 'monthly')).toBe('level-monthly');
    expect(normalizeWorldModeToken('mom')).toBe('step-monthly');
    expect(normalizeWorldModeToken('qoq')).toBe('step-quarterly');
    expect(normalizeWorldModeToken('yoy', 'quarterly')).toBe('yoy-quarterly');
    expect(normalizeWorldModeToken('yoy_abs', 'annual')).toBe('yoyabs-annual');
    expect(normalizeWorldModeToken('index_first', 'monthly')).toBe('index-monthly');
    expect(normalizeWorldModeToken('avg_year')).toBe('level-annual');
    expect(normalizeWorldModeToken('avg-quarter')).toBe('level-quarterly');
    expect(normalizeWorldModeToken('level-monthly')).toBe('level-monthly');
  });

  it('обратный маппинг в легаси для старого /data', () => {
    expect(worldModeToLegacyDataToken('step-monthly')).toBe('mom');
    expect(worldModeToLegacyDataToken('step-quarterly')).toBe('qoq');
    expect(worldModeToLegacyDataToken('yoy-annual')).toBe('yoy');
    expect(worldModeToLegacyDataToken('index-monthly')).toBe('index_first');
    expect(worldModeToLegacyDataToken('level-quarterly')).toBe('level');
  });

  it('buildWorldModeToken', () => {
    expect(buildWorldModeToken('level', 'annual')).toBe('level-annual');
  });
});

describe('stripFrequencySuffix', () => {
  it('убирает суффикс частоты из имени', () => {
    expect(stripFrequencySuffix(
      'Безработица, % экономически активного населения, помесячно',
    )).toBe('Безработица, % экономически активного населения');
    expect(stripFrequencySuffix('ВВП, поквартально')).toBe('ВВП');
    expect(stripFrequencySuffix('Индекс, за год')).toBe('Индекс');
  });
});

describe('groupModesFromApi', () => {
  it('строит двухуровневые группы: тип → частоты', () => {
    const groups = groupModesFromApi(WORLD_MOCK_MODES_FULL);
    expect(groups.map((g) => g.id)).toEqual([
      'Уровень',
      'К прошлому периоду',
      'К году',
      'Индекс',
    ]);
    const level = groups.find((g) => g.id === 'Уровень');
    expect(level.leafMode).toBeUndefined();
    expect(level.modes.map((m) => m.mode)).toEqual([
      'level-monthly',
      'level-quarterly',
      'level-annual',
    ]);
  });

  it('корректно работает без группы «К прошлому периоду»', () => {
    const groups = groupModesFromApi(WORLD_MOCK_MODES_NO_POP);
    expect(groups.map((g) => g.id)).toEqual(['Уровень', 'К году']);
    expect(groups.every((g) => g.id !== 'К прошлому периоду')).toBe(true);
  });

  it('пустой и битый вход — пустой массив', () => {
    expect(groupModesFromApi(null)).toEqual([]);
    expect(groupModesFromApi([])).toEqual([]);
    expect(groupModesFromApi([{ id: 'x' }])).toEqual([]);
  });
});

describe('adaptWorldModes (легаси → матрица)', () => {
  it('разворачивает плоские легаси-modes × frequencies', () => {
    const modes = adaptWorldModes({
      modes: WORLD_MOCK_MODES_LEGACY,
      frequencies: [
        { freq: 'monthly', official: true },
        { freq: 'quarterly', official: true },
        { freq: 'annual', official: true },
      ],
      indicator: { frequency: 'monthly' },
    });
    expect(modes.some((m) => m.id === 'level-monthly')).toBe(true);
    expect(modes.some((m) => m.id === 'level-quarterly')).toBe(true);
    expect(modes.some((m) => m.id === 'step-monthly')).toBe(true);
    expect(modes.some((m) => m.id === 'step-quarterly')).toBe(true);
    expect(modes.some((m) => m.id === 'yoy-annual')).toBe(true);
    expect(modes.every((m) => m.type && m.freq)).toBe(true);
  });

  it('дедуплицирует смешанный список легаси-id и составных токенов по каноническому id', () => {
    // Смешанный список: бэк отдаёт составные, легаси-id от старого контракта
    // нормализуются в те же канонические id → в группе остаётся одна кнопка.
    const modes = adaptWorldModes({
      modes: [
        { id: 'mom', label: 'М/м, %', group: 'К прошлому периоду', unit: '%' },
        { id: 'step-monthly', label: 'По месяцам', group: 'К прошлому периоду', type: 'step', freq: 'monthly', unit: '%' },
      ],
      frequencies: [{ freq: 'monthly', official: true }],
      indicator: { frequency: 'monthly' },
    });
    const stepModes = modes.filter((m) => m.id === 'step-monthly');
    expect(stepModes).toHaveLength(1);
    // Приоритет у записи, чей id пришёл с API без трансформации.
    expect(stepModes[0].label).toBe('По месяцам');
    expect(groupModesFromApi(modes).find((g) => g.id === 'К прошлому периоду').modes)
      .toHaveLength(1);
  });
});

describe('resolveWorldMode', () => {
  it('берёт mode из URL, если он есть в списке', () => {
    expect(resolveWorldMode(WORLD_MOCK_MODES_FULL, 'yoy-quarterly')).toBe('yoy-quarterly');
  });

  it('нормализует легаси URL и фолбэчит', () => {
    expect(resolveWorldMode(WORLD_MOCK_MODES_FULL, 'yoy', 'monthly')).toBe('yoy-monthly');
    expect(resolveWorldMode(WORLD_MOCK_MODES_FULL, 'nope')).toBe('level-monthly');
    expect(resolveWorldMode(WORLD_MOCK_MODES_FULL, null)).toBe('level-monthly');
  });
});

describe('findWorldMode / expandedGroup', () => {
  it('находит meta режима и группу', () => {
    expect(findWorldMode(WORLD_MOCK_MODES_FULL, 'step-monthly')?.group).toBe('К прошлому периоду');
    const groups = groupModesFromApi(WORLD_MOCK_MODES_FULL);
    expect(expandedGroupForWorldMode(groups, 'step-quarterly')).toBe('К прошлому периоду');
    expect(defaultModeForWorldGroup(groups, 'К прошлому периоду')).toBe('step-monthly');
  });
});

describe('collapseCountryIndicators', () => {
  it('схлопывает три частоты в одну плитку', () => {
    const collapsed = collapseCountryIndicators([
      {
        code: 'a-m',
        name: 'Безработица, % экономически активного населения, помесячно',
        unit: '%',
        frequency: 'monthly',
        points_count: 100,
      },
      {
        code: 'a-q',
        name: 'Безработица, % экономически активного населения, поквартально',
        unit: '%',
        frequency: 'quarterly',
        points_count: 40,
      },
      {
        code: 'a-a',
        name: 'Безработица, % экономически активного населения, за год',
        unit: '%',
        frequency: 'annual',
        points_count: 20,
      },
    ]);
    expect(collapsed).toHaveLength(1);
    expect(collapsed[0].code).toBe('a-m');
    expect(collapsed[0].name).toBe('Безработица, % экономически активного населения');
    expect(collapsed[0].frequencies).toEqual(['monthly', 'quarterly', 'annual']);
  });

  it('не трогает уже схлопнутый ответ API', () => {
    const input = [{
      code: 'x',
      name: 'Безработица',
      unit: '%',
      frequencies: ['monthly', 'quarterly'],
    }];
    expect(collapseCountryIndicators(input)).toHaveLength(1);
    expect(collapseCountryIndicators(input)[0].frequencies).toEqual(['monthly', 'quarterly']);
  });

  it('для схлопнутого API предпочитает locale-facing name, не name_ru', () => {
    const input = [{
      code: 'se-ei_issp_m-prd-i-sca-i21',
      name: 'Production in services index by NACE Rev. 2 activity - monthly data',
      name_ru: 'Производство услуг: гостиницы и общественное питание',
      unit: 'Index, 2021=100',
      frequencies: ['monthly'],
    }];
    const [row] = collapseCountryIndicators(input);
    expect(row.name).toBe('Production in services index by NACE Rev. 2 activity');
    expect(row.name).not.toMatch(/[А-Яа-яЁё]/);
    expect(row.name).not.toMatch(/monthly data/i);
  });
});

describe('indicatorPublicName', () => {
  it('на EN берёт name_en, если locale-facing имя русское', () => {
    const ind = {
      name: 'Валовой внутренний продукт в текущих ценах',
      name_en: 'Gross domestic product at current prices',
      name_ru: 'Валовой внутренний продукт в текущих ценах',
    };
    expect(indicatorPublicName(ind, 'en')).toBe('Gross domestic product at current prices');
    expect(indicatorPublicName(ind, 'ru')).toBe('Валовой внутренний продукт в текущих ценах');
  });

  it('на EN оставляет латинский locale-facing name (срез в имени)', () => {
    expect(indicatorPublicName({
      name: 'Production in services index: information and communication',
      name_en: 'Production in services index by NACE Rev. 2 activity - monthly data',
    }, 'en')).toBe('Production in services index: information and communication');
  });
});

describe('isEmptySeries', () => {
  it('распознаёт пустой ряд', () => {
    expect(isEmptySeries(null)).toBe(true);
    expect(isEmptySeries([])).toBe(true);
    expect(isEmptySeries([{ date: '2020-01-01', value: 1 }])).toBe(false);
  });
});

describe('formatWorldValue', () => {
  it('русская запятая и разряды', () => {
    expect(formatWorldValue(null)).toBe('—');
    expect(formatWorldValue(128.4)).toBe('128,4');
    expect(nbspToSpace(formatWorldValue(1054321, 0))).toBe('1 054 321');
  });
});

describe('worldVariantsToPickerGroup', () => {
  it('пробрасывает locale-facing groupLabel и pill labels', () => {
    const group = worldVariantsToPickerGroup(
      [
        { code: 'a', label: 'accommodation and food service activities, production' },
        { code: 'b', label: 'information and communication, production' },
      ],
      'Slice',
    );
    expect(group.label).toBe('Slice');
    expect(group.codes).toHaveLength(2);
    expect(group.codes[0].label).not.toMatch(/[А-Яа-яЁё]/);
    expect(group.codes[1].label).toContain('information');
  });

  it('по умолчанию RU groupLabel', () => {
    const group = worldVariantsToPickerGroup([
      { code: 'a', label: 'x' },
      { code: 'b', label: 'y' },
    ]);
    expect(group.label).toBe('Срез');
  });

  it('на EN берёт label_en, если label русский', () => {
    const group = worldVariantsToPickerGroup(
      [
        { code: 'ca-weo-lur', label: '% ЭАН', label_en: 'Unemployment rate' },
        { code: 'ca-weo-lp', label: 'Численность населения', label_en: 'Population' },
      ],
      'Slice',
      { locale: 'en' },
    );
    expect(group.codes.map((c) => c.label)).toEqual(['Unemployment rate', 'Population']);
    expect(group.codes.every((c) => !/[А-Яа-яЁё]/.test(c.label))).toBe(true);
  });
});

describe('worldChartTitle', () => {
  it('собирает заголовок без суффикса частоты в имени', () => {
    const title = worldChartTitle(
      { name: 'Безработица, помесячно', frequency: 'monthly' },
      { id: 'yoy-monthly', label: 'По месяцам', group: 'К году', freq: 'monthly' },
    );
    expect(title).toContain('Безработица');
    expect(title).not.toMatch(/помесячно.*помесячно/);
    expect(title).toContain('К году');
    expect(title).toContain('помесячно');
  });
});
