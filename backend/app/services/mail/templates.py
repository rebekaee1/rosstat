"""Письма Forecast Economy: тема, HTML и простой текст (ADR-0032).

Вид — по принципам владельца ([design-system](../../../../docs/design-system.md)):
холодно-нейтральный светлый фон со светом, плита письма отделена светлотой и мягкой
тенью (без рамок), графит и глубокий синий как основа, золото — одна тонкая линия
под знаком. Без картинок: почтовые программы часто их блокируют, а знак из текста
не теряет резкости ни на каком экране. Технических слов в тексте нет.

Вёрстка — таблицы и встроенные стили: так письмо одинаково в Яндекс Почте, Mail.ru,
Gmail, Apple Mail и Outlook. Каждый шаблон даёт и простой текст (multipart/alternative).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from html import escape

FONT = "Manrope,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
INK = "#1E2638"
TEXT = "#4B596F"
MUTED = "#5A667A"
BLUE = "#2C4A8A"
BLUE_DEEP = "#1E3A6E"
ON_BLUE = "#F2F5FA"
GOLD = "#B08A3E"
BG = "#EEF1F5"
SURFACE = "#FDFDFE"
LAYER = "#F4F5F7"

OPERATOR = {
    "ru": "ООО «ИИМПАКТ ПЛЮС», 123557, г. Москва, ул. Пресненский Вал, д. 21, помещ. 172",
    "en": "IIMPAKT PLUS LLC, 21 Presnensky Val St., premises 172, Moscow 123557, Russia",
}

STRINGS = {
    "ru": {
        "brand_tail": "Экономика в цифрах и прогнозах",
        "verify.subject": "Подтвердите адрес почты",
        "verify.preheader": "Одно нажатие — и адрес подтверждён.",
        "verify.title": "Подтвердите адрес почты",
        "verify.lead": "Вы зарегистрировались на Forecast Economy. Подтвердите, что этот адрес ваш: так мы сможем вернуть вам доступ, если вы забудете пароль, и присылать только то, что вы просили.",
        "verify.button": "Подтвердить адрес",
        "verify.note": "Ссылка действует 7 дней. Если вы не регистрировались, просто не отвечайте на это письмо — без подтверждения адрес не используется.",
        "reset.subject": "Новый пароль для Forecast Economy",
        "reset.preheader": "Ссылка для нового пароля действует один час.",
        "reset.title": "Задайте новый пароль",
        "reset.lead": "Кто-то, возможно вы, попросил сбросить пароль к аккаунту на Forecast Economy.",
        "reset.button": "Задать новый пароль",
        "reset.note": "Ссылка действует один час и срабатывает один раз. Если вы ничего не просили, просто не отвечайте на это письмо: пароль останется прежним.",
        "fallback": "Если кнопка не нажимается, откройте ссылку:",
        "service_footer": "Это служебное письмо по вашему аккаунту на Forecast Economy.",
        "news_footer": "Вы получили это письмо, потому что подписались на новости Forecast Economy при регистрации или в личном кабинете.",
        "unsubscribe": "Отписаться от рассылки",
        "manage": "Настройки в кабинете",
        "reply": "Вопросы и ответы — на info@forecasteconomy.com.",
        "test.subject": "Проверка почты Forecast Economy",
        "test.preheader": "Проверочное письмо: вид, ссылки и подпись домена.",
        "test.title": "Проверка почты",
        "test.lead": "Это проверочное письмо. Оно показывает, как выглядят письма сайта: заголовок, текст, блоки новостей, кнопка и подвал с отпиской.",
        "test.button": "Открыть сайт",
    },
    "en": {
        "brand_tail": "The economy in numbers and forecasts",
        "verify.subject": "Confirm your email address",
        "verify.preheader": "One click and your address is confirmed.",
        "verify.title": "Confirm your email address",
        "verify.lead": "You signed up for Forecast Economy. Please confirm that this address is yours: it lets us restore your access if you forget your password and send you only what you asked for.",
        "verify.button": "Confirm address",
        "verify.note": "The link is valid for 7 days. If you did not sign up, simply ignore this email — an unconfirmed address is not used.",
        "reset.subject": "Your new Forecast Economy password",
        "reset.preheader": "The link for a new password is valid for one hour.",
        "reset.title": "Set a new password",
        "reset.lead": "Someone, probably you, asked to reset the password of a Forecast Economy account.",
        "reset.button": "Set a new password",
        "reset.note": "The link is valid for one hour and works once. If you did not ask for this, simply ignore this email: your password stays the same.",
        "fallback": "If the button does not work, open this link:",
        "service_footer": "This is a service email about your Forecast Economy account.",
        "news_footer": "You received this email because you subscribed to Forecast Economy updates when signing up or in your account.",
        "unsubscribe": "Unsubscribe",
        "manage": "Account settings",
        "reply": "Questions and replies: info@forecasteconomy.com.",
        "test.subject": "Forecast Economy mail check",
        "test.preheader": "A test email: layout, links and domain signature.",
        "test.title": "Mail check",
        "test.lead": "This is a test email. It shows how the site's emails look: heading, text, news blocks, button and the footer with an unsubscribe link.",
        "test.button": "Open the site",
    },
}


def t(locale: str, key: str) -> str:
    return STRINGS["en" if locale == "en" else "ru"][key]


@dataclass
class RenderedMail:
    subject: str
    html: str
    text: str


@dataclass
class DigestItem:
    title: str
    text: str = ""
    url: str = ""
    value: str = ""  # крупное число справа («7,7 %»), необязательно


@dataclass
class Digest:
    """Содержимое выпуска рассылки на одном языке (из JSON-файла выпуска)."""
    subject: str
    title: str
    intro: str = ""
    preheader: str = ""
    items: list[DigestItem] = field(default_factory=list)
    cta_label: str = ""
    cta_url: str = ""
    outro: str = ""


# --- части HTML ---------------------------------------------------------------

def _p(text: str, *, color: str = TEXT, size: int = 15, margin: str = "0 0 16px") -> str:
    return (f'<p style="margin:{margin};font-family:{FONT};font-size:{size}px;line-height:1.6;'
            f'color:{color};">{escape(text)}</p>')


def _button(label: str, url: str) -> str:
    # «Пуленепробиваемая» кнопка: ячейка с цветом фона + ссылка (Outlook не знает градиентов).
    return (
        '<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin:8px 0 24px;">'
        f'<tr><td align="center" bgcolor="{BLUE}" style="border-radius:12px;'
        f'background:{BLUE};background-image:linear-gradient(180deg,{BLUE} 0%,{BLUE_DEEP} 100%);'
        'box-shadow:0 10px 24px -12px rgba(30,58,110,.55);">'
        f'<a href="{escape(url, quote=True)}" target="_blank" style="display:inline-block;padding:14px 28px;'
        f'font-family:{FONT};font-size:15px;font-weight:600;line-height:1.2;color:{ON_BLUE};'
        f'text-decoration:none;border-radius:12px;">{escape(label)}</a></td></tr></table>'
    )


def _fallback_link(locale: str, url: str) -> str:
    return (
        _p(t(locale, "fallback"), color=MUTED, size=13, margin="0 0 4px")
        + f'<p style="margin:0 0 20px;font-family:{FONT};font-size:13px;line-height:1.5;word-break:break-all;">'
        f'<a href="{escape(url, quote=True)}" style="color:{BLUE};text-decoration:underline;">{escape(url)}</a></p>'
    )


def _item(item: DigestItem) -> str:
    title = escape(item.title)
    if item.url:
        title = (f'<a href="{escape(item.url, quote=True)}" target="_blank" '
                 f'style="color:{INK};text-decoration:none;">{title}</a>')
    value = ""
    if item.value:
        value = (f'<td valign="top" align="right" style="padding:0 0 0 16px;font-family:{FONT};'
                 f'font-size:20px;font-weight:700;letter-spacing:-.02em;color:{INK};white-space:nowrap;">'
                 f'{escape(item.value)}</td>')
    text = (f'<div style="margin-top:4px;font-family:{FONT};font-size:14px;font-weight:400;line-height:1.55;color:{TEXT};">'
            f'{escape(item.text)}</div>') if item.text else ""
    return (
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" '
        f'style="margin:0 0 10px;background:{LAYER};border-radius:14px;">'
        f'<tr><td style="padding:16px 18px;"><table role="presentation" width="100%" cellspacing="0" '
        f'cellpadding="0" border="0"><tr><td valign="top" style="font-family:{FONT};font-size:15px;'
        f'font-weight:650;line-height:1.4;color:{INK};">{title}{text}</td>{value}</tr></table></td></tr></table>'
    )


def _footer(locale: str, *, kind: str, unsubscribe_url: str | None, manage_url: str | None) -> str:
    lines = [t(locale, "news_footer" if kind == "newsletter" else "service_footer")]
    links = []
    if unsubscribe_url:
        links.append(f'<a href="{escape(unsubscribe_url, quote=True)}" style="color:{MUTED};'
                     f'text-decoration:underline;">{escape(t(locale, "unsubscribe"))}</a>')
    if manage_url:
        links.append(f'<a href="{escape(manage_url, quote=True)}" style="color:{MUTED};'
                     f'text-decoration:underline;">{escape(t(locale, "manage"))}</a>')
    out = "".join(_p(line, color=MUTED, size=12, margin="0 0 8px") for line in lines)
    if links:
        out += (f'<p style="margin:0 0 8px;font-family:{FONT};font-size:12px;line-height:1.6;color:{MUTED};">'
                + " &nbsp;·&nbsp; ".join(links) + "</p>")
    out += _p(t(locale, "reply"), color=MUTED, size=12, margin="0 0 8px")
    out += _p(OPERATOR["en" if locale == "en" else "ru"], color=MUTED, size=11, margin="0")
    return out


def layout(locale: str, *, preheader: str, body_html: str, footer_html: str, site_url: str) -> str:
    lang = "en" if locale == "en" else "ru"
    # Невидимый прехедер: строка, которую почта показывает рядом с темой в списке писем.
    pre = (f'<div style="display:none;max-height:0;overflow:hidden;mso-hide:all;font-size:1px;'
           f'line-height:1px;color:{BG};opacity:0;">{escape(preheader)}'
           + "&#847;&zwnj;&nbsp;" * 30 + "</div>")
    brand = (
        f'<a href="{escape(site_url, quote=True)}" target="_blank" style="text-decoration:none;color:{INK};'
        f'font-family:{FONT};font-size:24px;line-height:1;letter-spacing:-.045em;">'
        # Знак как в шапке сайта: строчными, «forecast» плотным, «economy» тонким, без пробела.
        f'<span style="font-weight:750;">forecast</span><span style="font-weight:400;">economy</span></a>'
        f'<div style="margin:6px 0 0;font-family:{FONT};font-size:9px;line-height:1;font-weight:700;'
        f'letter-spacing:.24em;color:{MUTED};">ECONOMIC INTELLIGENCE</div>'
        f'<div style="margin:14px 0 0;width:30px;height:2px;line-height:2px;font-size:2px;background:{GOLD};">&nbsp;</div>'
    )
    # Фон не голый: холодный свет сверху справа и снизу слева (где почта понимает градиенты);
    # где не понимает — ровный холодный тон, плита письма всё равно светлее фона.
    bg_style = (f"background-color:{BG};background-image:radial-gradient(ellipse at 88% 0%,"
                "rgba(124,154,201,.30),rgba(124,154,201,0) 46%),radial-gradient(ellipse at 6% 100%,"
                "rgba(201,215,234,.55),rgba(201,215,234,0) 42%);")
    return f"""<!doctype html>
