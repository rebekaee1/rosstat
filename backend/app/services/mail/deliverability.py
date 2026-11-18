"""Что видно о доставке писем со стороны сайта (ADR-0032, дополнение 18.11.2026).

Попадание во «Входящие» или в «Спам» отправитель не видит: почта получателя принимает письмо
по SMTP и сама решает, в какую папку его положить. Со стороны сайта видны четыре вещи, и этот
модуль собирает их в одну сводку без адресов людей:

* **DNS домена** — SPF, DKIM (ключ селектора и его длина), DMARC (политика и адреса отчётов) и
  проверка, что адрес отчётов DMARC принимает почту (только RCPT, письмо не отправляется). До
  18.11.2026 отчёты шли на несуществующий `dmarc@` и терялись;
* **ящик отправителя** (IMAP, только чтение, как `bounces.py`): отказы (RFC 3464) по классам и
  сервисам получателя, жалобы (ARF) и **агрегатные отчёты DMARC** — каждый крупный сервис
  (Google, Mail.ru, Яндекс) раз в сутки пишет, сколько писем от домена он видел и прошли ли они
  DKIM и SPF с совпадением домена;
* **журнал отправки** `mail_outbox` по сервисам получателя: принято, отказ, «похоже на спам»;
* **переходы** из писем по сервисам (`mail_events`, ADR-0034).

Чего сводка не знает и не выдаёт за знание: папку письма у получателя. Её показывают только
проверочные ящики (раздел «Проверка доставки» в docs/newsletter-playbook.md) и кабинеты
отправителя при достаточном объёме (Google Postmaster Tools; Яндекс «Почтовый офис» закрыт
в сентябре 2020 года).
"""
from __future__ import annotations

import base64
import email
import gzip
import imaplib
import io
import re
import smtplib
import ssl
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.message import Message
from xml.etree import ElementTree

from app.config import settings
from app.services.mail import bounces

# Отчёт DMARC в архиве обычно меньше 100 КБ; больше — не разбираем (защита от «архивной бомбы»).
MAX_REPORT_BYTES = 5 * 1024 * 1024
DKIM_SELECTOR = "mail"  # селектор ключа Яндекс 360 (admin.yandex.ru → Домены → DKIM)

_REPORTER_ALIASES = (
    ("google", "google.com"),
    ("mail.ru", "mail.ru"),
    ("vk", "mail.ru"),
    ("yandex", "yandex.ru"),
    ("microsoft", "microsoft.com"),
    ("outlook", "microsoft.com"),
    ("yahoo", "yahoo.com"),
)


# ---------------------------------------------------------------------------------------------
# Разбор писем ящика отправителя
# ---------------------------------------------------------------------------------------------

@dataclass
class DmarcRecord:
    source_ip: str
    count: int
    disposition: str
    dkim_aligned: bool
    spf_aligned: bool
    header_from: str


@dataclass
class DmarcReport:
    org: str
    begin: datetime | None
    end: datetime | None
    policy_domain: str
    records: list[DmarcRecord] = field(default_factory=list)

    @property
    def messages(self) -> int:
        return sum(r.count for r in self.records)


def reporter_key(org: str) -> str:
    """Имя сервиса из org_name отчёта: «google.com», «Mail.Ru» → «mail.ru» и т. п."""
    low = (org or "").lower()
    for needle, key in _REPORTER_ALIASES:
        if needle in low:
            return key
    return low or "—"


