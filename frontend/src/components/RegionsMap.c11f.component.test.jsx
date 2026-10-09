// Круг 11, зона F: карточка выбранного региона на карте. Кнопки одной ширины, место занято заранее, сравнение набора и «Сравнить с…».
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import RegionsMap from './RegionsMap';
import mapData from '../lib/regionsMap.json';
import { mockApiGet, renderPage } from '../test/renderPage';

afterEach(() => vi.restoreAllMocks());

const [A, B, C] = mapData.regions;
const names = { [A.slug]: 'Регион А', [B.slug]: 'Регион Б', [C.slug]: 'Регион В' };
const values = new Map([[A.slug, 10], [B.slug, 20], [C.slug, 30]]);

function mount(props = {}) {
  mockApiGet([
    ['/auth/me', { user: null }],
    ['/regions', { districts: [{ slug: 'd', name: 'Округ', regions: [A, B, C].map((r) => ({ slug: r.slug, name: names[r.slug] })) }] }],
  ]);
  return renderPage(
    <RegionsMap valuesBySlug={values} nameBySlug={names} unit="%" {...props} />,
    { path: '*', route: '/russia/region/map/x' },
  );
}

describe('RegionsMap: карточка региона (круг 11, F)', () => {
  it('пока регион не выбран, место под карточку занято подсказкой (страница не прыгает при выборе)', () => {
    mount({ compareSlugs: [], onCompareToggle: () => {}, reserveCard: true });
    const empty = screen.getByTestId('map-pick-empty');
    expect(empty.textContent).toContain('Нажмите на регион');
    expect(document.querySelector('.fe-map-pick:not(.fe-map-pick--empty)')).toBeNull();
  });

  it('без резерва (карта штатов и прежние страницы) пустой карточки нет', () => {
    mount({});
    expect(screen.queryByTestId('map-pick-empty')).toBeNull();
  });

  it('у выбранного региона две кнопки одной сетки и «Сравнить с…» во всю ширину; «В сравнение» добавляет регион в набор', async () => {
    const toggle = vi.fn();
    mount({
      pickedSlug: A.slug, compareSlugs: [], onCompareToggle: toggle, reserveCard: true,
    });
    const actions = document.querySelector('.fe-map-pick__actions--grid');
    expect(actions).toBeTruthy();
    const buttons = actions.querySelectorAll(':scope > button');
    expect([...buttons].map((b) => b.textContent.trim())).toEqual(['В сравнение', 'Открыть']);
    expect(document.querySelector('.fe-map-pick').className).toContain('fe-map-pick--reserve');
    await waitFor(() => expect(actions.querySelector('.fe-map-pick__with [data-testid="region-compare-pick"]')).toBeTruthy());
    fireEvent.click(buttons[0]);
    expect(toggle).toHaveBeenCalledWith(A.slug);
  });

  it('регион уже в наборе: «В сравнении», нажатие снова убирает; при полном наборе чужой регион добавить нельзя', async () => {
    const toggle = vi.fn();
    const { rerender } = mount({
      pickedSlug: A.slug, compareSlugs: [A.slug, B.slug], onCompareToggle: toggle, compareMax: 2, reserveCard: true,
    });
    const inSet = screen.getByRole('button', { name: 'В сравнении' });
    expect(inSet.getAttribute('aria-pressed')).toBe('true');
    fireEvent.click(inSet);
    expect(toggle).toHaveBeenCalledWith(A.slug);
    rerender(<div />);
    mount({
      pickedSlug: C.slug, compareSlugs: [A.slug, B.slug], onCompareToggle: toggle, compareMax: 2, reserveCard: true,
    });
    await waitFor(() => expect(screen.getAllByRole('button', { name: 'В сравнение' }).pop().disabled).toBe(true));
  });
});
