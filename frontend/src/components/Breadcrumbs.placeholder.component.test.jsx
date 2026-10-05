import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Breadcrumbs from './Breadcrumbs';

afterEach(cleanup);

describe('Breadcrumbs: a name that has not arrived yet', () => {
  it('shows a grey bar in place of the literal ellipsis, and a real name once it is known', () => {
    const { rerender } = render(
      <MemoryRouter><Breadcrumbs items={[{ path: '/', name: 'Главная' }, { path: '/germany', name: '…' }]} /></MemoryRouter>,
    );
    expect(screen.getByTestId('crumb-placeholder')).toBeTruthy();
    expect(document.body.textContent).not.toContain('…');
    rerender(
      <MemoryRouter><Breadcrumbs items={[{ path: '/', name: 'Главная' }, { path: '/germany', name: 'Германия' }]} /></MemoryRouter>,
    );
    expect(screen.queryByTestId('crumb-placeholder')).toBeNull();
    expect(screen.getByText('Германия')).toBeTruthy();
  });
});
