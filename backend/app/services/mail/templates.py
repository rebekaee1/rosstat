"""Письма Forecast Economy: тема, прехедер, HTML и простой текст (ADR-0032).

Вид «хрустальное письмо» (переделка 14.11.2026 по замечаниям владельца, смотрено в его
Яндекс Почте) — принципы владельца из [design-system](../../../../docs/design-system.md):

* шапка — сапфировый хрусталь: тёмный холодный фон со светом и гранями (картинка
  ``assets/hero-crystal.jpg``; без картинок — ровный сапфир) и стеклянная F
  (``assets/f-glass.png``, 3× от размера показа — без пикселя), знак forecasteconomy
  светлым, подпись на языке письма;
* под шапкой одна тонкая золотая линия — единственное золото письма;
* плита письма отделена светлотой и тенью, без рамок; блоки данных — второй слой светлее
  фона; фон вокруг — холодный свет, не голый;
* картинки идут внутри письма (``cid:``), а не по ссылке: показываются сразу, без
  «загрузить изображения», и не зависят от выпуска сайта;
* ни одного технического слова и длинной ссылки на виду: запасная ссылка — короткой фразой.

Вёрстка — таблицы и встроенные стили (Яндекс Почта, Mail.ru, Gmail, Apple Mail, Outlook).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from pathlib import Path

FONT = "Manrope,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
INK = "#1E2638"
TEXT = "#3F4B61"
MUTED = "#6A7488"
BLUE = "#2C4A8A"
BLUE_DEEP = "#1E3A6E"
ON_DARK = "#F2F5FA"
ON_DARK_MUTED = "#AEB9CF"
SAPPHIRE = "#13213F"
GOLD = "#B08A3E"
GOLD_BRIGHT = "#C9A24D"
BG = "#E9EDF3"
SURFACE = "#FFFFFF"
LAYER = "#F3F5F9"

ASSETS = Path(__file__).with_name("assets")
CID_F = "fe-glass-f"
CID_HERO = "fe-hero"

OPERATOR = {
    "ru": "ООО «ИИМПАКТ ПЛЮС», 123557, Москва, ул. Пресненский Вал, д. 21, помещ. 172",
    "en": "IIMPAKT PLUS LLC, 21 Presnensky Val St., premises 172, Moscow 123557, Russia",
}

STRINGS = {
    "ru": {
        "tagline": "Данные и прогнозы экономики",
        "verify.subject": "Подтвердите почту для Forecast Economy",
        "verify.preheader": "Одно нажатие — и аккаунт закреплён за этим адресом.",
        "verify.title": "Подтвердите почту",
        "verify.lead": "Вы создали аккаунт на Forecast Economy. Подтвердите, что этот адрес ваш: через него мы вернём доступ, если пароль забудется, и будем присылать только то, что вы выберете сами.",
        "verify.button": "Подтвердить почту",
        "verify.note": "Ссылка действует 7 дней. Если аккаунт создавали не вы, ничего делать не нужно: без подтверждения адрес не используется.",
        "reset.subject": "Новый пароль для Forecast Economy",
        "reset.preheader": "Ссылка действует один час.",
        "reset.title": "Новый пароль",
        "reset.lead": "Мы получили запрос на смену пароля для аккаунта с этой почтой. Нажмите кнопку и задайте новый пароль.",
        "reset.button": "Задать пароль",
        "reset.note": "Ссылка действует один час и срабатывает один раз. Если вы не запрашивали смену, ничего делать не нужно: пароль останется прежним.",
        "oauth.subject": "Как войти в Forecast Economy",
        "oauth.preheader": "Пароля нет: вы входите через {provider}.",
        "oauth.title": "Вы входите через {provider}",
        "oauth.lead": "Мы получили запрос на смену пароля, но пароля у вашего аккаунта нет: вы входите через {provider}. Откройте страницу входа и выберите {provider}. Пароль можно задать позже в личном кабинете.",
        "oauth.button": "Перейти ко входу",
        "oauth.note": "Если вы не запрашивали смену пароля, ничего делать не нужно.",
        "reconfirm.subject": "Подтвердите почту, чтобы получать письма Forecast Economy",
        "reconfirm.preheader": "Одно нажатие — и письма будут приходить на этот адрес.",
        "reconfirm.title": "Подтвердите почту",
        "reconfirm.lead": "У вас есть аккаунт на Forecast Economy. Мы начинаем присылать письма: новые значения показателей, за которыми вы следите, восстановление пароля и, если вы подписаны, обзоры. Подтвердите, что этот адрес ваш.",
        "reconfirm.button": "Подтвердить почту",
        "reconfirm.note": "Ссылка действует 7 дней. Без подтверждения на этот адрес будут приходить только письма для входа; аккаунт работает как прежде.",
        "fallback.lead": "Кнопка не нажимается?",
        "fallback.link": "Откройте страницу по ссылке",
        "service_footer": "Письмо пришло, потому что с этим адресом связан аккаунт на Forecast Economy.",
        "news_footer": "Вы получаете это письмо, потому что подписались на обзоры Forecast Economy.",
        "unsubscribe": "Отписаться",
        "unpersonalize": "Письма без персональной подборки",
        "manage": "Настройки",
        "reply": "Ответьте на это письмо — его прочитает человек.",
        "test.subject": "Проверка почты Forecast Economy",
        "test.preheader": "Как выглядят письма сайта: шапка, блоки с числами, кнопка, подвал.",
        "test.title": "Проверка почты",
        "test.lead": "Проверочное письмо: шапка, текст, блоки с числами, кнопка и подвал с отпиской — так выглядят письма сайта.",
        "test.button": "Открыть сайт",
        "watch.subject": "Новое значение: {first}",
        "watch.subject_two": "Новые значения: {first} и {second}",
        "watch.subject_more": "Новые значения: {first} и ещё {n} {word}",
        "watch.preheader": "Вышли новые значения показателей, за которыми вы следите.",
        "watch.title": "Новые значения",
        "watch.lead": "Вышли новые данные по показателям, за которыми вы следите.",
        "watch.button": "Все слежения",
        "watch.footer": "Письмо пришло, потому что вы следите за показателями на Forecast Economy. Не больше одного письма в день.",
        "watch.unsubscribe": "Не присылать такие письма",
        "watch.as_of": "на {date}",
    },
    "en": {
        "tagline": "Economic data and forecasts",
        "verify.subject": "Confirm your email for Forecast Economy",
        "verify.preheader": "One click and your account is tied to this address.",
        "verify.title": "Confirm your email",
        "verify.lead": "You created an account on Forecast Economy. Please confirm this address is yours: it lets us restore your access if you forget the password and send you only what you choose.",
        "verify.button": "Confirm email",
        "verify.note": "The link is valid for 7 days. If you did not create an account, there is nothing to do: an unconfirmed address is not used.",
        "reset.subject": "Your new Forecast Economy password",
        "reset.preheader": "The link is valid for one hour.",
        "reset.title": "New password",
        "reset.lead": "We received a request to change the password of the account with this email. Press the button and set a new password.",
        "reset.button": "Set password",
        "reset.note": "The link is valid for one hour and works once. If you did not ask for a change, there is nothing to do: your password stays the same.",
        "oauth.subject": "How to sign in to Forecast Economy",
        "oauth.preheader": "No password: you sign in with {provider}.",
        "oauth.title": "You sign in with {provider}",
        "oauth.lead": "We received a password change request, but your account has no password: you sign in with {provider}. Open the sign-in page and choose {provider}. You can set a password later in your account.",
        "oauth.button": "Go to sign-in",
        "oauth.note": "If you did not ask for a password change, there is nothing to do.",
        "reconfirm.subject": "Confirm your email to receive Forecast Economy emails",
        "reconfirm.preheader": "One click and emails will arrive at this address.",
        "reconfirm.title": "Confirm your email",
        "reconfirm.lead": "You have an account on Forecast Economy. We are starting to send emails: new values for the indicators you follow, password recovery and, if you subscribed, reviews. Please confirm this address is yours.",
        "reconfirm.button": "Confirm email",
        "reconfirm.note": "The link is valid for 7 days. Without confirmation this address only receives sign-in emails; your account works as before.",
        "fallback.lead": "Button not working?",
        "fallback.link": "Open the page by link",
        "service_footer": "You received this email because an account on Forecast Economy uses this address.",
        "news_footer": "You receive this email because you subscribed to Forecast Economy reviews.",
        "unsubscribe": "Unsubscribe",
        "unpersonalize": "Emails without personal picks",
        "manage": "Settings",
        "reply": "Reply to this email — a person will read it.",
        "test.subject": "Forecast Economy mail check",
        "test.preheader": "How the site's emails look: header, number blocks, button, footer.",
        "test.title": "Mail check",
        "test.lead": "A test email: header, text, number blocks, button and the footer with an unsubscribe link — this is how the site's emails look.",
        "test.button": "Open the site",
        "watch.subject": "New value: {first}",
        "watch.subject_two": "New values: {first} and {second}",
        "watch.subject_more": "New values: {first} and {n} more {word}",
        "watch.preheader": "New values are out for the indicators you follow.",
        "watch.title": "New values",
        "watch.lead": "New data is out for the indicators you follow.",
        "watch.button": "All follows",
        "watch.footer": "You received this email because you follow indicators on Forecast Economy. At most one email a day.",
        "watch.unsubscribe": "Stop these emails",
        "watch.as_of": "as of {date}",
    },
}


def t(locale: str, key: str) -> str:
    return STRINGS["en" if locale == "en" else "ru"][key]


def inline_images() -> dict[str, tuple[bytes, str]]:
    """Картинки внутри письма: cid → (байты, подтип). Читаются при каждом письме (малы)."""
    return {
        CID_F: ((ASSETS / "f-glass.png").read_bytes(), "png"),
        CID_HERO: ((ASSETS / "hero-crystal.jpg").read_bytes(), "jpeg"),
    }


@dataclass
class RenderedMail:
    subject: str
    html: str
    text: str
    images: dict[str, tuple[bytes, str]] = field(default_factory=dict)


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
    masthead: str = ""  # «Неделя в цифрах · № 1 · данные на 14 ноября 2026» над заголовком
    signoff: str = ""   # «Редакция Forecast Economy» после последнего абзаца
    blocks: list[dict] = field(default_factory=list)  # блоки редактора (mail/blocks.py); иначе items
    personal_note: str = ""  # подвал персонального выпуска: «Подборка составлена по вашим действиям…»


# --- части HTML ---------------------------------------------------------------

def _p(text: str, *, color: str = TEXT, size: int = 16, margin: str = "0 0 18px", line: float = 1.62) -> str:
    return (f'<p style="margin:{margin};font-family:{FONT};font-size:{size}px;line-height:{line};'
            f'color:{color};">{escape(text)}</p>')


def _button(label: str, url: str) -> str:
    # Ячейка с цветом фона + ссылка: Outlook не знает градиентов, но берёт bgcolor.
    return (
        '<table role="presentation" class="fe-btn" cellspacing="0" cellpadding="0" border="0" style="margin:6px 0 26px;">'
        f'<tr><td align="center" bgcolor="{BLUE_DEEP}" style="border-radius:14px;background:{BLUE_DEEP};'
        f'background-image:linear-gradient(180deg,#3558A0 0%,{BLUE} 45%,{BLUE_DEEP} 100%);'
        'box-shadow:0 1px 0 rgba(255,255,255,.22) inset,0 12px 26px -12px rgba(19,33,63,.65);">'
        f'<a href="{escape(url, quote=True)}" target="_blank" style="display:inline-block;padding:15px 30px;'
        f'font-family:{FONT};font-size:16px;font-weight:600;letter-spacing:.01em;line-height:1.2;color:{ON_DARK};'
        f'text-decoration:none;border-radius:14px;">{escape(label)}&nbsp;&nbsp;&rarr;</a></td></tr></table>'
    )


def _fallback_link(locale: str, url: str) -> str:
    return (f'<p style="margin:0 0 22px;font-family:{FONT};font-size:13px;line-height:1.5;color:{MUTED};">'
            f'{escape(t(locale, "fallback.lead"))} '
            f'<a href="{escape(url, quote=True)}" target="_blank" style="color:{BLUE};text-decoration:underline;">'
            f'{escape(t(locale, "fallback.link"))}</a></p>')


def _note(text: str) -> str:
    # Пояснение отделено тонкой холодной линией-светом, а не рамкой.
    return (f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">'
            f'<tr><td style="height:1px;line-height:1px;font-size:1px;background:#E3E8F0;">&nbsp;</td></tr>'
            f'<tr><td style="padding-top:18px;">{_p(text, color=MUTED, size=13, margin="0", line=1.55)}</td></tr></table>')


def _item(item: DigestItem) -> str:
    title = escape(item.title)
    if item.url:
        title = (f'<a href="{escape(item.url, quote=True)}" target="_blank" '
                 f'style="color:{INK};text-decoration:none;">{title}</a>')
    value = ""
    if item.value:
        value = (f'<td valign="middle" align="right" style="padding:0 0 0 16px;font-family:{FONT};'
                 f'font-size:22px;font-weight:700;letter-spacing:-.02em;color:{INK};white-space:nowrap;">'
                 f'{escape(item.value)}</td>')
    text = (f'<div style="margin-top:3px;font-family:{FONT};font-size:13.5px;font-weight:400;line-height:1.5;'
            f'color:{MUTED};">{escape(item.text)}</div>') if item.text else ""
    return (
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" '
        f'style="margin:0 0 10px;background:{LAYER};border-radius:16px;'
        'box-shadow:0 1px 0 rgba(255,255,255,.9) inset;">'
        f'<tr><td style="padding:16px 20px;"><table role="presentation" width="100%" cellspacing="0" '
        f'cellpadding="0" border="0"><tr><td valign="middle" style="font-family:{FONT};font-size:15.5px;'
        f'font-weight:600;line-height:1.4;color:{INK};">{title}{text}</td>{value}</tr></table></td></tr></table>'
    )


def _footer(locale: str, *, kind: str, unsubscribe_url: str | None, manage_url: str | None,
            personal_note: str = "", unpersonalize_url: str | None = None) -> str:
    why = t(locale, {"newsletter": "news_footer", "watch": "watch.footer"}.get(kind, "service_footer"))
    links = []
    if personal_note and unpersonalize_url:
        links.append(f'<a href="{escape(unpersonalize_url, quote=True)}" style="color:{MUTED};'
                     f'text-decoration:underline;">{escape(t(locale, "unpersonalize"))}</a>')
    if unsubscribe_url:
        label = t(locale, "watch.unsubscribe" if kind == "watch" else "unsubscribe")
        links.append(f'<a href="{escape(unsubscribe_url, quote=True)}" style="color:{MUTED};'
                     f'text-decoration:underline;">{escape(label)}</a>')
    if manage_url:
        links.append(f'<a href="{escape(manage_url, quote=True)}" style="color:{MUTED};'
                     f'text-decoration:underline;">{escape(t(locale, "manage"))}</a>')
    out = ""
    if personal_note:
        out += _p(personal_note, color=MUTED, size=12, margin="0 0 10px", line=1.6)
    out += _p(why + " " + t(locale, "reply"), color=MUTED, size=12, margin="0 0 10px", line=1.6)
    if links:
        out += (f'<p style="margin:0 0 10px;font-family:{FONT};font-size:12px;line-height:1.6;color:{MUTED};">'
                + "&nbsp;&nbsp;&nbsp;".join(links) + "</p>")
    out += _p(OPERATOR["en" if locale == "en" else "ru"], color="#8A93A5", size=11, margin="0", line=1.5)
    return out


def _hero(locale: str, site_url: str) -> str:
    """Сапфировая шапка: стеклянная F и знак. Без картинок — ровный сапфир и тот же знак."""
    return (
        f'<tr><td bgcolor="{SAPPHIRE}" background="cid:{CID_HERO}" '
        f'style="background-color:{SAPPHIRE};background-image:url(cid:{CID_HERO});background-size:cover;'
        'background-position:center;border-radius:24px 24px 0 0;padding:34px 40px 30px;" class="fe-hero">'
        '<table role="presentation" cellspacing="0" cellpadding="0" border="0"><tr>'
        f'<td valign="middle" style="padding-right:10px;"><a href="{escape(site_url, quote=True)}" target="_blank">'
        f'<img src="cid:{CID_F}" width="84" height="93" alt="" '
        'style="display:block;width:84px;height:93px;border:0;outline:none;margin:-16px 0 -16px -18px;"></a></td>'
        f'<td valign="middle"><a href="{escape(site_url, quote=True)}" target="_blank" '
        f'class="fe-mark" style="text-decoration:none;color:{ON_DARK};font-family:{FONT};font-size:25px;line-height:1;'
        'letter-spacing:-.04em;"><span style="font-weight:700;color:#FFFFFF;">forecast</span>'
        f'<span style="font-weight:300;color:{ON_DARK};">economy</span></a>'
        f'<div class="fe-tag" style="margin-top:7px;font-family:{FONT};font-size:12.5px;line-height:1.2;font-weight:400;'
        f'color:{ON_DARK_MUTED};text-decoration:none;">'
        f'<span style="text-decoration:none;color:{ON_DARK_MUTED};">{escape(t(locale, "tagline"))}</span></div></td>'
        '</tr></table></td></tr>'
        # Единственное золото письма — тонкая линия, гаснущая к краям.
        f'<tr><td style="height:1px;line-height:1px;font-size:1px;background:{GOLD};'
        f'background-image:linear-gradient(90deg,rgba(176,138,62,0) 0%,{GOLD_BRIGHT} 50%,rgba(176,138,62,0) 100%);">&nbsp;</td></tr>'
    )


def layout(locale: str, *, preheader: str, body_html: str, footer_html: str, site_url: str) -> str:
    lang = "en" if locale == "en" else "ru"
    pre = (f'<div style="display:none;max-height:0;overflow:hidden;mso-hide:all;font-size:1px;'
           f'line-height:1px;color:{BG};opacity:0;">{escape(preheader)}'
           + "&#847;&zwnj;&nbsp;" * 40 + "</div>")
    bg_style = (f"background-color:{BG};background-image:radial-gradient(ellipse at 85% 0%,"
                "rgba(124,154,201,.32),rgba(124,154,201,0) 50%),radial-gradient(ellipse at 8% 100%,"
                "rgba(201,215,234,.6),rgba(201,215,234,0) 45%);")
    return f"""<!doctype html>
