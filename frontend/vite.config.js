import { resolve } from 'node:path'
import { readFileSync, writeFileSync, existsSync } from 'node:fs'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const DEFAULT_PUBLIC_ORIGIN = 'https://forecasteconomy.com'

// Ручные чанки по npm-пакету. Раньше был объектный manualChunks: он тянет в
// группу и все зависимости пакета, поэтому d3-array (зависимость и recharts,
// и d3-geo) оказывался в `charts`, и карта мира на главной скачивала и
// исполняла весь recharts (~125 КБ gzip), хотя графиков там нет. Здесь в
// `charts` — только recharts и пакеты, которые нужны исключительно ему;
// общие d3-array/internmap Rollup кладёт в отдельный маленький чанк.
// react-dom намеренно не в `vendor`: замер (Lighthouse, devtools-throttling)
// показал +~100 мс FCP на странице индикатора, когда vendor разрастается до 230 КБ.
const MANUAL_CHUNK_PACKAGES = {
  vendor: ['react', 'react-router', 'react-router-dom', 'cookie', 'set-cookie-parser'],
  query: ['@tanstack/react-query', '@tanstack/query-core', 'axios'],
  animation: ['gsap'],
  // Общие для recharts и d3-geo (карта): отдельный чанк, иначе Rollup
  // затягивает их в `charts` как зависимость ручного чанка.
  d3: ['d3-array', 'internmap'],
  charts: [
    'recharts', 'victory-vendor', '@reduxjs/toolkit', 'react-redux', 'redux', 'redux-thunk',
    'immer', 'reselect', 'es-toolkit', 'decimal.js-light', 'eventemitter3', 'tiny-invariant',
    'd3-scale', 'd3-shape', 'd3-path', 'd3-interpolate', 'd3-color', 'd3-format',
    'd3-time', 'd3-time-format', 'd3-ease', 'd3-timer',
  ],
}
const CHUNK_BY_PACKAGE = new Map(
  Object.entries(MANUAL_CHUNK_PACKAGES).flatMap(([chunk, pkgs]) => pkgs.map((pkg) => [pkg, chunk])),
)

function manualChunkFor(id) {
  const normalized = id.replace(/\\/g, '/')
  const at = normalized.lastIndexOf('/node_modules/')
  if (at < 0) return undefined
  const rest = normalized.slice(at + '/node_modules/'.length).split('/')
  const pkg = rest[0].startsWith('@') ? `${rest[0]}/${rest[1]}` : rest[0]
  return CHUNK_BY_PACKAGE.get(pkg)
}

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
        manualChunks: manualChunkFor,
      },
    },
  },
  }
})
