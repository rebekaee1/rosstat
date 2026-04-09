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
      output: {
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
