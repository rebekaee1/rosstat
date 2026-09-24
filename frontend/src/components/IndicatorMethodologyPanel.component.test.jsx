/** @vitest-environment jsdom */
import { expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { LocaleProvider } from '../i18n';
import IndicatorMethodologyPanel from './IndicatorMethodologyPanel';

it('links a world indicator to its published source series', () => {
  const sourceUrl = 'https://fred.stlouisfed.org/series/LASST060000000000005';
  render(
    <LocaleProvider>
      <MemoryRouter>
        <IndicatorMethodologyPanel
          indicator={{ name: 'Civilian employment', source: 'U.S. Bureau of Labor Statistics' }}
          content={{ description: 'Employed residents', methodology: 'Monthly LAUS series' }}
          sourcePath={sourceUrl}
        />
      </MemoryRouter>
    </LocaleProvider>,
  );
  expect(screen.getByRole('link', { name: /source|источник/i }).getAttribute('href')).toBe(sourceUrl);
});
