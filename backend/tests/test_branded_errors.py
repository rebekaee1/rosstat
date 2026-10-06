"""БД3: фирменные страницы 429 и 5xx на стороне nginx (структура конфига и статические файлы)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NGINX = (ROOT / "frontend" / "nginx.conf").read_text(encoding="utf-8")
PUBLIC = ROOT / "frontend" / "public"


def test_new_nginx_blocks_are_self_contained():
    """nginx в песочнице не запускается: проверяем хотя бы, что новые блоки закрыты и стоят в нужных контекстах."""
    map_block = NGINX.split("map $request_uri $branded_error_ext {", 1)[1].split("}", 1)[0]
    assert "default" in map_block and "json" in map_block
    # map живёт в контексте http (до server), location'ы внутри server.
    assert NGINX.index("map $request_uri $branded_error_ext") < NGINX.index("server {")
    assert NGINX.index("location = /__branded-429") > NGINX.index("server {")
    for name in ("__branded-429", "__branded-50x"):
        head, tail = NGINX.split(f"location = /{name} {{", 1)
        block = tail.split("\n    }", 1)[0]
        assert block.count("{") == block.count("}") == 0
        assert block.rstrip().endswith(";")


def test_branded_429_and_5xx_are_wired_to_internal_static_pages():
    assert "error_page 429 =429 /__branded-429;" in NGINX
    assert "error_page 500 502 503 504 /__branded-50x;" in NGINX
    for name, page in (("__branded-429", "429"), ("__branded-50x", "50x")):
        block = NGINX.split(f"location = /{name} {{", 1)[1].split("}", 1)[0]
        assert "internal;" in block
        assert f"rewrite ^ /{page}.$branded_error_ext break;" in block
        assert 'add_header Cache-Control "no-store" always;' in block
        assert "Retry-After" in block
        assert "noindex" in block
    # Запросы к API получают JSON, остальные HTML.
    assert re.search(r'map \$request_uri \$branded_error_ext \{\s*default\s+html;\s*"~\^/api/"\s+json;', NGINX)


def test_branded_pages_exist_and_speak_both_languages_without_a_backend():
    for name in ("429.html", "50x.html", "404.html"):
        html = (PUBLIC / name).read_text(encoding="utf-8")
        assert "#F4F5F7" in html, f"{name}: фон бумаги"
        assert 'fill="#AD8A48"' in html, f"{name}: логотип"
        assert 'class="ru"' in html and 'class="en"' in html, f"{name}: оба языка"
        assert "·" not in html
        assert "fonts/fonts.css" in html
    again = (PUBLIC / "429.html").read_text(encoding="utf-8")
    assert "Слишком много запросов" in again and "Обновить" in again
    assert "Too many requests" in again and "Reload" in again
    assert "location.reload()" in again
    unavailable = (PUBLIC / "50x.html").read_text(encoding="utf-8")
    assert "Сайт временно недоступен" in unavailable and "Обновить" in unavailable
    assert (PUBLIC / "429.json").read_text(encoding="utf-8").strip().startswith('{"detail"')
    assert (PUBLIC / "50x.json").read_text(encoding="utf-8").strip().startswith('{"detail"')


def test_test_server_sed_keeps_the_new_blocks_untouched():
    """deploy.sh тестового сервера умножает rate= и burst=: в блоках ошибок таких токенов быть не должно."""
    for name in ("__branded-429", "__branded-50x"):
        block = NGINX.split(f"location = /{name} {{", 1)[1].split("}", 1)[0]
        assert "rate=" not in block and "burst=" not in block
    scaled = re.sub(r"rate=([0-9]+)r/s", r"rate=\g<1>00r/s", NGINX)
    scaled = re.sub(r"burst=([0-9]+)", r"burst=\g<1>0", scaled)
    assert scaled.count("limit_req_zone") == NGINX.count("limit_req_zone")
    assert "error_page 429 =429 /__branded-429;" in scaled


def test_guessed_search_address_is_a_redirect_to_the_home_search_not_a_404():
    assert "location = /search { return 301 /$is_args$args; }" in NGINX
    # Главная читает параметр q (HomeHero), поэтому запрос не теряется.
    hero = (ROOT / "frontend" / "src" / "components" / "home" / "HomeHero.jsx").read_text(encoding="utf-8")
    assert "params.get('q')" in hero


def test_test_stand_lifts_the_concurrent_connection_cap_that_caused_429():
    """БД7: все проверяющие стенда приходят с одного адреса; потолок в 8 соединений отдавал им 429."""
    deploy = (ROOT / "scripts" / "test-server" / "deploy.sh").read_text(encoding="utf-8")
    assert "s/limit_conn perip ([0-9]+)/limit_conn perip \\1000/" in deploy
    lifted = re.sub(r"limit_conn perip ([0-9]+)", r"limit_conn perip \g<1>000", NGINX)
    assert "limit_conn perip 8000;" in lifted and "limit_conn perip 8;" not in lifted
    # Лимит соединений на картинки остаётся как есть: он защищает память сервера.
    assert "limit_conn ogconn 4;" in lifted
