import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AuthContext } from '../context/authContext';
import ChartBrandCaption from './ChartBrandCaption';

describe('ChartBrandCaption', () => {
  it('shows the domain only to a confirmed guest', () => {
    const { rerender } = render(
      <AuthContext.Provider value={{ isAuthed: false, isLoading: false }}>
        <ChartBrandCaption />
      </AuthContext.Provider>,
    );
    expect(screen.getByText('forecasteconomy.com')).toBeTruthy();

    rerender(
      <AuthContext.Provider value={{ isAuthed: true, isLoading: false }}>
        <ChartBrandCaption />
      </AuthContext.Provider>,
    );
    expect(screen.queryByText('forecasteconomy.com')).toBeNull();

    rerender(
      <AuthContext.Provider value={{ isAuthed: false, isLoading: true }}>
        <ChartBrandCaption />
      </AuthContext.Provider>,
    );
    expect(screen.queryByText('forecasteconomy.com')).toBeNull();
  });
});
