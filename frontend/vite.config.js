import { resolve } from 'node:path'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

/**
 * В dev без локального backend данные «пропадали»: прокси шёл на :8000.
 * По умолчанию проксируем на продакшен (только GET, публичные данные).
 * Локальный API: в .env.local задать VITE_DEV_API_PROXY=http://127.0.0.1:8000
 * NB: Прокси на прод — только чтение публичного API; мутирующих эндпоинтов нет.
 *     Если появятся POST/PUT, переключить default на localhost.
 */
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiTarget = env.VITE_DEV_API_PROXY || 'https://forecasteconomy.com'

  return {
  plugins: [react(), tailwindcss()],
  // Версия сборки в js_error: привязка регрессий фронта к деплоям.
  define: {
    __BUILD_ID__: JSON.stringify(env.VITE_BUILD_ID || new Date().toISOString().slice(0, 10)),
  },
  server: {
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
        secure: true,
      },
    },
  },
  build: {
    rollupOptions: {
      input: {
        main: resolve(process.cwd(), 'index.html'),
        // Второй entry: тот же behavior.js для чистых SSR-страниц (~43k URL
        // SEO-программы), подключается фиксированным именем из seo_renderer.
        'behavior-standalone': resolve(process.cwd(), 'src/behavior-standalone.js'),
      },
      output: {
        // standalone-бандл — фиксированное имя (SSR-хром ссылается строкой);
        // остальные ассеты — обычный hash-номенклатура Vite.
        entryFileNames: (chunk) => (
          chunk.name === 'behavior-standalone' ? 'assets/behavior-standalone.js' : 'assets/[name]-[hash].js'
        ),
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          charts: ['recharts'],
          query: ['@tanstack/react-query', 'axios'],
          animation: ['gsap'],
        },
      },
    },
  },
  }
})
