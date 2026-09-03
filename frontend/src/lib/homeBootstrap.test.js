/** @vitest-environment jsdom */
import { afterEach, describe, expect, it } from 'vitest';
import { QueryClient } from '@tanstack/react-query';
import {
  HOME_BOOTSTRAP_ID,
  readHomeBootstrap,
  resetHomeBootstrapCache,
  seedQueryClientFromHomeBootstrap,
} from './homeBootstrap';
import { indicatorsListQueryKey } from './hooks';

function mountBootstrap(payload) {
  const el = document.createElement('script');
  el.type = 'application/json';
  el.id = HOME_BOOTSTRAP_ID;
  el.textContent = JSON.stringify(payload);
  document.body.appendChild(el);
}

afterEach(() => {
  resetHomeBootstrapCache();
  document.getElementById(HOME_BOOTSTRAP_ID)?.remove();
});

describe('homeBootstrap', () => {
  it('читает JSON из #fe-bootstrap', () => {
    mountBootstrap({
      locale: 'ru',
      indicators: [{ code: 'cpi', name: 'ИПЦ', is_listed: true }],
    });
    expect(readHomeBootstrap().indicators[0].code).toBe('cpi');
  });

  it('кладёт flagships в QueryClient и помечает ключ stale', () => {
    const list = [{ code: 'cpi', name: 'ИПЦ', is_listed: true }];
    mountBootstrap({ locale: 'ru', indicators: list });
    const qc = new QueryClient();
    expect(seedQueryClientFromHomeBootstrap(qc)).toBe(true);
    const key = indicatorsListQueryKey('ru');
    expect(qc.getQueryData(key)).toEqual(list);
    const cached = qc.getQueryCache().find({ queryKey: key });
    expect(cached?.state.isInvalidated).toBe(true);
  });
});
