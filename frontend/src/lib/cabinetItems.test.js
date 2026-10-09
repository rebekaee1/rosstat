// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import {
  cabinetErrorCode, cabinetErrorKey, comparisonKeyFromSearch, normalizeSavedInput, safePath, savedItemHref, watchHref,
} from './cabinetItems';

describe('safePath', () => {
  it('принимает только адреса внутри сайта', () => {
    expect(safePath('/russia/indicator/CPI?x=1')).toBe('/russia/indicator/CPI?x=1');
    expect(safePath('//evil.example')).toBeNull();
    expect(safePath('https://evil.example')).toBeNull();
    expect(safePath('/a b')).toBeNull();
    expect(safePath('/a\\b')).toBeNull();
    expect(safePath('/a\nb')).toBeNull();
    expect(safePath('javascript:alert(1)')).toBeNull();
    expect(safePath(null)).toBeNull();
    expect(safePath(`/${'a'.repeat(700)}`)).toBeNull();
  });
});

describe('normalizeSavedInput', () => {
  it('отбрасывает неизвестный вид и пустой ключ', () => {
    expect(normalizeSavedInput({ kind: 'nope', itemKey: 'x' })).toBeNull();
    expect(normalizeSavedInput({ kind: 'country', itemKey: '  ' })).toBeNull();
    expect(normalizeSavedInput({ kind: 'country', itemKey: 'x'.repeat(301) })).toBeNull();
  });

  it('обрезает название и подставляет адрес текущей страницы', () => {
    window.history.replaceState({}, '', '/turkey?x=1');
    const out = normalizeSavedInput({ kind: 'country', itemKey: 'turkey', title: ` ${'я'.repeat(300)} ` });
    expect(out.title).toHaveLength(200);
    expect(out.payload.path).toBe('/turkey?x=1');
  });

  it('чужой небезопасный адрес в payload заменяется текущей страницей', () => {
    window.history.replaceState({}, '', '/compare');
    const out = normalizeSavedInput({ kind: 'comparison', itemKey: 'codes=a,b', payload: { path: '//evil', names: ['A'] } });
    expect(out.payload.path).toBe('/compare');
    expect(out.payload.names).toEqual(['A']);
  });
});

describe('ссылки записей', () => {
  it('сохранённый адрес главнее адреса по виду', () => {
    expect(savedItemHref({ kind: 'indicator', item_key: 'CPI', payload: { path: '/turkey/indicator/cpi' } })).toBe('/turkey/indicator/cpi');
  });

  it('без адреса строит его по виду записи', () => {
    expect(savedItemHref({ kind: 'country', item_key: 'turkey' })).toBe('/turkey');
    expect(savedItemHref({ kind: 'comparison', item_key: 'codes=a,b' })).toBe('/compare?codes=a,b');
    expect(savedItemHref({ kind: 'calc', item_key: 'x' })).toBe('/calculator');
    expect(savedItemHref({ kind: 'world', item_key: 'x' })).toBeNull();
  });

  it('слежение: мировой ряд ведёт на страницу страны, региональный на рейтинг', () => {
    expect(watchHref({ subject_kind: 'world', subject_key: 'inflation', country_slug: 'turkey' })).toBe('/turkey/indicator/inflation');
    expect(watchHref({ subject_kind: 'world', subject_key: 'inflation' })).toBeNull();
    expect(watchHref({ subject_kind: 'region', subject_key: 'wage' })).toBe('/russia/region-rating/wage');
    expect(watchHref({ subject_kind: 'indicator', subject_key: 'cpi_yoy' })).toContain('cpi_yoy');
  });
});

describe('comparisonKeyFromSearch', () => {
  it('порядок параметров не меняет ключ', () => {
    expect(comparisonKeyFromSearch('?rep=index&codes=a,b')).toBe(comparisonKeyFromSearch('codes=a,b&rep=index'));
    expect(comparisonKeyFromSearch('')).toBe('');
  });
});

describe('коды ошибок', () => {
  it('берёт код из detail и подсказывает ключ текста', () => {
    expect(cabinetErrorCode({ response: { status: 409, data: { detail: { code: 'limit_reached' } } } })).toBe('limit_reached');
    expect(cabinetErrorCode({ response: { status: 401, data: {} } })).toBe('unauthorized');
    expect(cabinetErrorCode({})).toBe('network');
    expect(cabinetErrorKey('limit_reached')).toBe('c11b.err.limit');
    expect(cabinetErrorKey('whatever')).toBe('c11b.err.generic');
  });
});
