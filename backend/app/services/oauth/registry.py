"""Реестр OAuth-провайдеров (ADR-0007).

Провайдер доступен только если сконфигурирован. fake — лишь в dev/test
(enabled + debug), на проде он невидим даже при случайно выставленном флаге
(см. также startup-assert в main.py).
"""
from app.config import settings
from app.services.oauth.base import OAuthProvider
from app.services.oauth.fake import FakeProvider
from app.services.oauth.yandex import YandexProvider
from app.services.oauth.vk import VkProvider

SUPPORTED = ("fake", "yandex", "vk")

# Провайдеры, которые показываем пользователю в UI (fake — служебный, не для UI).
PUBLIC_PROVIDERS = ("yandex", "vk")


def get_provider(name: str) -> OAuthProvider | None:
    if name == "fake":
        if settings.auth_fake_provider_enabled and settings.debug:
            return FakeProvider()
        return None
    if name == "yandex":
        if settings.oauth_yandex_client_id and settings.oauth_yandex_client_secret:
            return YandexProvider(
                settings.oauth_yandex_client_id,
                settings.oauth_yandex_client_secret,
                scope=settings.oauth_yandex_scope or None,
            )
        return None
    if name == "vk":
        if settings.oauth_vk_client_id:
            return VkProvider(settings.oauth_vk_client_id, scope=settings.oauth_vk_scope or None)
        return None
    return None


def enabled_public_providers() -> list[str]:
    """Список включённых провайдеров для UI (фронт скрывает остальные)."""
    return [name for name in PUBLIC_PROVIDERS if get_provider(name) is not None]
