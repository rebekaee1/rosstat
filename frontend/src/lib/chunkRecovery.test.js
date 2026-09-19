import { describe, expect, it, vi } from 'vitest';
import { createChunkRecovery } from './chunkRecovery';

function storage() {
  const data = new Map();
  return { getItem: (key) => data.get(key), setItem: (key, value) => data.set(key, value) };
}

describe('chunk recovery', () => {
  it('reloads only once for a release across startups, regardless of time', () => {
    const saved = storage();
    const reload = vi.fn();
    const options = { release: '/assets/main-releaseA.js', getStorage: () => saved, reload };
    const recover = createChunkRecovery(options);
    const event = { preventDefault: vi.fn() };
    expect(recover(event)).toBe(true);
    expect(recover(event)).toBe(false);
    expect(createChunkRecovery(options)(event)).toBe(false);
    expect(reload).toHaveBeenCalledTimes(1);
    expect(event.preventDefault).toHaveBeenCalledTimes(1);
    expect(createChunkRecovery({ ...options, release: '/assets/main-releaseB.js' })(event)).toBe(true);
    expect(reload).toHaveBeenCalledTimes(2);
    expect(createChunkRecovery(options)(event)).toBe(false);
    expect(reload).toHaveBeenCalledTimes(2);
  });

  it.each(['access', 'read', 'write', 'silent write'])('does not crash or reload when storage fails: %s', (failure) => {
    const broken = () => { throw new Error('SecurityError'); };
    const saved = storage();
    if (failure === 'read') saved.getItem = broken;
    if (failure === 'write') saved.setItem = broken;
    if (failure === 'silent write') saved.setItem = () => {};
    const reload = vi.fn();
    const event = { preventDefault: vi.fn() };
    const recover = createChunkRecovery({ release: 'A', getStorage: failure === 'access' ? broken : () => saved, reload });
    expect(recover(event)).toBe(false);
    expect(recover(event)).toBe(false);
    expect(reload).not.toHaveBeenCalled();
    expect(event.preventDefault).not.toHaveBeenCalled();
  });
});
