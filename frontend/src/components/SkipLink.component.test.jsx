import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import SkipLink from './SkipLink';

afterEach(() => { document.documentElement.removeAttribute('data-fe-pointer'); });

describe('SkipLink, круг 11 G (U32)', () => {
  it('пока не нажат Tab, документ помечен «указателем» (CSS прячет ссылку при программном фокусе); Tab снимает метку', () => {
    const { unmount } = render(<SkipLink />);
    expect(screen.getByRole('link').getAttribute('href')).toBe('#main-content');
    expect(document.documentElement.hasAttribute('data-fe-pointer')).toBe(true);
    fireEvent.keyDown(document, { key: 'Tab' });
    expect(document.documentElement.hasAttribute('data-fe-pointer')).toBe(false);
    fireEvent.pointerDown(document.body);
    expect(document.documentElement.hasAttribute('data-fe-pointer')).toBe(true);
    unmount();
    expect(document.documentElement.hasAttribute('data-fe-pointer')).toBe(false);
  });
});
