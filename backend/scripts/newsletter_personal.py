"""Персональный выпуск рассылки из командной строки (ADR-0033). Адреса на экран не выводятся.

Запуск в контейнере backend (на сервере) или локально с PYTHONPATH=backend:

    python /app/scripts/newsletter_personal.py profile --user <uuid|адрес>
    python /app/scripts/newsletter_personal.py explain --user <uuid|адрес> --issue issue-ru.json issue-en.json
    python /app/scripts/newsletter_personal.py preview --user <uuid|адрес> --issue … --out /tmp/nl-preview
    python /app/scripts/newsletter_personal.py preview --persona rich|light|cold|rich-en|light-en|cold-en --issue … --out …
    python /app/scripts/newsletter_personal.py build --issue … [--persist] [--limit N]   # снимки по всем подписчикам
    python /app/scripts/newsletter_personal.py audit --issue …                           # сверка чисел с базой перед отправкой
    python /app/scripts/newsletter_personal.py aggregates                               # «запрос → ряд», связанные ряды
    python /app/scripts/newsletter_personal.py metrics --campaign <ключ>
    python /app/scripts/newsletter_personal.py send-test (--user … | --persona …) --issue … --to rebeka.ee@yandex.ru
    python /app/scripts/newsletter_personal.py campaign --issue … [--send] [--include-unverified] [--max N]

Предпросмотр и проверочное письмо по умолчанию учитывают сигналы поведения (это не отправка
людям); `--no-behavior` — как будет при выключенном флаге. `campaign --send` — только по команде
владельца: те же защиты, что у `scripts/mail.py campaign`, плюс тихие часы и частота.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve()
for candidate in ("/app", str(HERE.parents[1])):
    if os.path.isdir(os.path.join(candidate, "app")) and candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.config import settings  # noqa: E402


def _ensure_preview_secret() -> None:
    """Предпросмотр без секрета ссылок: временный секрет процесса (ничего не отправляется)."""
    if len(settings.mail_token_secret or "") < 16:
        settings.mail_token_secret = secrets.token_hex(32)


async def _user_id(db, raw: str) -> uuid.UUID:
    from sqlalchemy import func, select

    from app.models import EmailCredential, OAuthIdentity

    try:
        return uuid.UUID(raw)
    except ValueError:
        pass
    email = raw.strip().lower()
    uid = await db.scalar(select(EmailCredential.user_id).where(func.lower(EmailCredential.email) == email))
    if uid is None:
        uid = await db.scalar(select(OAuthIdentity.user_id).where(func.lower(OAuthIdentity.email) == email))
    if uid is None:
        raise SystemExit("человек не найден")
    return uid


def _issue(paths):
    from app.services.mail import campaign

    return campaign.load_issue(*paths)


async def _result(db, args, issue):
    from app.services.newsletter_personal.build import Builder, _utcnow, locale_for
    from app.services.newsletter_personal.personas import persona_signals
    from app.services.newsletter_personal.signals import collect

    behavior = not getattr(args, "no_behavior", False)
    builder = Builder(db, issue, behavior=behavior, holdout_pct=0,
                      subject_ab_pct=100 if getattr(args, "personal_subject", False) else 0,
                      dormant=getattr(args, "dormant", False) or None)
    if getattr(args, "persona", None):
        us, locale = persona_signals(args.persona, now=builder.now)
    else:
        uid = await _user_id(db, args.user)
        us = (await collect(db, [uid], now=_utcnow(), behavior=behavior))[str(uid)]
        locale = await locale_for(db, uid)
    if getattr(args, "locale", None):
        locale = args.locale
    return await builder.build(us, locale), builder


def _profile_view(p) -> dict:
    return {"tier": p.tier, "locale": p.locale, "timezone": p.timezone, "geo": p.geo, "stats": p.stats,
            "topics": p.topics, "subjects": p.subjects[:15]}


async def cmd_profile(args) -> int:
    from app.database import async_session
    from app.services.newsletter_personal.build import Builder, _utcnow, locale_for
    from app.services.newsletter_personal.signals import collect

    async with async_session() as db:
        uid = await _user_id(db, args.user)
        b = Builder(db, issue=None, behavior=not args.no_behavior)
        us = (await collect(db, [uid], now=_utcnow(), behavior=b.behavior))[str(uid)]
        p = await b.profile_for(us, await locale_for(db, uid))
    print(json.dumps(_profile_view(p), ensure_ascii=False, indent=2, default=str))
    return 0


async def cmd_explain(args) -> int:
    from app.database import async_session

    issue = _issue(args.issue)
    async with async_session() as db:
        res, _b = await _result(db, args, issue)
    print(json.dumps({"summary": res.summary(), "profile": _profile_view(res.profile) if res.profile else None,
                      "blocks": res.blocks_meta}, ensure_ascii=False, indent=2, default=str))
    return 0


def _render(issue, locale: str, payload: dict, user_id: str):
    from app.services.mail import campaign

    digest = campaign.personal_digest(issue, locale, payload)
    return campaign.render_for(issue, locale, user_id, digest)


async def cmd_preview(args) -> int:
    from app.database import async_session

    _ensure_preview_secret()
    issue = _issue(args.issue)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    async with async_session() as db:
        res, _b = await _result(db, args, issue)
    if res.payload is None:
        print(f"в выпуске нет языка {res.locale}")
        return 1
    rendered, _one = _render(issue, res.locale, res.payload, res.user_id)
    name = args.name or (f"{args.persona}" if args.persona else f"user-{res.user_id[:8]}")
    (out / f"{name}.html").write_text(rendered.html, encoding="utf-8")
    (out / f"{name}.txt").write_text(f"Subject: {rendered.subject}\n\n{rendered.text}", encoding="utf-8")
    (out / f"{name}.json").write_text(json.dumps({"summary": res.summary(), "blocks_meta": res.blocks_meta,
                                                  "payload": res.payload}, ensure_ascii=False, indent=2,
                                                 default=str), encoding="utf-8")
    print(json.dumps({"file": str(out / f"{name}.html"), **res.summary(), "subject": rendered.subject},
                     ensure_ascii=False))
    return 0


async def cmd_build(args) -> int:
    from app.database import async_session
    from app.services.newsletter_personal.build import build_campaign

    issue = _issue(args.issue)
    async with async_session() as db:
        report = await build_campaign(db, issue, persist=args.persist, limit=args.limit,
                                      behavior=True if args.behavior else None)
    print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
    return 0


_RAW_SQL = {
    "ru": "select d.date, d.value from indicator_data d join indicators i on i.id=d.indicator_id "
          "where i.code=:c and d.value is not null order by d.date desc limit 1",
    "w": "select d.date, d.value from world_data_points d join world_indicators i on i.id=d.indicator_id "
         "join world_countries c on c.id=i.country_id where i.code=:c and c.slug=:s and d.value is not null "
         "order by d.date desc limit 1",
    "rm": "select d.month, d.value from region_monthly_data d join region_indicators i on i.id=d.indicator_id "
          "join regions r on r.id=d.region_id where i.code=:c and r.slug=:s order by d.month desc limit 1",
    "ra": "select d.year, d.value from region_data d join region_indicators i on i.id=d.indicator_id "
          "join regions r on r.id=d.region_id where i.code=:c and r.slug=:s and d.value is not null "
          "order by d.year desc limit 1",
}


async def cmd_audit(args) -> int:
    """Сверка перед отправкой (правила письма, «Записка к выпуску»): каждое число личных блоков против
    последней точки ряда прямым запросом, в обход кода сборки. Ничего не пишет и не отправляет.

    Расхождение — не всегда ошибка: ряды «за год» (расчётное число) и годовые оценки незавершённого
    года сборка намеренно показывает иначе; такие строки помечены и смотрятся глазами.
    """
    from sqlalchemy import text

    from app.database import async_session
    from app.services.mail import audience
    from app.services.newsletter_personal.build import Builder
    from app.services.newsletter_personal.signals import collect

    issue = _issue(args.issue)
    checked, differ, review, stale = 0, [], [], []
    statuses: dict[str, int] = {}
    async with async_session() as db:
        b = Builder(db, issue, behavior=True, holdout_pct=0)
        ids = await audience.subscriber_ids(db)
        if args.limit:
            ids = ids[:args.limit]
        sigs = await collect(db, ids, now=b.now, behavior=True)
        seen: set[tuple[str, str]] = set()
        for uid in ids:
            rec = await audience.resolve(db, uid)
            res = await b.build(sigs[str(uid)], rec.locale if rec else "ru")
            statuses[res.status] = statuses.get(res.status, 0) + 1
            for m in res.blocks_meta:
                key = m.get("subject")
                if m.get("origin") != "personal" or not key or key.startswith("fc:") or (key, res.locale) in seen:
                    continue
                seen.add((key, res.locale))
                fact = await b.cache(res.locale).get(key)
                if fact is None:
                    differ.append({"subject": key, "problem": "в письме есть, факта нет"})
                    continue
                kind, _, rest = key.partition(":")
                if kind == "ru":
                    row = (await db.execute(text(_RAW_SQL["ru"]), {"c": rest})).first()
                else:
                    slug, code = rest.split(":", 1)
                    row = (await db.execute(text(_RAW_SQL["w" if kind == "w" else "rm"]), {"c": code, "s": slug})).first()
                    if row is None and kind == "r":
                        row = (await db.execute(text(_RAW_SQL["ra"]), {"c": code, "s": slug})).first()
                checked += 1
                if fact.stale:
                    stale.append(key)
                if row is None:
                    differ.append({"subject": key, "problem": "ряд не найден прямым запросом"})
                elif fact.headline_yoy:
                    review.append({"subject": key, "letter": fact.value_text, "note": "число «за год» — расчётное"})
                elif abs(float(row[1]) - fact.value) > 1e-6 * max(1.0, abs(float(row[1]))):
                    (review if fact.frequency == "annual" else differ).append(
                        {"subject": key, "letter": fact.value, "letter_date": fact.as_of.isoformat(),
                         "base": float(row[1]), "base_date": str(row[0])})
        await db.rollback()
    print(json.dumps({"subscribers": len(ids), "statuses": statuses, "checked": checked, "differ": differ,
                      "review_by_eye": review, "stale_in_letters": stale}, ensure_ascii=False, indent=2))
    return 1 if differ or stale else 0


async def cmd_aggregates(_args) -> int:
    from app.services.newsletter_personal.jobs import aggregates_job

    await aggregates_job()
    return 0


async def cmd_metrics(args) -> int:
    from app.database import async_session
    from app.services.newsletter_personal.metrics import campaign_metrics, summary_by_generator

    async with async_session() as db:
        m = await campaign_metrics(db, args.campaign)
    m["by_block"] = summary_by_generator(m)
    print(json.dumps(m, ensure_ascii=False, indent=2, default=str))
    return 0


async def cmd_send_test(args) -> int:
    from app.database import async_session
    from app.services.mail import service

    if not service.recipient_allowed(args.to):
        print("адрес не в списке допуска (RUSTATS_MAIL_ALLOWLIST) — не отправляю")
        return 1
    issue = _issue(args.issue)
    async with async_session() as db:
        res, _b = await _result(db, args, issue)
    if res.payload is None:
        print(f"в выпуске нет языка {res.locale}")
        return 1
    rendered, one_click = _render(issue, res.locale, res.payload, "00000000-0000-0000-0000-000000000000")
    # Тема без пометки «[test]»: проверочное письмо выглядит как настоящее (слово владельца 16.11.2026).
    if args.no_db:
        # Без журнала mail_outbox (стенд без миграции почты): прямая отправка, как `mail.py test --no-db`.
        from app.services.mail import transport

        try:
            await transport.send(transport.OutgoingMail(
                to=args.to, subject=rendered.subject, html=rendered.html, text=rendered.text, kind="newsletter",
                unsubscribe_url=one_click, campaign="test", images=getattr(rendered, "images", None) or {}))
            status = "sent"
        except (transport.SendError, transport.MailConfigError) as exc:
            status = f"failed:{getattr(exc, 'code', type(exc).__name__)}"
    else:
        status = await service.send_now(kind="newsletter", to=args.to, locale=res.locale, rendered=rendered,
                                        unsubscribe_url=one_click)
    print(json.dumps({**res.summary(), "mail": status}, ensure_ascii=False))
    return 0 if status in ("sent", "disabled") else 2


async def cmd_campaign(args) -> int:
    from app.database import async_session
    from app.services.mail import campaign
    from app.services.newsletter_personal.build import per_recipient_hook

    issue = _issue(args.issue)
    async with async_session() as db:
        report = await campaign.run(db, issue, send=args.send, include_unverified=args.include_unverified,
                                    max_per_run=args.max, per_recipient=per_recipient_hook(issue),
                                    count_personal=not args.send)
    print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
    return 0 if not report.stopped or report.stopped == "max_per_run" else 3


def main() -> int:
    p = argparse.ArgumentParser(description="Персональный выпуск рассылки Forecast Economy")
    sub = p.add_subparsers(dest="cmd", required=True)

    def who(sp, persona=True):
        g = sp.add_mutually_exclusive_group(required=True)
        g.add_argument("--user")
        if persona:
            g.add_argument("--persona")
        sp.add_argument("--no-behavior", action="store_true")
        sp.add_argument("--locale", choices=("ru", "en"))
        sp.add_argument("--personal-subject", action="store_true")
        sp.add_argument("--dormant", action="store_true")

    pr = sub.add_parser("profile")
    pr.add_argument("--user", required=True)
    pr.add_argument("--no-behavior", action="store_true")
    ex = sub.add_parser("explain")
    who(ex)
    ex.add_argument("--issue", nargs="+", required=True)
    pv = sub.add_parser("preview")
    who(pv)
    pv.add_argument("--issue", nargs="+", required=True)
    pv.add_argument("--out", required=True)
    pv.add_argument("--name")
    b = sub.add_parser("build")
    b.add_argument("--issue", nargs="+", required=True)
    b.add_argument("--persist", action="store_true")
    b.add_argument("--limit", type=int)
    b.add_argument("--behavior", action="store_true", help="учитывать поведение (иначе — по флагу)")
    au = sub.add_parser("audit", help="сверка каждого числа личных блоков с базой (ничего не пишет)")
    au.add_argument("--issue", nargs="+", required=True)
    au.add_argument("--limit", type=int)
    sub.add_parser("aggregates")
    m = sub.add_parser("metrics")
    m.add_argument("--campaign", required=True)
    st = sub.add_parser("send-test")
    who(st)
    st.add_argument("--issue", nargs="+", required=True)
    st.add_argument("--to", required=True)
    st.add_argument("--no-db", action="store_true", help="без журнала писем (стенд без миграции почты)")
    c = sub.add_parser("campaign")
    c.add_argument("--issue", nargs="+", required=True)
    c.add_argument("--send", action="store_true")
    c.add_argument("--include-unverified", action="store_true")
    c.add_argument("--max", type=int)
    args = p.parse_args()
    handlers = {"profile": cmd_profile, "explain": cmd_explain, "preview": cmd_preview, "build": cmd_build,
                "aggregates": cmd_aggregates, "audit": cmd_audit, "metrics": cmd_metrics, "send-test": cmd_send_test,
                "campaign": cmd_campaign}
    return asyncio.run(handlers[args.cmd](args))


if __name__ == "__main__":
    sys.exit(main())