def _ts(value: str | None) -> datetime | None:
    try:
        return datetime.fromtimestamp(int((value or "").strip()), tz=timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _text(node, path: str) -> str:
    found = node.find(path) if node is not None else None
    return (found.text or "").strip() if found is not None and found.text else ""


def parse_dmarc_xml(xml: bytes) -> DmarcReport | None:
    """Агрегатный отчёт DMARC (RFC 7489, приложение C). Пространство имён не важно."""
    if not xml or len(xml) > MAX_REPORT_BYTES or b"<!ENTITY" in xml or b"<!DOCTYPE" in xml:
        return None
    # Внешние сущности и DOCTYPE отброшены выше: ElementTree их не загружает, но «смех миллиарда»
    # через внутренние сущности разбирать незачем — в настоящих отчётах их нет.
    xml = re.sub(rb'\sxmlns(:\w+)?="[^"]*"', b"", xml)
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError:
        return None
    if root.tag.split("}")[-1] != "feedback":
        return None
    meta = root.find("report_metadata")
    report = DmarcReport(
        org=_text(meta, "org_name"),
        begin=_ts(_text(meta, "date_range/begin")),
        end=_ts(_text(meta, "date_range/end")),
        policy_domain=_text(root, "policy_published/domain").lower(),
    )
    for rec in root.findall("record"):
        try:
            count = int(_text(rec, "row/count") or 0)
        except ValueError:
            count = 0
        report.records.append(DmarcRecord(
            source_ip=_text(rec, "row/source_ip"),
            count=count,
            disposition=_text(rec, "row/policy_evaluated/disposition").lower() or "none",
            dkim_aligned=_text(rec, "row/policy_evaluated/dkim").lower() == "pass",
            spf_aligned=_text(rec, "row/policy_evaluated/spf").lower() == "pass",
            header_from=_text(rec, "identifiers/header_from").lower(),
        ))
    return report


def _unpack(data: bytes, name: str, ctype: str) -> bytes | None:
    name, ctype = (name or "").lower(), (ctype or "").lower()
    try:
        if name.endswith(".zip") or ctype in ("application/zip", "application/x-zip-compressed"):
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                members = [m for m in z.infolist() if m.file_size <= MAX_REPORT_BYTES]
                return z.read(members[0]) if members else None
        if name.endswith((".gz", ".gzip")) or "gzip" in ctype:
            with gzip.GzipFile(fileobj=io.BytesIO(data)) as g:
                out = g.read(MAX_REPORT_BYTES + 1)
            return out if len(out) <= MAX_REPORT_BYTES else None
        if name.endswith(".xml") or ctype in ("text/xml", "application/xml"):
            return data
    except (zipfile.BadZipFile, OSError, EOFError):
        return None
    return None


def parse_dmarc_message(raw: bytes) -> DmarcReport | None:
    """Письмо с агрегатным отчётом DMARC → отчёт; любое другое письмо → None."""
    msg = email.message_from_bytes(raw)
    for part in msg.walk():
        if part.is_multipart():
            continue
        name, ctype = part.get_filename() or "", part.get_content_type()
        if not (name or ctype in ("application/zip", "application/gzip", "application/x-gzip",
                                  "application/xml", "text/xml")):
            continue
        xml = _unpack(part.get_payload(decode=True) or b"", name, ctype)
        report = parse_dmarc_xml(xml) if xml else None
        if report is not None:
            return report
    return None


def _remote_service(msg: Message) -> str:
    """Сервис получателя из отчёта о недоставке (Remote-MTA или домен адреса), без адреса."""
    for part in msg.walk():
        if part.get_content_type() != "message/delivery-status":
            continue
        payload = part.get_payload()
        text = "\n\n".join(p.as_string() for p in payload) if isinstance(payload, list) else str(payload)
        for line in text.splitlines():
            low = line.lower()
            if low.startswith("remote-mta:"):
                return service_of(low.split(";")[-1].strip())
        for line in text.splitlines():
            if line.lower().startswith("final-recipient:"):
                return service_of(line.split("@")[-1].strip())
    return "—"


def service_of(host_or_domain: str) -> str:
    """Почтовый сервис по домену адреса или имени сервера: gmail / mailru / yandex / … ."""
    h = (host_or_domain or "").lower().strip(" .>")
    if h.endswith(("gmail.com", "google.com", "googlemail.com")):
        return "gmail"
    if h.endswith(("mail.ru", "bk.ru", "list.ru", "inbox.ru", "internet.ru")):
        return "mailru"
    if h.endswith(("yandex.ru", "yandex.net", "ya.ru", "yandex.com")):
        return "yandex"
    if h.endswith(("icloud.com", "me.com", "apple.com")):
        return "icloud"
    if h.endswith(("outlook.com", "hotmail.com", "live.com", "protection.outlook.com")):
        return "outlook"
    return "other"


@dataclass
class MailboxSurvey:
    folders: dict[str, int] = field(default_factory=dict)  # папка → писем за период
    bounces: Counter = field(default_factory=Counter)      # («5.1.1», «gmail») → число
    complaints: int = 0
    dmarc: list[DmarcReport] = field(default_factory=list)
    other: int = 0                                         # письма людей и служб — не разбираются
    error: str | None = None


def classify(raw: bytes) -> tuple[str, object]:
    """Одно письмо ящика: («bounce», [(статус, сервис)…]) | («complaint», n) | («dmarc», отчёт) | («other», None)."""
    msg = email.message_from_bytes(raw)
    if msg.get_content_type() == "multipart/report":
        events = bounces.parse_report(raw)
        if events and all(e.complaint for e in events):
            return "complaint", len(events)
        if events:
            svc = _remote_service(msg)
            return "bounce", [(e.status, svc) for e in events if not e.complaint]
    report = parse_dmarc_message(raw)
    if report is not None:
        return "dmarc", report
    return "other", None


def _junk_folder(imap: imaplib.IMAP4) -> str | None:
    typ, data = imap.list()
    for line in data or []:
        s = line.decode("utf-8", "replace") if isinstance(line, bytes) else str(line)
        if "\\Junk" in s or "\\Spam" in s:
            m = re.search(r'"([^"]+)"\s*$|(\S+)\s*$', s)
            return (m.group(1) or m.group(2)) if m else None
    return None


def survey_mailbox(days: int = 7) -> MailboxSurvey:
    """Ящик отправителя за `days` суток: «Входящие» и «Спам», только чтение (EXAMINE, BODY.PEEK)."""
    out = MailboxSurvey()
    if not (settings.mail_smtp_user and settings.mail_smtp_password):
        out.error = "нет ящика: RUSTATS_MAIL_SMTP_USER / RUSTATS_MAIL_SMTP_PASSWORD"
        return out
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%d-%b-%Y")
    try:
        ctx = ssl.create_default_context()
        with imaplib.IMAP4_SSL(settings.mail_imap_host, int(settings.mail_imap_port), ssl_context=ctx) as imap:
            imap.login(settings.mail_smtp_user, settings.mail_smtp_password)
            folders = ["INBOX"]
            junk = _junk_folder(imap)
            if junk and junk.upper() != "INBOX":
                folders.append(junk)
            for folder in folders:
                typ, _ = imap.select(f'"{folder}"', readonly=True)
                if typ != "OK":
                    continue
                typ, data = imap.uid("SEARCH", None, f"SINCE {since}")
                uids = (data[0] or b"").split() if typ == "OK" else []
                out.folders[folder] = len(uids)
                for uid in uids[-500:]:
                    typ, parts = imap.uid("FETCH", uid, "(BODY.PEEK[])")
                    if typ != "OK" or not parts or not isinstance(parts[0], tuple):
                        continue
                    kind, value = classify(parts[0][1])
                    if kind == "bounce":
                        for status, svc in value:  # type: ignore[union-attr]
                            out.bounces[(status, svc)] += 1
                    elif kind == "complaint":
                        out.complaints += int(value)  # type: ignore[arg-type]
                    elif kind == "dmarc":
                        out.dmarc.append(value)  # type: ignore[arg-type]
                    else:
                        out.other += 1
    except Exception as exc:  # noqa: BLE001 — сводка не падает из-за ящика
        out.error = f"ящик не прочитан: {type(exc).__name__}"
    return out


def dmarc_summary(reports: list[DmarcReport], domain: str) -> dict[str, dict[str, int]]:
    """Сервис → писем, прошли DKIM с совпадением домена, SPF с совпадением, DMARC (хоть одно), не «none»."""
    agg: dict[str, dict[str, int]] = defaultdict(lambda: {"reports": 0, "messages": 0, "dkim_aligned": 0,
                                                          "spf_aligned": 0, "dmarc_pass": 0, "not_none": 0})
    for rep in reports:
        if rep.policy_domain and rep.policy_domain != domain:
            continue
        row = agg[reporter_key(rep.org)]
        row["reports"] += 1
        for r in rep.records:
            row["messages"] += r.count
            row["dkim_aligned"] += r.count if r.dkim_aligned else 0
            row["spf_aligned"] += r.count if r.spf_aligned else 0
            row["dmarc_pass"] += r.count if (r.dkim_aligned or r.spf_aligned) else 0
            row["not_none"] += r.count if r.disposition != "none" else 0
    return dict(agg)


# ---------------------------------------------------------------------------------------------
# DNS домена
# ---------------------------------------------------------------------------------------------

def _doh(name: str, rtype: str) -> list[str]:
    """Запрос DNS через DNS-over-HTTPS (в контейнере нет dnspython). Пустой список — записи нет."""
    import httpx

    r = httpx.get("https://dns.google/resolve", params={"name": name, "type": rtype}, timeout=8.0)
    r.raise_for_status()
    answers = r.json().get("Answer") or []
    want = {"TXT": 16, "MX": 15}.get(rtype)
    out = []
    for a in answers:
        if want and a.get("type") != want:
            continue
        data = str(a.get("data") or "")
        if rtype == "TXT":
            data = "".join(re.findall(r'"((?:[^"\\]|\\.)*)"', data)) or data.strip('"')
        out.append(data)
    return out


def dkim_key_bits(record: str) -> int | None:
    """Примерная длина ключа DKIM по длине DER открытого ключа (162 Б ≈ 1024, 294 Б ≈ 2048)."""
    m = re.search(r"(?:^|;)\s*p=([A-Za-z0-9+/=\s]+)", record or "")
    if not m:
        return None
    try:
        der = base64.b64decode(re.sub(r"\s", "", m.group(1)))
    except (ValueError, TypeError):
        return None
    n = len(der)
    if n == 0:
        return 0  # ключ отозван
    return 1024 if n < 200 else 2048 if n < 330 else 4096 if n < 600 else n * 8


def parse_dmarc_record(record: str) -> dict[str, str]:
    return {k.strip().lower(): v.strip() for k, _, v in (p.partition("=") for p in record.split(";")) if k.strip()}


def rcpt_probe(address: str, mx_host: str, timeout: float = 10.0) -> tuple[int, str]:
    """Принимает ли сервер адрес: EHLO → MAIL FROM:<> → RCPT TO → RSET. Письмо не отправляется."""
    with smtplib.SMTP(mx_host, 25, timeout=timeout) as s:
        s.ehlo("forecasteconomy.com")
        s.mail("")
        code, text = s.rcpt(address)
        s.rset()
    return code, text.decode("utf-8", "replace")[:120] if isinstance(text, bytes) else str(text)[:120]


def check_dns(domain: str, *, probe_rua: bool = True) -> dict[str, object]:
    """SPF, DKIM, DMARC и адрес отчётов DMARC. Ошибка сети → поле `error`, остальное что успели."""
    res: dict[str, object] = {"domain": domain}
    try:
        mx = sorted(_doh(domain, "MX"), key=lambda v: int(v.split()[0]) if v.split()[0].isdigit() else 99)
        res["mx"] = [v.split()[-1].rstrip(".") for v in mx]
        txt = _doh(domain, "TXT")
        spf = [t for t in txt if t.lower().startswith("v=spf1")]
        res["spf"] = spf[0] if len(spf) == 1 else (spf or None)
        dkim = [t for t in _doh(f"{DKIM_SELECTOR}._domainkey.{domain}", "TXT") if "p=" in t]
        res["dkim_selector"] = DKIM_SELECTOR
        res["dkim_bits"] = dkim_key_bits(dkim[0]) if dkim else None
        dmarc = [t for t in _doh(f"_dmarc.{domain}", "TXT") if t.lower().startswith("v=dmarc1")]
        res["dmarc"] = dmarc[0] if dmarc else None
    except Exception as exc:  # noqa: BLE001
        res["error"] = f"DNS не прочитан: {type(exc).__name__}"
        return res
    if res.get("dmarc"):
        tags = parse_dmarc_record(str(res["dmarc"]))
        res["dmarc_policy"] = tags.get("p")
        rua = [u.strip()[len("mailto:"):].split("!")[0] for u in tags.get("rua", "").split(",")
               if u.strip().lower().startswith("mailto:")]
        res["dmarc_rua"] = rua
        if probe_rua:
            checks = {}
            for addr in rua:
                if addr.lower().endswith("@" + domain) and res.get("mx"):
                    try:
                        code, text = rcpt_probe(addr, res["mx"][0])  # type: ignore[index]
                        checks[addr] = "принимает" if 200 <= code < 300 else f"НЕ ПРИНИМАЕТ ({code} {text})"
                    except Exception as exc:  # noqa: BLE001 — порт 25 бывает закрыт
                        checks[addr] = f"не проверено ({type(exc).__name__})"
                else:
                    checks[addr] = "чужой домен — не проверялся"
            res["dmarc_rua_check"] = checks
    return res


# ---------------------------------------------------------------------------------------------
# Журнал отправки и переходы
# ---------------------------------------------------------------------------------------------

async def journal_by_service(db, campaign_key: str) -> dict[str, dict[str, int]]:
    """Сервис получателя → статусы писем выпуска и число писем с переходом (без адресов)."""
    from sqlalchemy import distinct, func, select

    from app.models import MailEvent, MailMessage

    out: dict[str, dict[str, int]] = defaultdict(Counter)
    rows = (await db.execute(
        select(MailMessage.to_email, MailMessage.status, MailMessage.error)
        .where(MailMessage.campaign == campaign_key))).all()
    for to_email, status, error in rows:
        svc = service_of(to_email.split("@")[-1])
        key = "spam_rejected" if (error or "").endswith(":spam") else status
        out[svc][key] += 1
    clicked = (await db.execute(
        select(MailMessage.to_email, func.count(distinct(MailEvent.mail_id)))
        .join(MailEvent, MailEvent.mail_id == MailMessage.id)
        .where(MailMessage.campaign == campaign_key, MailEvent.kind == "click", MailEvent.machine.is_(False))
        .group_by(MailMessage.to_email))).all()
    for to_email, _n in clicked:
        out[service_of(to_email.split("@")[-1])]["clicked"] += 1
    return {k: dict(v) for k, v in out.items()}


# ---------------------------------------------------------------------------------------------
# Текст сводки
# ---------------------------------------------------------------------------------------------

def _pct(part: int, whole: int) -> str:
    return f"{round(100 * part / whole)} %" if whole else "—"


def format_report(dns: dict | None, box: MailboxSurvey | None, journal: dict | None,
                  campaign_key: str | None, days: int) -> str:
    lines: list[str] = []
    if dns is not None:
        lines.append(f"DNS {dns.get('domain')}")
        if dns.get("error"):
            lines.append(f"  {dns['error']}")
        else:
            lines.append(f"  MX: {', '.join(dns.get('mx') or []) or 'НЕТ'}")
            spf = dns.get("spf")
            lines.append(f"  SPF: {spf if isinstance(spf, str) else ('НЕТ' if not spf else 'НЕСКОЛЬКО ЗАПИСЕЙ — ошибка')}")
            bits = dns.get("dkim_bits")
            lines.append(f"  DKIM {dns.get('dkim_selector')}: " + ("НЕТ" if bits is None else "ключ отозван" if bits == 0
                                                                   else f"есть, ≈{bits} бит"))
            lines.append(f"  DMARC: {dns.get('dmarc') or 'НЕТ'}")
            for addr, verdict in (dns.get("dmarc_rua_check") or {}).items():
                lines.append(f"  адрес отчётов DMARC {addr}: {verdict}")
    if box is not None:
        lines.append(f"Ящик отправителя за {days} сут. (только чтение)")
        if box.error:
            lines.append(f"  {box.error}")
        else:
            lines.append("  папки: " + ", ".join(f"{k} {v}" for k, v in box.folders.items()))
            if box.bounces:
                for (status, svc), n in sorted(box.bounces.items()):
                    kind = "постоянный" if status.startswith("5") else "временный"
                    lines.append(f"  отказ {status} ({kind}), {svc}: {n}")
            else:
                lines.append("  отказов нет")
            lines.append(f"  жалоб «это спам» (ARF): {box.complaints}")
            summary = dmarc_summary(box.dmarc, str((dns or {}).get("domain") or "forecasteconomy.com"))
            if summary:
                for svc, row in sorted(summary.items()):
                    m = row["messages"]
                    lines.append(f"  DMARC {svc}: отчётов {row['reports']}, писем {m}, проверку прошли "
                                 f"{_pct(row['dmarc_pass'], m)} (DKIM {_pct(row['dkim_aligned'], m)}, "
                                 f"SPF {_pct(row['spf_aligned'], m)}), карантин/отказ {row['not_none']}")
            else:
                lines.append("  отчётов DMARC нет")
            lines.append(f"  прочих писем (люди, службы; не разбираются): {box.other}")
    if journal is not None:
        lines.append(f"Журнал выпуска {campaign_key or '—'} по сервисам получателя")
        if not journal:
            lines.append("  писем нет")
        for svc, row in sorted(journal.items(), key=lambda kv: -sum(kv[1].values())):
            parts = ", ".join(f"{k} {v}" for k, v in sorted(row.items()))
            lines.append(f"  {svc}: {parts}")
    lines.append("Папку письма у получателя («Входящие» или «Спам») отсюда не видно: "
                 "нужны проверочные ящики (docs/newsletter-playbook.md, «Проверка доставки»).")
    return "\n".join(lines)
