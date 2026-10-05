import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { CountryMood, CrystalDefs } from './CountryMood';
import { moodColors } from '../../lib/countryMood';

describe('moodColors', () => {
  it('даёт два цвета флага по ISO-коду в любом регистре', () => {
    expect(moodColors('de')).toEqual(['#C9A24D', '#FFCE00']);
    expect(moodColors('FR')).toEqual(['#0055A4', '#B08A3E']);
    expect(moodColors('US')).toHaveLength(2);
  });

  it('неизвестная страна получает золото бренда, а не пустоту', () => {
    expect(moodColors('ZZ')).toEqual(['#C9A24D', '#B08A3E']);
    expect(moodColors(undefined)).toEqual(['#C9A24D', '#B08A3E']);
  });

  it('красных и розовых пятен нет: они уходят в тёплое золото бренда', () => {
    for (const code of ['AL', 'AT', 'DK', 'JP', 'PL', 'CH', 'TR', 'GE', 'LV', 'CA', 'ES', 'US', 'DE']) {
      for (const color of moodColors(code)) {
        const n = parseInt(color.slice(1), 16);
        const r = (n >> 16) & 255; const g = (n >> 8) & 255; const b = n & 255;
        // красный доминирует над зелёным и синим вместе: признак красного/розового
        expect(r > g + 60 && r > b + 60 && g < 140, `${code} ${color}`).toBe(false);
      }
    }
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
    expect(mood.style.getPropertyValue('--mood-a')).toBe('#C9A24D');
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