<html lang="{lang}" xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="only light">
<meta name="supported-color-schemes" content="light">
<meta name="x-apple-disable-message-reformatting">
<title>Forecast Economy</title>
<style>
  /* Письмо светлое: просим почту не перекрашивать (Apple Mail, iOS, браузеры с автотёмной темой). */
  :root {{ color-scheme: light only; supported-color-schemes: light; }}
  /* Outlook.com / Outlook в тёмной теме перекрашивает цвета, помечая элементы data-ogsc/ogsb:
     шапка остаётся сапфировой, знак — белым. */
  [data-ogsb] .fe-hero {{ background-color:{SAPPHIRE} !important; }}
  [data-ogsc] .fe-mark, [data-ogsc] .fe-mark span {{ color:#FFFFFF !important; }}
  [data-ogsc] .fe-tag, [data-ogsc] .fe-tag span {{ color:{ON_DARK_MUTED} !important; }}
  @media (max-width:620px) {{
    .fe-wrap {{ padding:14px 8px 28px !important; }}
    .fe-hero {{ padding:26px 24px 22px !important; border-radius:20px 20px 0 0 !important; }}
    .fe-body {{ padding:30px 24px 26px !important; }}
    .fe-card {{ border-radius:20px !important; }}
    .fe-foot {{ padding:20px 16px 0 !important; }}
    h1 {{ font-size:24px !important; }}
    .fe-btn {{ width:100% !important; }}
    .fe-btn a {{ display:block !important; text-align:center !important; }}
    .fe-val {{ display:none !important; }}
    .fe-val-m {{ display:block !important; max-height:none !important; overflow:visible !important; }}
    .fe-lead-num {{ font-size:38px !important; }}
  }}
</style>
</head>
<body style="margin:0;padding:0;background-color:{BG};-webkit-text-size-adjust:100%;">
{pre}
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" bgcolor="{BG}" style="{bg_style}">
<tr><td class="fe-wrap" align="center" style="padding:36px 16px 44px;">
<table role="presentation" class="fe-card" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:600px;border-radius:24px;background:{SURFACE};box-shadow:0 30px 60px -30px rgba(19,33,63,.45),0 2px 8px rgba(19,33,63,.06);">
{_hero(locale, site_url)}
<tr><td class="fe-body" bgcolor="{SURFACE}" style="background:{SURFACE};border-radius:0 0 24px 24px;padding:40px 40px 34px;">
{body_html}
</td></tr>
</table>
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:600px;">
<tr><td class="fe-foot" style="padding:24px 28px 0;">{footer_html}</td></tr>
</table>
</td></tr>
</table>
</body>
</html>"""


def _h1(text: str) -> str:
    return (f'<h1 style="margin:0 0 14px;font-family:{FONT};font-size:27px;line-height:1.2;font-weight:700;'
            f'letter-spacing:-.025em;color:{INK};">{escape(text)}</h1>')


def _text_footer(locale: str, *, kind: str, unsubscribe_url: str | None, manage_url: str | None) -> str:
    why = t(locale, {"newsletter": "news_footer", "watch": "watch.footer"}.get(kind, "service_footer"))
    parts = ["—", why + " " + t(locale, "reply")]
    if unsubscribe_url:
        label = t(locale, "watch.unsubscribe" if kind == "watch" else "unsubscribe")
        parts.append(f"{label}: {unsubscribe_url}")
    if manage_url:
        parts.append(f"{t(locale, 'manage')}: {manage_url}")
    parts.append(OPERATOR["en" if locale == "en" else "ru"])
    return "\n".join(parts)


# --- письма ---------------------------------------------------------------------

ACTION_KINDS = ("verify", "reset", "oauth", "reconfirm")


def render_action(kind: str, locale: str, *, action_url: str, site_url: str, manage_url: str | None = None,
                  **fmt: str) -> RenderedMail:
    """Служебное письмо с одной кнопкой: verify (подтверждение адреса), reset (сброс пароля),
    oauth (пароля нет — вход через провайдера, ``provider=``), reconfirm (подтверждение адреса
    для давно зарегистрированных)."""
    if kind not in ACTION_KINDS:
        raise ValueError(kind)

    def tx(key: str) -> str:
        return t(locale, f"{kind}.{key}").format(**fmt) if fmt else t(locale, f"{kind}.{key}")

    title = tx("title")
    body = (_h1(title) + _p(tx("lead")) + _button(tx("button"), action_url)
            + _fallback_link(locale, action_url) + _note(tx("note")))
    html = layout(locale, preheader=tx("preheader"), body_html=body,
                  footer_html=_footer(locale, kind="service", unsubscribe_url=None, manage_url=manage_url),
                  site_url=site_url)
    text = "\n\n".join([
        tx("preheader"), title, tx("lead"), f"{tx('button')}: {action_url}", tx("note"),
        _text_footer(locale, kind="service", unsubscribe_url=None, manage_url=manage_url),
    ])
    return RenderedMail(subject=tx("subject"), html=html, text=text, images=inline_images())


def _list_text(items: list[DigestItem]) -> list[str]:
    out = []
    for i in items:
        block = [f"• {i.title}" + (f" — {i.value}" if i.value else "")]
        if i.text:
            block.append(f"  {i.text}")
        if i.url:
            block.append(f"  {i.url}")
        out.append("\n".join(block))
    return out


def _ru_plural(n: int, one: str, few: str, many: str) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def watch_subject(titles: list[str], locale: str) -> str:
    """Тема сводки: «Новое значение: X», «Новые значения: X и Y», «… X и ещё 3 показателя»."""
    if len(titles) == 1:
        return t(locale, "watch.subject").format(first=titles[0])
    if len(titles) == 2:
        return t(locale, "watch.subject_two").format(first=titles[0], second=titles[1])
    n = len(titles) - 1
    word = (_ru_plural(n, "показатель", "показателя", "показателей") if locale != "en"
            else ("indicator" if n == 1 else "indicators"))
    return t(locale, "watch.subject_more").format(first=titles[0], n=n, word=word)


def render_watch(items: list[DigestItem], locale: str, *, site_url: str, cabinet_url: str,
                 unsubscribe_url: str) -> RenderedMail:
    """Сводка о новых значениях по «колокольчику»: одно письмо в день, своя отписка."""
    if not items:
        raise ValueError("empty watch digest")
    subject = watch_subject([i.title for i in items], locale)
    body = (_h1(t(locale, "watch.title")) + _p(t(locale, "watch.lead"), margin="0 0 24px")
            + "".join(_item(i) for i in items)
            + '<div style="height:16px;line-height:16px;font-size:16px;">&nbsp;</div>'
            + _button(t(locale, "watch.button"), cabinet_url))
    html = layout(locale, preheader=t(locale, "watch.preheader"), body_html=body,
                  footer_html=_footer(locale, kind="watch", unsubscribe_url=unsubscribe_url, manage_url=cabinet_url),
                  site_url=site_url)
    lines = [t(locale, "watch.preheader"), t(locale, "watch.title"), t(locale, "watch.lead"), *_list_text(items),
             f"{t(locale, 'watch.button')}: {cabinet_url}",
             _text_footer(locale, kind="watch", unsubscribe_url=unsubscribe_url, manage_url=cabinet_url)]
    return RenderedMail(subject=subject[:300], html=html, text="\n\n".join(lines), images=inline_images())


def _paragraphs(text: str, *, margin_last: str = "0 0 24px") -> str:
    parts = [x.strip() for x in (text or "").split("\n\n") if x.strip()]
    return "".join(_p(x, margin=(margin_last if i == len(parts) - 1 else "0 0 14px")) for i, x in enumerate(parts))


def preheader_of(digest: Digest) -> str:
    """Прехедер выпуска; без него — начало вступления по границе слова с многоточием."""
    if digest.preheader:
        return digest.preheader
    intro = " ".join((digest.intro or "").split())
    if len(intro) <= 110:
        return intro
    cut = intro[:110].rsplit(" ", 1)[0].rstrip(",.;:—-")
    return cut + "…"


def render_digest(digest: Digest, locale: str, *, site_url: str, unsubscribe_url: str,
                  manage_url: str | None = None, today=None, unpersonalize_url: str | None = None) -> RenderedMail:
    """Письмо рассылки: строка выпуска, заголовок, вступление, блоки, кнопка, конец, подпись."""
    from app.services.mail import blocks as blk

    body = ""
    if digest.masthead:
        body += (f'<div style="margin:0 0 10px;font-family:{FONT};font-size:12px;font-weight:600;line-height:1.3;'
                 f'color:{MUTED};">{escape(digest.masthead)}</div>')
    body += _h1(digest.title)
    body += _paragraphs(digest.intro)
    if digest.blocks:
        body += "".join(blk.render(b, locale, today) for b in digest.blocks)
    else:
        body += "".join(_item(i) for i in digest.items)
    if digest.cta_label and digest.cta_url:
        body += '<div style="height:12px;line-height:12px;font-size:12px;">&nbsp;</div>'
        body += _button(digest.cta_label, digest.cta_url)
    if digest.outro:
        body += _paragraphs(digest.outro, margin_last="0 0 6px")
    if digest.signoff:
        body += (f'<p style="margin:6px 0 0;font-family:{FONT};font-size:14px;font-weight:600;color:{INK};">'
                 f'{escape(digest.signoff)}</p>')
    preheader = preheader_of(digest)
    html = layout(locale, preheader=preheader, body_html=body,
                  footer_html=_footer(locale, kind="newsletter", unsubscribe_url=unsubscribe_url,
                                      manage_url=manage_url, personal_note=digest.personal_note,
                                      unpersonalize_url=unpersonalize_url),
                  site_url=site_url)
    # Первая строка простого текста — то, что почта покажет рядом с темой в списке писем.
    lines = [preheader or digest.title]
    if digest.masthead:
        lines.append(digest.masthead)
    lines.append(digest.title)
    if digest.intro:
        lines.append(digest.intro)
    if digest.blocks:
        lines += [blk.as_text(b, locale, today) for b in digest.blocks]
    else:
        lines += _list_text(digest.items)
    if digest.cta_label and digest.cta_url:
        lines.append(f"{digest.cta_label}: {digest.cta_url}")
    if digest.outro:
        lines.append(digest.outro)
    if digest.signoff:
        lines.append(digest.signoff)
    if digest.personal_note:
        lines.append(digest.personal_note + (f"\n{t(locale, 'unpersonalize')}: {unpersonalize_url}"
                                              if unpersonalize_url else ""))
    lines.append(_text_footer(locale, kind="newsletter", unsubscribe_url=unsubscribe_url, manage_url=manage_url))
    return RenderedMail(subject=digest.subject, html=html, text="\n\n".join(x for x in lines if x),
                        images=inline_images())


def sample_digest(locale: str, site_url: str) -> Digest:
    """Проверочный выпуск: все элементы письма рассылки, без настоящих новостей."""
    if locale == "en":
        items = [
            DigestItem("Block with a number", "A short explanation in one or two lines.", site_url, "7.7 %"),
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
