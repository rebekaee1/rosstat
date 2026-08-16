import { resolve } from 'node:path'
import { readFileSync, writeFileSync, existsSync } from 'node:fs'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const DEFAULT_PUBLIC_ORIGIN = 'https://forecasteconomy.com'

function resolvePublicOrigin(env) {
  return (env.VITE_PUBLIC_BASE_URL || DEFAULT_PUBLIC_ORIGIN).replace(/\/$/, '')
}

/** Mirror backend resolve_request_origin: Host ru.* → https://ru.{apex}. */
function originFromRequestHost(reqHost, fallbackOrigin) {
  const host = (reqHost || '').split(',')[0].trim().toLowerCase().split(':')[0]
  let apex
  try {
    apex = new URL(fallbackOrigin).hostname.replace(/^www\./, '')
  } catch {
    apex = 'forecasteconomy.com'
  }
  if (host.startsWith('ru.') || host === `ru.${apex}`) {
    return `https://ru.${apex}`
  }
  return fallbackOrigin
}

/** Подставляет origin/host в index.html + public/robots.txt + public/llms.txt. */
function publicOriginPlugin(origin) {
  const rewrite = (code, activeOrigin = origin) => {
    const host = new URL(activeOrigin).hostname
    return code
      .replaceAll('__PUBLIC_ORIGIN__', activeOrigin)
      .replaceAll('__PUBLIC_HOST__', host)
  }

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
      // Host-aware: ru.* → ru origin (prod nginx proxies these to backend).
      server.middlewares.use((req, res, next) => {
        const url = req.url?.split('?')[0]
        if (url !== '/robots.txt' && url !== '/llms.txt') return next()
        const filePath = resolve(process.cwd(), 'public', url.slice(1))
        if (!existsSync(filePath)) return next()
        const active = originFromRequestHost(
          req.headers['x-forwarded-host'] || req.headers.host,
          origin,
        )
        res.setHeader('Content-Type', 'text/plain; charset=utf-8')
        res.setHeader('Vary', 'Host')
        res.end(rewrite(readFileSync(filePath, 'utf8'), active))
      })
    },
    writeBundle(options) {
      const outDir = options.dir || resolve(process.cwd(), 'dist')
      // Dist fallback stays apex; production nginx proxies robots/llms to backend.
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
        configure: (proxy) => {
          // Vite EN preview: forward ?preview_locale= from Referer so API
          // returns name_en in `name` without touching production hosts.
          proxy.on('proxyReq', (proxyReq, req) => {
            const referer = req.headers.referer || ''
            const m = /[?&]preview_locale=(en|ru)\b/i.exec(referer)
            if (m) proxyReq.setHeader('X-FE-Locale', m[1].toLowerCase())
          })
        },
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
