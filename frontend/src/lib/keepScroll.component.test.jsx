import { useEffect } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, render } from '@testing-library/react';
import { MemoryRouter, useNavigate } from 'react-router-dom';
import { rememberScroll, useRestoreScroll } from './keepScroll';

afterEach(() => vi.restoreAllMocks());

const probe = { go: null };
function Probe() {
  useRestoreScroll();
  const navigate = useNavigate();
  useEffect(() => {
    probe.go = (to) => { rememberScroll(); navigate(to); };
  }, [navigate]);
  return null;
}

describe('keepScroll', () => {
  it('после смены адреса возвращает прокрутку на запомненное место', () => {
    const frames = [];
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => { frames.push(cb); return frames.length; });
    const scrollTo = vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
    Object.defineProperty(window, 'scrollY', { value: 640, configurable: true });
    render(<MemoryRouter initialEntries={['/russia/region']}><Probe /></MemoryRouter>);
    act(() => probe.go('/russia/region/map/zarplata'));
    act(() => { frames.splice(0).forEach((cb) => cb(0)); });
    expect(scrollTo).toHaveBeenCalledWith({ top: 640, left: 0, behavior: 'instant' });
  });
});
