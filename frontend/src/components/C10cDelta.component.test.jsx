/** @vitest-environment jsdom */
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render } from '@testing-library/react';
import TelemetryCard from './TelemetryCard';
import DeltaBadge from './DeltaBadge';
import { LocaleProvider } from '../i18n';
import { indicatorPolarity } from '../lib/deltaTone';

afterEach(cleanup);

describe('Г3: изменение «к прошлому значению» с явным знаком и цветом', () => {
  it('падение биткоина: «−», красный тон, маркер вниз', () => {
    const polarity = indicatorPolarity('Биткоин (BTC/USD)', 'Bitcoin (BTC/USD)', 'btc-usd');
    const { container } = render(
      <LocaleProvider>
        <TelemetryCard label="Текущее" value={80984.09} unit="USD" change={-2337.72} polarity={polarity} />
      </LocaleProvider>,
    );
    const badge = container.querySelector('.fe-delta-badge');
    expect(badge.className).toContain('fe-tone--bad');
    expect(badge.textContent).toContain('−2');
    expect(badge.querySelector('[aria-hidden="true"]').textContent).toBe('▼');
  });

  it('рост котировки: «+», зелёный тон', () => {
    const { container } = render(
      <LocaleProvider>
        <TelemetryCard label="Текущее" value={80984.09} unit="USD" change={120.5} polarity="market" />
      </LocaleProvider>,
    );
    const badge = container.querySelector('.fe-delta-badge');
    expect(badge.className).toContain('fe-tone--good');
    expect(badge.textContent).toContain('+120');
  });

  it('плашка без смысла остаётся нейтральной', () => {
    const { container } = render(<DeltaBadge delta={-2} polarity="neutral">−2,0</DeltaBadge>);
    expect(container.firstChild.className).toContain('fe-tone--neutral');
  });
});
