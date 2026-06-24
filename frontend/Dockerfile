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
RUN npm run build

# Stage 2: Production
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

RUN chown -R nginx:nginx /usr/share/nginx/html /var/cache/nginx /var/log/nginx /run

USER nginx

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
