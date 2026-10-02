import { expect, it } from 'vitest';
import { tableRowMatches } from './tableSearch';

it('matches decimal comma, displayed thousands and raw ISO dates', () => {
  const row = { date: '2024-12-01', value: 1234.5 };
  expect(tableRowMatches(row, '1 234,5')).toBe(true);
  expect(tableRowMatches(row, '1234.5')).toBe(true);
  expect(tableRowMatches(row, '2024-12')).toBe(true);
  expect(tableRowMatches(row, '2023')).toBe(false);
});

it('keeps quarterly and annual rows within the loaded table', () => {
  const row = { date: '2024-12-31', value: 16.5 };
  expect(tableRowMatches(row, 'IV кв. 2024', { dateFormat: 'quarterly' })).toBe(true);
  expect(tableRowMatches(row, '2024-Q4', { dateFormat: 'quarterly' })).toBe(true);
  expect(tableRowMatches(row, '2024-Q3', { dateFormat: 'quarterly' })).toBe(false);
  expect(tableRowMatches(row, '2024', { dateFormat: 'annual' })).toBe(true);
  expect(tableRowMatches(row, '16,5')).toBe(true);
});

it('treats punctuation literally and does not turn null into a number', () => {
  expect(tableRowMatches({ date: '2024-01-01', value: null }, '0,00')).toBe(false);
  expect(tableRowMatches({ date: '2024-11-11', value: null }, '16,5')).toBe(false);
  expect(tableRowMatches({ date: '2024-11-11', value: 16.5 }, '100%')).toBe(false);
  expect(tableRowMatches({ date: '2024-11-11', value: 16.5 }, ' ')).toBe(true);
});
