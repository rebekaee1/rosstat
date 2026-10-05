// @vitest-environment jsdom
import { act, cleanup, render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import LightScene from './LightScene';

function scene(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <LightScene />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  window.matchMedia = (q) => ({
    matches: false,
    media: q,
    addEventListener: () => {},
    removeEventListener: () => {},
  });
  window.requestIdleCallback = (cb) => setTimeout(cb, 0);
  window.cancelIdleCallback = (id) => clearTimeout(id);
});

afterEach(() => {
  cleanup();
});

async function settle() {
  await act(async () => {
    await new Promise((r) => setTimeout(r, 20));
  });
}

describe('LightScene', () => {
  it('рисует небо: три каустики, текстуру и шесть граней, всё скрыто от читалок экрана', () => {
    const { container } = scene('/about');
    const root = container.querySelector('.fe-scene');
    expect(root).not.toBeNull();
    expect(root.getAttribute('aria-hidden')).toBe('true');
    expect(root.querySelectorAll('.fe-scene__lamp')).toHaveLength(3);
    expect(root.querySelectorAll('.fe-scene__shard')).toHaveLength(6);
    expect(root.querySelector('.fe-scene__texture')).not.toBeNull();
    // Грани: два слоя параллакса, 0,15 и 0,3.
    const depths = [...root.querySelectorAll('.fe-scene__shard-slot')].map((n) => n.getAttribute('data-depth'));
    expect(new Set(depths)).toEqual(new Set(['0.15', '0.3']));
  });

  it('при монтировании ставит режим на html и снимает при размонтировании', () => {
    const view = scene('/about');
    expect(document.documentElement.classList.contains('fe-scene-on')).toBe(true);
    expect(document.documentElement.getAttribute('data-fe-motion')).toMatch(/^(on|off)$/);
    view.unmount();
    expect(document.documentElement.classList.contains('fe-scene-on')).toBe(false);
  });

  it('герой появляется на главной и в карточке страны, на остальных страницах его нет', async () => {
    const home = scene('/');
    await settle();
    const hero = home.container.parentElement.querySelector('.fe-scene-hero');
    expect(hero).not.toBeNull();
    expect(hero.getAttribute('data-fe-hero')).toBe('home');
    const img = hero.querySelector('img');
    // Размеры заданы (нет сдвига вёрстки), ленивая загрузка, без подписи.
    expect(img.getAttribute('width')).toBe('780');
    expect(img.getAttribute('height')).toBe('1044');
    expect(img.getAttribute('loading')).toBe('lazy');
    expect(img.getAttribute('alt')).toBe('');
    expect(hero.querySelector('source').getAttribute('width')).toBe('1600');
    home.unmount();

    const country = scene('/germany');
    await settle();
    expect(country.container.parentElement.querySelector('[data-fe-hero="country"]')).not.toBeNull();
    country.unmount();

    const other = scene('/compare');
    await settle();
    expect(other.container.parentElement.querySelector('.fe-scene-hero')).toBeNull();
    expect(other.container.parentElement.querySelector('.fe-scene-leak--top')).toBeNull();
    expect(other.container.parentElement.querySelector('.fe-scene-leak--bottom')).not.toBeNull();
  });

  it('при экономии трафика (Save-Data) героя не монтирует', async () => {
    Object.defineProperty(window.navigator, 'connection', { value: { saveData: true }, configurable: true });
    try {
      const view = scene('/');
      await settle();
      expect(view.container.parentElement.querySelector('.fe-scene-hero')).toBeNull();
    } finally {
      delete window.navigator.connection;
    }
  });
});
