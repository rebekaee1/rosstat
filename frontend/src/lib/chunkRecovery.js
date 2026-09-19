const STORAGE_KEY = 'fe:chunk-reload:release';

// A reload is safe only after persisting its guard. In privacy/quota modes
// failing closed preserves the error UI instead of creating a reload loop.
export function createChunkRecovery({ release, getStorage, reload }) {
  const key = `${STORAGE_KEY}:${release}`;
  let attempted = false;
  return (event) => {
    if (attempted) return false;
    attempted = true;
    try {
      const storage = getStorage();
      if (storage.getItem(key) === '1') return false;
      storage.setItem(key, '1');
      if (storage.getItem(key) !== '1') return false;
    } catch {
      return false;
    }
    reload();
    event?.preventDefault?.();
    return true;
  };
}
