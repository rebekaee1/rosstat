import { act, fireEvent, render, screen } from '@testing-library/react';
import { useEffect } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { usePending } from './usePending';
import Chip from '../components/Chip';
import Button from '../components/Button';

function Probe({ task }) {
  const { pending, run } = usePending();
  return (
    <>
      <Chip pending={pending} onClick={() => run(task)}>Год к году</Chip>
      <Button pending={pending} onClick={() => run(task)}>Добавить</Button>
    </>
  );
}

describe('usePending + Chip/Button (круг 11, G, U31)', () => {
  it('на время ответа чип и кнопка помечены aria-busy, повторное нажатие функцию не зовёт', async () => {
    let finish;
    const task = vi.fn(() => new Promise((resolve) => { finish = resolve; }));
    render(<Probe task={task} />);
    const chip = screen.getByRole('button', { name: /Год к году/ });
    fireEvent.click(chip);
    expect(task).toHaveBeenCalledTimes(1);
    expect(chip.getAttribute('aria-busy')).toBe('true');
    expect(chip.getAttribute('data-pending')).toBe('true');
    expect(chip.querySelector('.fe-chip__spinner')).toBeTruthy();
    const button = screen.getByRole('button', { name: /Добавить/ });
    expect(button.getAttribute('aria-busy')).toBe('true');
    expect(button.disabled).toBe(true);
    fireEvent.click(chip);
    expect(task).toHaveBeenCalledTimes(1);
    await act(async () => { finish(); });
    expect(chip.getAttribute('aria-busy')).toBeNull();
    expect(chip.querySelector('.fe-chip__spinner')).toBeNull();
    expect(button.disabled).toBe(false);
  });

  it('синхронная функция ожидания не оставляет; ошибка снимает ожидание и уходит дальше', async () => {
    const sync = vi.fn();
    const { unmount } = render(<Probe task={sync} />);
    fireEvent.click(screen.getByRole('button', { name: /Год к году/ }));
    expect(screen.getByRole('button', { name: /Год к году/ }).getAttribute('aria-busy')).toBeNull();
    unmount();

    const captured = {};
    function Boom() {
      const { pending, run } = usePending();
      useEffect(() => { captured.run = run; });
      return <span>{String(pending)}</span>;
    }
    render(<Boom />);
    let caught = null;
    await act(async () => {
      try { await captured.run(() => Promise.reject(new Error('нет сети'))); } catch (error) { caught = error; }
    });
    expect(caught?.message).toBe('нет сети');
    expect(screen.getByText('false')).toBeTruthy();
  });

  it('чип без ожидания работает как раньше', () => {
    const onClick = vi.fn();
    render(<Chip onClick={onClick}>Месяц</Chip>);
    fireEvent.click(screen.getByRole('button', { name: 'Месяц' }));
    expect(onClick).toHaveBeenCalledOnce();
    expect(screen.getByRole('button', { name: 'Месяц' }).getAttribute('aria-busy')).toBeNull();
  });
});
