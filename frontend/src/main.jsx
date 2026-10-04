import { createRoot } from 'react-dom/client';
import { QueryClient } from '@tanstack/react-query';
import * as Sentry from '@sentry/react';
import SpaRoot from './SpaRoot.jsx';
import { seedQueryClientFromHomeBootstrap } from './lib/homeBootstrap';
import { installChunkRecovery } from './lib/chunkRecovery';
import { mountWhenCssReady } from './lib/mountWhenCssReady';
import './index.css';
import './styles/data-visuals.css';

// После релиза у открытой вкладки пропадают старые хэшированные чанки: одна
// перезагрузка за новым index.html (не чаще раза в 5 минут, не при вводе текста
// и не во время загрузки файла). Иначе — обычный экран ошибки.
installChunkRecovery(window);

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
      // axios уже повторяет безопасные GET (lib/api.js); два уровня повторов давали до ~3 минут скелетона.
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});
seedQueryClientFromHomeBootstrap(queryClient);

function mountApp() {
  if (window.__feAppMounted) return;
  const root = document.getElementById('root');
  if (!root) return;
  window.__feAppMounted = true;
  // SSR-страница остаётся видимой, пока подгружается чанк маршрута (см. RouteFallback): без этого
  // посетитель из поиска видел, как готовый текст исчезает и несколько секунд висит каркас.
  const ssrPage = root.querySelector(':scope > main.seo-page');
  window.__feSsrSnapshot = ssrPage ? root.innerHTML.replace('<main class="seo-page"', '<div class="seo-page"').replace(/<\/main>\s*$/, '</div>') : null;
  createRoot(root).render(
    <SpaRoot queryClient={queryClient} />,
  );
}

// SSR stays visible under critical CSS until the full stylesheet can style React.
mountWhenCssReady(mountApp);
