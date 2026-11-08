# Stage 1: Build
FROM node:22-alpine AS builder

WORKDIR /app

COPY package*.json ./
# Устойчивость к флапающей сети сервера до npm-реестра (наблюдалось 2026-06-24:
# периодические обрывы → "npm error Exit handler never called"). Больше попыток
# и длиннее таймауты, чтобы поймать рабочее окно.
RUN npm ci --no-audit --no-fund \
    --fetch-retries=6 \
    --fetch-retry-factor=2 \
    --fetch-retry-mintimeout=15000 \
    --fetch-retry-maxtimeout=120000 \
    --fetch-timeout=300000
COPY . .
ARG VITE_PUBLIC_BASE_URL=https://forecasteconomy.com
ARG VITE_APEX_LOCALE_EN=false
ARG VITE_BUILD_ID
ENV VITE_PUBLIC_BASE_URL=$VITE_PUBLIC_BASE_URL
ENV VITE_APEX_LOCALE_EN=$VITE_APEX_LOCALE_EN
ENV VITE_BUILD_ID=$VITE_BUILD_ID
RUN npm run build

# Stage 2: Production
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY search-crawlers.conf /etc/nginx/search-crawlers.conf
# Пропуск человека: entrypoint пишет секрет в /etc/nginx/fe-pass/secret.conf (пусто = выключено).
COPY --chmod=755 40-fe-human-pass.sh /docker-entrypoint.d/40-fe-human-pass.sh

# security/ is bind-mounted in prod for fail2ban; create it in-image so
# nginx -t / local runs without the host mount still succeed. CI prepares the
# host bind with uid 101 before compose up (see .github/workflows/ci.yml).
RUN mkdir -p /var/log/nginx/security /etc/nginx/fe-pass \
    && chown -R nginx:nginx /usr/share/nginx/html /var/cache/nginx /var/log/nginx /run /etc/nginx/fe-pass

USER nginx

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
