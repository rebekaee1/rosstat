"""152-ФЗ (круг 11): в LLM не уходят имена, почты и телефоны."""
import json

from app.services.pii_scrub import (
    MASK,
    contains_pii,
    sanitize_memory_for_llm,
    sanitize_snapshot_for_llm,
    scrub_text,
)
from app.services.pulse_report import build_llm_user_content


def test_scrub_text_masks_email_and_phone_but_keeps_search_numbers():
    assert scrub_text("напишите ivan.petrov@mail.ru пожалуйста") == f"напишите {MASK} пожалуйста"
    assert scrub_text("+7 (999) 123-45-67") == MASK
    assert scrub_text("89991234567") == MASK
    assert scrub_text("4276 1234 5678 9012") == MASK
    # обычные поисковые запросы не затрагиваются
    for q in ("ввп 2025", "инфляция 2020-2025", "курс 90.5", "ипотека 12.5% 2026", "ключевая ставка"):
        assert scrub_text(q) == q, q
    assert not contains_pii("инфляция в россии")
    assert contains_pii("a@b.ru")


SNAPSHOT = {
    "date": "2026-10-08",
    "users": {
        "total": 130, "new": 2, "newsletter": 41,
        "new_list": [
            {"name": "Иван Петров", "contact": "ivan@example.com", "method": "email"},
            {"method": "yandex", "site_locale": "en", "country": "Germany",
             "name": "Анна", "contact": "anna@yandex.ru"},
        ],
    },
    "events": {
        "search_top": {"ввп": 3, "bob@example.org": 1, "+7 999 111-22-33": 1},
        "search_zero_results": {"credit@bank.ru": 1},
    },
    "behavior": {
        "copied_top": {"8.4%": 3, "ivan@example.com": 1},
        "clicks_top": [{"element": "nav > a", "text": "Привет, ivan@example.com", "n": 2}],
    },
    "acquisition": {"search_phrases_top": [{"phrase": "почта admin@site.ru", "visits": 4}]},
}


def test_snapshot_for_llm_has_no_names_or_emails():
    clean = sanitize_snapshot_for_llm(SNAPSHOT)
    blob = json.dumps(clean, ensure_ascii=False)
    for secret in ("Иван Петров", "Анна", "ivan@example.com", "anna@yandex.ru", "bob@example.org",
                   "credit@bank.ru", "admin@site.ru", "999 111-22-33"):
        assert secret not in blob, secret
    # число, способ входа, язык и страна остаются
    assert clean["users"]["new"] == 2
    assert clean["users"]["new_list"] == [
        {"method": "email"},
        {"method": "yandex", "site_locale": "en"},  # страна отдельного человека в модель не уходит
    ]
    assert clean["events"]["search_top"]["ввп"] == 3


def test_snapshot_for_llm_does_not_mutate_original():
    before = json.dumps(SNAPSHOT, ensure_ascii=False, sort_keys=True)
    sanitize_snapshot_for_llm(SNAPSHOT)
    assert json.dumps(SNAPSHOT, ensure_ascii=False, sort_keys=True) == before


def test_llm_user_content_is_clean_for_snapshot_memory_and_hypotheses():
    memory = [{"date": "2026-10-07", "summary": "писал support@forecasteconomy.com про ипотеку"}]
    hypotheses = [{"id": 1, "statement": "тест", "rationale": "см. user@example.com"}]
    content = build_llm_user_content(SNAPSHOT, memory, hypotheses)
    for secret in ("Иван Петров", "ivan@example.com", "support@forecasteconomy.com", "user@example.com"):
        assert secret not in content, secret
    assert MASK in content


def test_memory_sanitizer_keeps_numbers():
    out = sanitize_memory_for_llm([{"date": "2026-10-07", "events": 150, "summary": "ok"}])
    assert out == [{"date": "2026-10-07", "events": 150, "summary": "ok"}]


def test_users_snapshot_has_method_and_language_but_no_name_or_email(auth_env):
    import asyncio
    import uuid
    from datetime import datetime

    from app.models import EmailCredential, OAuthIdentity, User, UserSignup
    from app.services import pulse

    start, end = datetime(2026, 10, 7, 21, 0), datetime(2026, 10, 8, 21, 0)
    u_mail, u_ya = uuid.uuid4(), uuid.uuid4()

    async def run():
        async with auth_env["session_maker"]() as db:
            db.add_all([
                User(id=u_mail, display_name="Иван Петров", created_at=datetime(2026, 10, 8, 6, 0)),
                User(id=u_ya, display_name="Анна", created_at=datetime(2026, 10, 8, 7, 0)),
                EmailCredential(user_id=u_mail, email="ivan@example.com", password_hash="x"),
                OAuthIdentity(user_id=u_ya, provider="yandex", provider_user_id="1", email="anna@yandex.ru"),
                UserSignup(user_id=u_ya, created_at=datetime(2026, 10, 8, 7, 0), site_locale="en", country="Германия"),
            ])
            await db.commit()
            return await pulse._users_snapshot(db, start, end)

    snap = asyncio.run(run())
    assert snap["new"] == 2 and snap["total"] == 2
    blob = json.dumps(snap, ensure_ascii=False)
    for secret in ("Иван", "Петров", "Анна", "ivan@example.com", "anna@yandex.ru", "Германия"):
        assert secret not in blob, secret
    assert sorted(map(json.dumps, snap["new_list"])) == sorted(map(json.dumps, [
        {"method": "email"}, {"method": "yandex", "site_locale": "en"}]))