<html lang="{lang}" xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<meta name="supported-color-schemes" content="light">
<meta name="x-apple-disable-message-reformatting">
<title>Forecast Economy</title>
<style>
  @media (max-width:620px) {{ .fe-card {{ padding:28px 22px !important; border-radius:18px !important; }} .fe-wrap {{ padding:20px 10px !important; }} }}
  a {{ color:{BLUE}; }}
</style>
</head>
<body style="margin:0;padding:0;background-color:{BG};">
{pre}
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" bgcolor="{BG}" style="{bg_style}">
<tr><td class="fe-wrap" align="center" style="padding:40px 16px;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:600px;">
<tr><td style="padding:0 8px 22px;">{brand}</td></tr>
<tr><td class="fe-card" bgcolor="{SURFACE}" style="background:{SURFACE};border-radius:22px;padding:40px 40px 32px;box-shadow:0 1px 0 rgba(255,255,255,.95) inset,0 24px 48px -24px rgba(30,38,56,.30),0 2px 6px rgba(30,38,56,.05);">
{body_html}
</td></tr>
<tr><td style="padding:24px 12px 0;">{footer_html}</td></tr>
</table>
</td></tr>
</table>
</body>
</html>"""


def _h1(text: str) -> str:
    return (f'<h1 style="margin:0 0 14px;font-family:{FONT};font-size:24px;line-height:1.25;font-weight:700;'
            f'letter-spacing:-.02em;color:{INK};">{escape(text)}</h1>')


def _text_footer(locale: str, *, kind: str, unsubscribe_url: str | None, manage_url: str | None) -> str:
    parts = ["--", t(locale, "news_footer" if kind == "newsletter" else "service_footer")]
    if unsubscribe_url:
        parts.append(f"{t(locale, 'unsubscribe')}: {unsubscribe_url}")
    if manage_url:
        parts.append(f"{t(locale, 'manage')}: {manage_url}")
    parts += [t(locale, "reply"), OPERATOR["en" if locale == "en" else "ru"]]
    return "\n".join(parts)


# --- письма ---------------------------------------------------------------------

def render_action(kind: str, locale: str, *, action_url: str, site_url: str, manage_url: str | None = None) -> RenderedMail:
    """Служебное письмо с одной кнопкой: verify (подтверждение адреса) или reset (сброс пароля)."""
    if kind not in ("verify", "reset"):
        raise ValueError(kind)
    title = t(locale, f"{kind}.title")
    body = (_h1(title) + _p(t(locale, f"{kind}.lead")) + _button(t(locale, f"{kind}.button"), action_url)
            + _fallback_link(locale, action_url) + _p(t(locale, f"{kind}.note"), color=MUTED, size=13, margin="0"))
    html = layout(locale, preheader=t(locale, f"{kind}.preheader"), body_html=body,
                  footer_html=_footer(locale, kind="service", unsubscribe_url=None, manage_url=manage_url),
                  site_url=site_url)
    text = "\n\n".join([
        "Forecast Economy", title, t(locale, f"{kind}.lead"),
        f"{t(locale, f'{kind}.button')}: {action_url}", t(locale, f"{kind}.note"),
        _text_footer(locale, kind="service", unsubscribe_url=None, manage_url=manage_url),
    ])
    return RenderedMail(subject=t(locale, f"{kind}.subject"), html=html, text=text)


def render_digest(digest: Digest, locale: str, *, site_url: str, unsubscribe_url: str,
                  manage_url: str | None = None) -> RenderedMail:
    """Письмо рассылки: заголовок, вступление, блоки новостей, кнопка, подвал с отпиской."""
    body = _h1(digest.title)
    if digest.intro:
        body += _p(digest.intro, margin="0 0 22px")
    body += "".join(_item(i) for i in digest.items)
    if digest.cta_label and digest.cta_url:
        body += '<div style="height:14px;line-height:14px;font-size:14px;">&nbsp;</div>'
        body += _button(digest.cta_label, digest.cta_url)
    if digest.outro:
        body += _p(digest.outro, margin="8px 0 0")
    html = layout(locale, preheader=digest.preheader or digest.intro[:120], body_html=body,
                  footer_html=_footer(locale, kind="newsletter", unsubscribe_url=unsubscribe_url,
                                      manage_url=manage_url),
                  site_url=site_url)
    lines = ["Forecast Economy", digest.title]
    if digest.intro:
        lines.append(digest.intro)
    for i in digest.items:
        head = f"• {i.title}" + (f" — {i.value}" if i.value else "")
        block = [head]
        if i.text:
            block.append(f"  {i.text}")
        if i.url:
            block.append(f"  {i.url}")
        lines.append("\n".join(block))
    if digest.cta_label and digest.cta_url:
        lines.append(f"{digest.cta_label}: {digest.cta_url}")
    if digest.outro:
        lines.append(digest.outro)
    lines.append(_text_footer(locale, kind="newsletter", unsubscribe_url=unsubscribe_url, manage_url=manage_url))
    return RenderedMail(subject=digest.subject, html=html, text="\n\n".join(lines))


def sample_digest(locale: str, site_url: str) -> Digest:
    """Проверочный выпуск: все элементы письма рассылки, без настоящих новостей."""
    if locale == "en":
        items = [
            DigestItem("Block with a number", "A short explanation in one or two lines.", site_url, "7.7%"),
            DigestItem("Block without a number", "Text only, for a comment or an announcement.", site_url),
            DigestItem("Block with a title only", url=site_url),
        ]
    else:
        items = [
            DigestItem("Блок с числом", "Короткое пояснение в одну-две строки.", site_url, "7,7 %"),
            DigestItem("Блок без числа", "Только текст — для комментария или анонса.", site_url),
            DigestItem("Блок только с заголовком", url=site_url),
        ]
    return Digest(
        subject=t(locale, "test.subject"), title=t(locale, "test.title"), intro=t(locale, "test.lead"),
        preheader=t(locale, "test.preheader"), items=items,
        cta_label=t(locale, "test.button"), cta_url=site_url,
    )
