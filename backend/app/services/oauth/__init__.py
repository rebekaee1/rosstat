"""OAuth2 (authorization-code + PKCE) — ручная реализация на httpx (ADR-0007).

Authlib не используем: его high-level клиент держит state/PKCE в session-cookie
или framework-cache, чистого Redis-свапа нет — конфликт с «state в Redis».
Провайдеры — реестр в стиле PARSER_REGISTRY (fake/yandex/vk).
"""
