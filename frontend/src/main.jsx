import { createRoot } from 'react-dom/client';
import { QueryClient } from '@tanstack/react-query';
import * as Sentry from '@sentry/react';
import SpaRoot from './SpaRoot.jsx';
import { seedQueryClientFromHomeBootstrap } from './lib/homeBootstrap';
import { createChunkRecovery } from './lib/chunkRecovery';
import './index.css';

// The entry URL contains Vite's content hash, including local builds without
// a release ID. Never reset the guard on successful startup or by a timer.
const reloadForMissingChunk = createChunkRecovery({
  release: import.meta.url,
  getStorage: () => window.sessionStorage,
  reload: () => window.location.reload(),
});

window.addEventListener('vite:preloadError', reloadForMissingChunk);
window.addEventListener('unhandledrejection', (event) => {
  const msg = String(event.reason?.message || event.reason || '');
  if (/ChunkLoadError|Failed to fetch dynamically imported module|Loading chunk/i.test(msg)) {
    reloadForMissingChunk(event);
  }
});

if (import.meta.env.VITE_SENTRY_DSN) {
  Sentry.init({
    dsn: import.meta.env.VITE_SENTRY_DSN,
    environment: import.meta.env.MODE,
    tracesSampleRate: 0.1,
    replaysSessionSampleRate: 0,
    replaysOnErrorSampleRate: 0.1,
  });
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
});
seedQueryClientFromHomeBootstrap(queryClient);

createRoot(document.getElementById('root')).render(
  <SpaRoot queryClient={queryClient} />,
);
