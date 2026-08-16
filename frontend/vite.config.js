import { resolve } from 'node:path'
import { readFileSync, writeFileSync, existsSync } from 'node:fs'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const DEFAULT_PUBLIC_ORIGIN = 'https://forecasteconomy.com'

function resolvePublicOrigin(env) {
  return (env.VITE_PUBLIC_BASE_URL || DEFAULT_PUBLIC_ORIGIN).replace(/\/$/, '')
}

/** Подставляет origin/host в index.html + public/robots.txt + public/llms.txt. */
function publicOriginPlugin(origin) {
  const host = new URL(origin).hostname
  const rewrite = (code) =>
    code.replaceAll('__PUBLIC_ORIGIN__', origin).replaceAll('__PUBLIC_HOST__', host)

  const rewriteDistFile = (outDir, name) => {
    const filePath = resolve(outDir, name)
    if (!existsSync(filePath)) return
    writeFileSync(filePath, rewrite(readFileSync(filePath, 'utf8')))
  }

  return {
    name: 'public-origin',
    transformIndexHtml(html) {
      return rewrite(html)
    },
    configureServer(server) {
      // Vite отдаёт public/ as-is; без middleware robots/llms останутся с плейсхолдерами.
      server.middlewares.use((req, res, next) => {
        const url = req.url?.split('?')[0]
        if (url !== '/robots.txt' && url !== '/llms.txt') return next()
        const filePath = resolve(process.cwd(), 'public', url.slice(1))
        if (!existsSync(filePath)) return next()
        res.setHeader('Content-Type', 'text/plain; charset=utf-8')
        res.end(rewrite(readFileSync(filePath, 'utf8')))
      })
    },
    writeBundle(options) {
      const outDir = options.dir || resolve(process.cwd(), 'dist')
      rewriteDistFile(outDir, 'robots.txt')
      rewriteDistFile(outDir, 'llms.txt')
    },
  }
}

/**
 * В dev без локального backend данные «пропадали»: прокси шёл на :8000.
 * По умолчанию проксируем на продакшен (только GET, публичные данные).
 * Локальный API: в .env.local задать VITE_DEV_API_PROXY=http://127.0.0.1:8000
 * NB: Прокси на прод — только чтение публичного API; мутирующих эндпоинтов нет.
 *     Если появятся POST/PUT, переключить default на localhost.
 */
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const publicOrigin = resolvePublicOrigin(env)
  const apiTarget = env.VITE_DEV_API_PROXY || publicOrigin

  return {
  plugins: [react(), tailwindcss(), publicOriginPlugin(publicOrigin)],
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
