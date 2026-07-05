"""Лёгкий разбор User-Agent без внешних зависимостей.

Нужен для собственного портрета аудитории (behavior_sessions): браузер,
версия, ОС, тип устройства. Точность сознательно «уровня аналитики», не
fingerprinting: покрываем реальные семейства браузеров рунета (Яндекс.Браузер,
Chrome, Safari, Firefox, Edge, Opera, Samsung Internet) и основные ОС.
Порядок проверок важен: многие UA содержат «Chrome» и «Safari» одновременно.
"""
from __future__ import annotations

import re

# (человеческое имя, regex с группой версии). Порядок = приоритет.
_BROWSERS: list[tuple[str, re.Pattern]] = [
    ("Яндекс.Браузер", re.compile(r"YaBrowser/(\d+[\.\d]*)")),
    ("Edge", re.compile(r"Edg(?:e|A|iOS)?/(\d+[\.\d]*)")),
    ("Opera", re.compile(r"(?:OPR|Opera)/(\d+[\.\d]*)")),
    ("Samsung Internet", re.compile(r"SamsungBrowser/(\d+[\.\d]*)")),
    ("Firefox", re.compile(r"(?:Firefox|FxiOS)/(\d+[\.\d]*)")),
    ("Chrome", re.compile(r"(?:Chrome|CriOS)/(\d+[\.\d]*)")),
    # Safari — последним: его токен есть почти во всех WebKit UA.
    ("Safari", re.compile(r"Version/(\d+[\.\d]*).*Safari/")),
]

_BOT_RE = re.compile(
    r"bot|crawl|spider|slurp|yandex(?:bot|images|metrika)|preview|headless|"
    r"lighthouse|pingdom|monitor", re.IGNORECASE,
)

_OSES: list[tuple[str, re.Pattern]] = [
    # Мобильные раньше десктопных: Android UA содержит «Linux».
    ("iOS", re.compile(r"iPhone|iPad|iPod")),
    ("Android", re.compile(r"Android")),
    ("Windows", re.compile(r"Windows NT")),
    ("macOS", re.compile(r"Mac OS X|Macintosh")),
    ("ChromeOS", re.compile(r"CrOS")),
    ("Linux", re.compile(r"Linux|X11")),
]

_OS_VERSION = {
    "Windows": re.compile(r"Windows NT (\d+[\.\d]*)"),
    "macOS": re.compile(r"Mac OS X (\d+[_\.\d]*)"),
    "iOS": re.compile(r"OS (\d+[_\.\d]*) like Mac"),
    "Android": re.compile(r"Android (\d+[\.\d]*)"),
}

# Маркетинговые имена Windows по NT-версии.
_WINDOWS_NAMES = {"10.0": "10/11", "6.3": "8.1", "6.2": "8", "6.1": "7"}


def parse_user_agent(ua: str | None) -> dict[str, str | None]:
    """UA → {browser, browser_version, os, os_version, device_type}.

    device_type: mobile / tablet / desktop / bot.
    """
    out: dict[str, str | None] = {
        "browser": None, "browser_version": None,
        "os": None, "os_version": None, "device_type": None,
    }
    if not ua:
        return out

    if _BOT_RE.search(ua):
        out["device_type"] = "bot"
        return out

    for name, rx in _BROWSERS:
        m = rx.search(ua)
        if m:
            out["browser"] = name
            out["browser_version"] = m.group(1).split(".")[0]
            break

    for name, rx in _OSES:
        if rx.search(ua):
            out["os"] = name
            vrx = _OS_VERSION.get(name)
            if vrx:
                vm = vrx.search(ua)
                if vm:
                    ver = vm.group(1).replace("_", ".")
                    if name == "Windows":
                        ver = _WINDOWS_NAMES.get(ver, ver)
                    out["os_version"] = ver
            break

    if re.search(r"iPad|Tablet|(?=.*Android)(?!.*Mobile)", ua):
        out["device_type"] = "tablet"
    elif re.search(r"Mobi|iPhone|iPod|Android", ua):
        out["device_type"] = "mobile"
    else:
        out["device_type"] = "desktop"
    return out
