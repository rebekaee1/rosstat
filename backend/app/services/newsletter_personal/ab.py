"""Группы A/B и псевдонимная метка клика (ADR-0033).

* контрольная группа (только выпуск редакции) — постоянная для человека, доля `holdout_pct`
  (решение 15.11.2026: 0 % сейчас, включается настройкой);
* группа темы письма (личная тема и прехедер / тема редакции) — своя в каждом выпуске;
* метка клика `utm_term=r<10 знаков>` — HMAC от человека и выпуска на секрете ссылок почты: по ней
  переход из письма связывается с блоком без входа на сайт. Обратного пути к адресу нет; включается
  только вместе с флагом поведенческих сигналов (текст политики).
"""
from __future__ import annotations

import hashlib
import hmac

from app.config import settings

EXPERIMENT_HOLDOUT = "newsletter-personal-holdout"
EXPERIMENT_SUBJECT = "newsletter-personal-subject"


def bucket(user_id: str, salt: str) -> int:
    digest = hashlib.sha256(f"{salt}|{user_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % 100


def arm(user_id: str, holdout_pct: int | None = None) -> str:
    pct = settings.newsletter_personal_holdout_pct if holdout_pct is None else holdout_pct
    return "control" if bucket(user_id, EXPERIMENT_HOLDOUT) < max(0, min(100, int(pct))) else "personal"


def subject_arm(user_id: str, campaign: str, pct: int | None = None) -> str:
    share = settings.newsletter_personal_subject_ab_pct if pct is None else pct
    return "subj_personal" if bucket(user_id, f"{EXPERIMENT_SUBJECT}|{campaign}") < max(0, min(100, int(share))) \
        else "subj_base"


def click_token(user_id: str, campaign: str) -> str | None:
    secret = settings.mail_token_secret or ""
    if len(secret) < 16:
        return None
    mac = hmac.new(secret.encode("utf-8"), f"nl-click|{campaign}|{user_id}".encode("utf-8"), hashlib.sha256)
    return "r" + mac.hexdigest()[:10]


def click_tokens_enabled() -> bool:
    return bool(settings.newsletter_personal_click_token and settings.newsletter_personal_behavior_signals)


def user_hash(user_id: str) -> str:
    """Короткий отпечаток человека для логов (без адреса и самого идентификатора)."""
    secret = (settings.mail_token_secret or "fe-nl").encode("utf-8")
    return hmac.new(secret, f"nl-log|{user_id}".encode("utf-8"), hashlib.sha256).hexdigest()[:12]
