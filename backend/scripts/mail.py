"""Почта сайта из командной строки (ADR-0032). Адреса подписчиков на экран не выводятся.

Запуск в контейнере backend (на сервере) или локально с PYTHONPATH=backend:

    python /app/scripts/mail.py check                  # настройки (без секретов) + вход на SMTP, без письма
    python /app/scripts/mail.py test --to rebeka.ee@yandex.ru [--locale ru|en|all] [--no-db]
                                                       # все виды писем на проверочный адрес
    python /app/scripts/mail.py render sample --out /tmp/mail-preview   # HTML и .eml без отправки
    python /app/scripts/mail.py render issue.json --out /tmp/mail-preview
    python /app/scripts/mail.py audience               # сколько подписчиков, с каким адресом и языком
    python /app/scripts/mail.py campaign issue.json --test-to rebeka.ee@yandex.ru   # выпуск на проверочный адрес
    python /app/scripts/mail.py campaign issue.json    # сухой прогон: кому ушло бы, ничего не отправляет
    python /app/scripts/mail.py campaign issue.json --send [--include-unverified] [--max 50]
                                                       # ЛЮДЯМ; только по команде владельца и при
                                                       # RUSTATS_MAIL_ALLOW_ALL_RECIPIENTS=true

Проверочные письма уходят только на адреса из RUSTATS_MAIL_ALLOWLIST.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import smtplib
import ssl
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve()
for candidate in ("/app", str(HERE.parents[1])):
    if os.path.isdir(os.path.join(candidate, "app")) and candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.config import settings  # noqa: E402
from app.services.mail import campaign, service, tokens, transport  # noqa: E402
from app.services.mail.account import reset_mail, verify_mail  # noqa: E402
from app.services.mail.templates import render_digest, sample_digest  # noqa: E402

DUMMY_USER = "00000000-0000-0000-0000-000000000000"


def _yes(v) -> str:
    return "задан" if v else "НЕ ЗАДАН"


def cmd_check(_args) -> int:
    print(f"почта включена (MAIL_ENABLED):      {settings.mail_enabled}")
    print(f"SMTP:                               {settings.mail_smtp_host}:{settings.mail_smtp_port} ({settings.mail_smtp_security})")
    print(f"ящик (MAIL_SMTP_USER):              {settings.mail_smtp_user or 'НЕ ЗАДАН'}")
    print(f"пароль (MAIL_SMTP_PASSWORD):        {_yes(settings.mail_smtp_password)}")
    print(f"отправитель:                        {settings.mail_from_name} <{transport.from_address() or '—'}>")
    print(f"ответы (Reply-To):                  {settings.mail_reply_to or '—'}")
    print(f"секрет ссылок (MAIL_TOKEN_SECRET):  {_yes(len(settings.mail_token_secret or '') >= 16)}")
    print(f"только список допуска:              {not settings.mail_allow_all_recipients} -> {sorted(service.allowlist())}")
    print(f"ссылки ru / en:                     {service.site_origin('ru')} / {service.site_origin('en')}")
    if settings.mail_smtp_user and transport.from_address() != settings.mail_smtp_user:
        print("ВНИМАНИЕ: отправитель не совпадает с ящиком входа — Яндекс 360 такое письмо отклонит")
    if not (settings.mail_smtp_user and settings.mail_smtp_password):
        return 1
    try:
        ctx = ssl.create_default_context()
        if settings.mail_smtp_security == "starttls":
            with smtplib.SMTP(settings.mail_smtp_host, settings.mail_smtp_port, timeout=20) as c:
                c.starttls(context=ctx)
                c.login(settings.mail_smtp_user, settings.mail_smtp_password)
        else:
            with smtplib.SMTP_SSL(settings.mail_smtp_host, settings.mail_smtp_port, timeout=20, context=ctx) as c:
                c.login(settings.mail_smtp_user, settings.mail_smtp_password)
        print("вход на SMTP:                       успешно (письмо не отправлялось)")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"вход на SMTP:                       ОШИБКА {type(exc).__name__} {getattr(exc, 'smtp_code', '')}")
        return 2


def _test_mails(locale: str):
    site = service.site_origin(locale) + "/"
    page, one_click = campaign.unsubscribe_links(DUMMY_USER, locale)
    yield "verify_email", verify_mail(DUMMY_USER, "test@example.com", locale), None
    yield "password_reset", reset_mail(DUMMY_USER, "test-hash", locale), None
    yield "newsletter", render_digest(sample_digest(locale, site), locale, site_url=site, unsubscribe_url=page,
                                      manage_url=service.site_link(locale, "/account")), one_click


async def cmd_test(args) -> int:
    if not service.recipient_allowed(args.to):
        print("адрес не в списке допуска (RUSTATS_MAIL_ALLOWLIST) — не отправляю")
        return 1
    if not settings.mail_enabled and not args.no_db:
        print("RUSTATS_MAIL_ENABLED=false: письма лишь запишутся в журнал со статусом disabled")
    locales = ("ru", "en") if args.locale == "all" else (args.locale,)
    code = 0
    for loc in locales:
        for kind, rendered, one_click in _test_mails(loc):
            rendered.subject = f"[test] {rendered.subject}"
            if args.no_db:
                try:
                    mid = await transport.send(transport.OutgoingMail(
                        to=args.to, subject=rendered.subject, html=rendered.html, text=rendered.text,
                        kind=kind, unsubscribe_url=one_click, campaign="test"))
                    print(f"{loc} {kind}: sent {mid}")
                except (transport.SendError, transport.MailConfigError) as exc:
                    print(f"{loc} {kind}: ОШИБКА {getattr(exc, 'code', type(exc).__name__)}")
                    code = 2
            else:
                status = await service.send_now(kind=kind, to=args.to, locale=loc, rendered=rendered,
                                                unsubscribe_url=one_click)
                print(f"{loc} {kind}: {status}")
                code = code or (0 if status in ("sent", "disabled") else 2)
    return code


def cmd_render(args) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.source == "sample":
        items = []
        for loc in ("ru", "en"):
            for kind, rendered, one_click in _test_mails(loc):
                items.append((f"{loc}-{kind}", kind, rendered, one_click))
    else:
        issue = campaign.load_issue(args.source)
        items = []
        for loc in issue.by_locale:
            rendered, one_click = campaign.render_for(issue, loc, DUMMY_USER)
            items.append((f"{issue.key}-{loc}", "newsletter", rendered, one_click))
    for name, kind, rendered, one_click in items:
        (out / f"{name}.html").write_text(rendered.html, encoding="utf-8")
        (out / f"{name}.txt").write_text(f"Subject: {rendered.subject}\n\n{rendered.text}", encoding="utf-8")
        msg = transport.build_message(transport.OutgoingMail(
            to="preview@example.com", subject=rendered.subject, html=rendered.html, text=rendered.text,
            kind=kind, unsubscribe_url=one_click, campaign="preview"))
        (out / f"{name}.eml").write_bytes(bytes(msg))
        print(out / f"{name}.html")
    return 0


async def cmd_audience(_args) -> int:
    from app.database import async_session
    from app.services.mail import audience

    async with async_session() as db:
        recs, missing = await audience.subscribers(db)
    c = Counter((r.locale, "подтверждён" if r.verified else "не подтверждён") for r in recs)
    print(f"подписчиков с адресом: {len(recs)}; без адреса (вход через VK без почты): {missing}")
    for (loc, ver), n in sorted(c.items()):
        print(f"  {loc} · {ver}: {n}")
    domains = Counter(r.email.rsplit("@", 1)[-1] for r in recs)
    print("почтовые сервисы:", ", ".join(f"{d} {n}" for d, n in domains.most_common(8)))
    return 0


async def cmd_campaign(args) -> int:
    issue = campaign.load_issue(args.file)
    if args.test_to:
        res = await campaign.send_test(issue, args.test_to)
        print(json.dumps(res, ensure_ascii=False))
        return 0 if all(v in ("sent", "disabled") for v in res.values()) else 2
    from app.database import async_session

    async with async_session() as db:
        report = await campaign.run(db, issue, send=args.send, include_unverified=args.include_unverified,
                                    max_per_run=args.max)
    print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
    return 0 if not report.stopped or report.stopped == "max_per_run" else 3


def main() -> int:
    p = argparse.ArgumentParser(description="Почта Forecast Economy")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    t = sub.add_parser("test")
    t.add_argument("--to", required=True)
    t.add_argument("--locale", choices=("ru", "en", "all"), default="all")
    t.add_argument("--no-db", action="store_true", help="без журнала: прямая отправка (локальная проверка)")
    r = sub.add_parser("render")
    r.add_argument("source", help="sample или путь к JSON выпуска")
    r.add_argument("--out", required=True)
    sub.add_parser("audience")
    c = sub.add_parser("campaign")
    c.add_argument("file")
    c.add_argument("--test-to")
    c.add_argument("--send", action="store_true")
    c.add_argument("--include-unverified", action="store_true")
    c.add_argument("--max", type=int)
    args = p.parse_args()
    try:
        tokens._secret()
    except tokens.TokenSecretMissing:
        if args.cmd not in ("check",):
            print("RUSTATS_MAIL_TOKEN_SECRET не задан (нужен для ссылок в письмах)")
            return 1
    if args.cmd == "check":
        return cmd_check(args)
    if args.cmd == "render":
        return cmd_render(args)
    return asyncio.run({"test": cmd_test, "audience": cmd_audience, "campaign": cmd_campaign}[args.cmd](args))


if __name__ == "__main__":
    sys.exit(main())
