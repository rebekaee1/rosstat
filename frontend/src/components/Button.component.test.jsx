import { it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { MemoryRouter, Link } from 'react-router-dom';
import Button from './Button';
import Chip from './Chip';
import Spinner from './Spinner';

afterEach(cleanup);

it('renders a native button that fires onClick and is disabled while loading', () => {
  const onClick = vi.fn();
  const { rerender } = render(<Button onClick={onClick}>Go</Button>);
  fireEvent.click(screen.getByRole('button', { name: 'Go' }));
  expect(onClick).toHaveBeenCalledOnce();
  rerender(<Button onClick={onClick} loading>Go</Button>);
  const busy = screen.getByRole('button', { name: /Go/ });
  expect(busy.disabled).toBe(true);
  expect(busy.getAttribute('aria-busy')).toBe('true');
  expect(busy.querySelector('.fe-spinner')).toBeTruthy();
});

it('can render as a router link and blocks navigation while disabled', () => {
  render(<MemoryRouter><Button as={Link} to="/x" variant="secondary">Open</Button></MemoryRouter>);
  expect(screen.getByRole('link', { name: 'Open' }).getAttribute('href')).toBe('/x');
  cleanup();
  render(<MemoryRouter><Button as={Link} to="/x" disabled>Open</Button></MemoryRouter>);
  const link = screen.getByRole('link', { name: 'Open' });
  expect(link.getAttribute('aria-disabled')).toBe('true');
  expect(fireEvent.click(link)).toBe(false);
});

it('Chip exposes its state through aria-pressed and the active class', () => {
  const { rerender } = render(<Chip active>Day</Chip>);
  const chip = screen.getByRole('button', { name: 'Day' });
  expect(chip.getAttribute('aria-pressed')).toBe('true');
  expect(chip.className).toContain('is-active');
  rerender(<Chip>Day</Chip>);
  expect(screen.getByRole('button', { name: 'Day' }).getAttribute('aria-pressed')).toBe('false');
});

it('Spinner is hidden from assistive tech unless labelled', () => {
  const { container, rerender } = render(<Spinner />);
  expect(container.firstChild.getAttribute('aria-hidden')).toBe('true');
  rerender(<Spinner label="Loading" />);
  expect(screen.getByRole('status', { name: 'Loading' })).toBeTruthy();
});
