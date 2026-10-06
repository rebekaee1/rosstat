import { describe, it, expect, vi } from 'vitest';
import { fireEvent, screen } from '@testing-library/react';
import MapTimeline from './MapTimeline';
import { renderPage } from '../test/renderPage';

describe('MapTimeline', () => {
  it('год — обычный текст над ползунком, а не окно выбора года (класс fe-year-pop из world.css)', () => {
    const onYearChange = vi.fn();
    renderPage(
      <MapTimeline years={[2020, 2021, 2022]} year={2021} onYearChange={onYearChange} metric="wage" />,
      { path: '/', route: '/' },
    );
    const year = screen.getByTestId('map-timeline-year');
    expect(year.textContent).toBe('2021');
    expect(year.className).not.toContain('fe-year-pop');
    expect(year.className).toContain('whitespace-nowrap');
    fireEvent.change(screen.getByRole('slider'), { target: { value: '2022' } });
    expect(onYearChange).toHaveBeenCalledWith(2022);
  });

  it('бегунок не откатывается, пока родитель (адрес) не успел обновить год: можно отматывать несколько лет подряд', () => {
    const onYearChange = vi.fn(); // родитель год не меняет, как роутер с задержкой
    renderPage(
      <MapTimeline years={[2018, 2019, 2020, 2021, 2022]} year={2022} onYearChange={onYearChange} metric="wage" />,
      { path: '/', route: '/' },
    );
    const slider = screen.getByRole('slider');
    fireEvent.change(slider, { target: { value: '2021' } });
    expect(slider.value).toBe('2021');
    fireEvent.change(slider, { target: { value: '2019' } });
    expect(slider.value).toBe('2019');
    expect(screen.getByTestId('map-timeline-year').textContent).toBe('2019');
    expect(onYearChange).toHaveBeenLastCalledWith(2019);
  });

  it('не рисуется, если лет меньше двух', () => {
    const { container } = renderPage(
      <MapTimeline years={[2020]} year={2020} onYearChange={() => {}} metric="wage" />,
      { path: '/', route: '/' },
    );
    expect(container.querySelector('input[type="range"]')).toBeNull();
  });
});
