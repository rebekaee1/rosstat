import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { CountryMood, CrystalDefs } from './CountryMood';
import { moodColors } from '../../lib/countryMood';

describe('moodColors', () => {
  it('даёт два цвета флага по ISO-коду в любом регистре', () => {
    expect(moodColors('de')).toEqual(['#DD0000', '#FFCE00']);
    expect(moodColors('US')).toHaveLength(2);
  });

  it('неизвестная страна получает золото бренда, а не пустоту', () => {
    expect(moodColors('ZZ')).toEqual(['#C9A24D', '#B08A3E']);
    expect(moodColors(undefined)).toEqual(['#C9A24D', '#B08A3E']);
  });

  it('все цвета таблицы — валидный HEX', () => {
    for (const code of ['AL', 'AU', 'BR', 'CN', 'FR', 'IN', 'JP', 'RU', 'ZA', 'GB']) {
      for (const color of moodColors(code)) expect(color).toMatch(/^#[0-9A-F]{6}$/i);
    }
  });
});

describe('CountryMood и CrystalDefs', () => {
  it('настроение — декоративный слой с цветами флага в CSS-переменных', () => {
    const { getByTestId } = render(<CountryMood code="DE" />);
    const mood = getByTestId('country-mood');
    expect(mood.getAttribute('aria-hidden')).toBe('true');
    expect(mood.style.getPropertyValue('--mood-a')).toBe('#DD0000');
    expect(mood.style.getPropertyValue('--mood-b')).toBe('#FFCE00');
  });

  it('градиент кристалла объявлен с id, на который ссылается CSS силуэта', () => {
    const { container } = render(<CrystalDefs />);
    const gradient = container.querySelector('linearGradient#fe-k6-crystal') || container.querySelector('#fe-k6-crystal');
    expect(gradient).toBeTruthy();
    const stops = [...gradient.querySelectorAll('stop')].map((stop) => stop.getAttribute('stop-color').toUpperCase());
    expect(stops[0]).toBe('#F3E4B8');
    expect(stops).toContain('#B08A3E');
    expect(stops[stops.length - 1]).toBe('#7A5F2A');
    expect(container.querySelector('svg').getAttribute('aria-hidden')).toBe('true');
  });
});
