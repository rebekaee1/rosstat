"""Служебные письма аккаунта: подтверждение адреса и сброс пароля (ADR-0032)."""
from __future__ import annotations

from app.services.mail import service, tokens
from app.services.mail.templates import RenderedMail, render_action


def verify_mail(user_id, email: str, locale: str) -> RenderedMail:
    tok = tokens.issue("verify", str(user_id), tokens.fingerprint(service.normalize(email)))
    return render_action(
        "verify", locale, action_url=service.site_link(locale, "/account/verify-email", t=tok),
        site_url=service.site_origin(locale) + "/", manage_url=service.site_link(locale, "/account"),
    )


def reset_mail(user_id, password_hash: str, locale: str) -> RenderedMail:
    tok = tokens.issue("reset", str(user_id), tokens.fingerprint(password_hash))
    return render_action(
        "reset", locale, action_url=service.site_link(locale, "/account/reset-password", t=tok),
        site_url=service.site_origin(locale) + "/",
    )


PROVIDER_NAMES = {
    "ru": {"yandex": "Яндекс ID", "vk": "VK ID", "google": "Google"},
    "en": {"yandex": "Yandex ID", "vk": "VK ID", "google": "Google"},
}


def provider_name(provider: str, locale: str) -> str:
    return PROVIDER_NAMES["en" if locale == "en" else "ru"].get(provider, provider)


def oauth_hint_mail(provider: str, locale: str) -> RenderedMail:
    """«Пароля нет — вы входите через Яндекс ID / Google / VK ID» в ответ на «Забыли пароль?»."""
    return render_action(
        "oauth", locale, action_url=service.site_link(locale, "/login"),
        site_url=service.site_origin(locale) + "/", provider=provider_name(provider, locale),
    )


def reconfirm_mail(user_id, email: str, locale: str) -> RenderedMail:
    """Подтверждение адреса для зарегистрированных до запуска почты (та же ссылка verify)."""
    tok = tokens.issue("verify", str(user_id), tokens.fingerprint(service.normalize(email)))
    return render_action(
        "reconfirm", locale, action_url=service.site_link(locale, "/account/verify-email", t=tok),
        site_url=service.site_origin(locale) + "/", manage_url=service.site_link(locale, "/account"),
    )


def mask_email(addr: str | None) -> str:
    """r…a@yandex.ru — человек узнаёт свой адрес, посторонний по ссылке его не прочтёт."""
    if not addr or "@" not in addr:
        return ""
    name, domain = addr.split("@", 1)
    if len(name) <= 2:
        return f"{name[:1]}…@{domain}"
    return f"{name[0]}…{name[-1]}@{domain}"
