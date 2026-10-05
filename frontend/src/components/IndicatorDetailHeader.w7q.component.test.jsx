import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import IndicatorDetailHeader from './IndicatorDetailHeader';

afterEach(cleanup);

const renderHeader = (props) => render(
  <MemoryRouter><IndicatorDetailHeader code="weo-gdp-usd" {...props} /></MemoryRouter>,
);

describe('IndicatorDetailHeader: breadcrumbs while the name is loading', () => {
  it('shows grey bars instead of the internal code and the country until the real name arrives', () => {
    const { container } = renderHeader({ indicator: undefined, loading: true });
    const crumbs = container.querySelector('nav.fe-crumbs');
    expect(crumbs.textContent).not.toContain('weo-gdp-usd');
    expect(crumbs.textContent).not.toContain('Россия');
    expect(crumbs.querySelectorAll('.fe-crumbs__ghost').length).toBeGreaterThanOrEqual(2);
  });

  it('shows the full trail once the indicator is known', () => {
    const { container } = renderHeader({
      indicator: { name: 'ВВП в текущих долларах США', category: 'ВВП и рост', frequency: 'annual' },
      loading: false,
    });
    const crumbs = container.querySelector('nav.fe-crumbs');
    expect(crumbs.textContent).toContain('ВВП в текущих долларах США');
    expect(crumbs.textContent).toContain('Россия');
    expect(crumbs.querySelectorAll('.fe-crumbs__ghost')).toHaveLength(0);
  });
});
