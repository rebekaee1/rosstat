import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import HomeDataScope from './HomeDataScope';
import { renderPage } from '../../test/renderPage';

function renderScope() {
  return renderPage(<HomeDataScope />, { path: '/', route: '/' });
}

describe('HomeDataScope — состав платформы в hero главной', () => {
  it('рендерится с заголовком блока и общеплатформенными цифрами', () => {
    renderScope();

    expect(screen.getByRole('heading', { name: 'Что внутри платформы' })).toBeTruthy();

    expect(screen.getByText('100+')).toBeTruthy();
    expect(screen.getByText(/макроиндикаторов России/)).toBeTruthy();

    expect(screen.getByText('36 000+')).toBeTruthy();
    expect(screen.getByText(/показателей по странам мира/)).toBeTruthy();

    expect(screen.getByText('48')).toBeTruthy();
    expect(screen.getByText(/стран мира/)).toBeTruthy();

    expect(screen.getByText('1,7 млн+')).toBeTruthy();
  });

  it('показывает официальные источники и режим обновления', () => {
    renderScope();

    expect(screen.getByText(/Росстат, Банк России, Минфин России/)).toBeTruthy();
    expect(screen.getByText(/06:00 и 20:00 МСК/)).toBeTruthy();
  });

  it('нет текста-заглушки и запрещённого разделителя mid-dot', () => {
    renderScope();

    const block = screen.getByLabelText('Что внутри платформы');
    expect(block.textContent).not.toMatch(/lorem|заглушк|mock/i);
    // U+00B7 в литерале запрещён даже в тестовых .jsx — эскейп, см. noMiddleDot.test.js.
    expect(block.textContent).not.toContain('\u00B7');
  });
});
