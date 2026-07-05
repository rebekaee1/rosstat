import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import * as Sentry from '@sentry/react';
import App from './App.jsx';
import './index.css';

// Самообновление до новой версии сайта. После деплоя хэшированные чанки
// старой сборки исчезают: у посетителя, сидящего на странице во время
// релиза, следующая ленивая навигация падает с ChunkLoadError и выглядит
// как «поехавший» сайт. Ловим vite:preloadError и один раз перезагружаем
// страницу — браузер получает свежий HTML (он no-cache) и новые ассеты.
// Одноразовый флаг в sessionStorage защищает от цикла перезагрузок.
window.addEventListener('vite:preloadError', (event) => {
  const KEY = 'fe:chunk-reload';
  if (sessionStorage.getItem(KEY)) return; // уже перезагружались — не зацикливаемся
  sessionStorage.setItem(KEY, String(Date.now()));
  event.preventDefault();
  window.location.reload();
});
window.addEventListener('load', () => {
  // Успешная загрузка — сбрасываем флаг, чтобы следующий деплой тоже покрывался.
  setTimeout(() => sessionStorage.removeItem('fe:chunk-reload'), 10000);
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

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
);
