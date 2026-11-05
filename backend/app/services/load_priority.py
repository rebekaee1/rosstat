"""Класс клиента для приоритета холодного рендера (ADR-0026, 05.11.2026).

nginx (frontend/nginx.conf, карта `$fe_client_class`) ставит каждому SSR-запросу заголовок `X-FE-Client-Class`:

* `crawler` — проверенный поисковый робот (сеть + UA, search-crawlers.conf);
* `referred` — есть Referer (человек из поиска или с самого сайта);
* `internal` — адрес из сети docker (прогрев кэша);
* `robot` — без Referer, UA честно называет робота (Applebot, предпросмотр ссылок);
* `anon` — без Referer, браузерный UA: так выглядела ферма 05.11.2026 (46 тысяч запросов с 39,7 тысяч IP за 53 минуты).

`robot` и `anon` — низкий приоритет: им достаётся меньше слотов холодного рендера и короткое ожидание, а при перегрузке
диска хоста они сразу получают «занято» (`seo_pages._acquire_render_slot`). Заголовок клиент подделать не может: nginx
перезаписывает его своим значением, а backend доступен только через nginx (порты на loopback). Нет заголовка (прямой
вызов, тесты, локальная разработка) — `unknown`, обычный приоритет: ошибка разметки не должна резать людей.
"""

from __future__ import annotations

from contextvars import ContextVar, Token

HEADER = "x-fe-client-class"

CRAWLER = "crawler"
REFERRED = "referred"
INTERNAL = "internal"
ROBOT = "robot"
ANON = "anon"
UNKNOWN = "unknown"

_KNOWN = frozenset({CRAWLER, REFERRED, INTERNAL, ROBOT, ANON})
LOW_PRIORITY = frozenset({ROBOT, ANON})

_client_class: ContextVar[str] = ContextVar("fe_client_class", default=UNKNOWN)


def classify(header_value: str | None) -> str:
    """Значение заголовка nginx → класс; всё незнакомое — `unknown` (обычный приоритет)."""
    value = (header_value or "").strip().lower()
    return value if value in _KNOWN else UNKNOWN


def bind(header_value: str | None) -> Token:
    return _client_class.set(classify(header_value))


def reset(token: Token) -> None:
    _client_class.reset(token)


def current() -> str:
    return _client_class.get()


def is_low_priority() -> bool:
    return _client_class.get() in LOW_PRIORITY
