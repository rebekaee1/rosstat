import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen } from '@testing-library/react';
import CompareExample from './CompareExample';
import { mockApiGet, renderPage } from '../../test/renderPage';

afterEach(() => vi.restoreAllMocks());

function series(name, nameEn, values) {
  return {
    meta: {
      code: 'x', country_name: name, country_name_en: nameEn, concept_name: 'Безработица',
      concept_slug: 'unemployment-rate', unit: '%', frequency: 'monthly',
    },
    data: values.map((value, i) => ({
      date: `${2016 + Math.floor(i / 12)}-${String((i % 12) + 1).padStart(2, '0')}-01`,
      value,
    })),
  };
}
const MONTHS = Array.from({ length: 120 }, (_, i) => 3 + (i % 12) * 0.2);

function mount(onOpen = vi.fn()) {
  mockApiGet([
    ['/world/compare/series/germany/unemployment-rate', series('Германия', 'Germany', MONTHS)],
    ['/world/compare/series/france/unemployment-rate', series('Франция', 'France', MONTHS.map((v) => v + 4))],
  ]);
  renderPage(<CompareExample onOpen={onOpen} />, { path: '/', route: '/' });
  return onOpen;
}

describe('CompareExample', () => {
  it('рисует две линии «Германия и Франция» с флагами и последними значениями', async () => {
    mount();
    const box = await screen.findByTestId('compare-example');
    expect(box.querySelectorAll('path.fe-draw-line')).toHaveLength(2);
    expect(box.textContent).toContain('Германия');
    expect(box.textContent).toContain('Франция');
    expect(box.textContent).toMatch(/\p{Regional_Indicator}/u);
    expect(screen.getByRole('img', { name: /Германия.*Франция/ })).toBeTruthy();
  });

  it('кнопка открывает именно это сравнение', async () => {
    const onOpen = mount();
    fireEvent.click(await screen.findByRole('button', { name: /Открыть это сравнение/ }));
    expect(onOpen).toHaveBeenCalledWith(['w:germany:unemployment-rate', 'w:france:unemployment-rate']);
  });

  it('при сбое — вежливый текст и кнопка «Повторить», а не пустота', async () => {
    mockApiGet([]);
    renderPage(<CompareExample onOpen={() => {}} />, { path: '/', route: '/' });
    expect(await screen.findByTestId('compare-example-error')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Повторить' })).toBeTruthy();
  });
});
