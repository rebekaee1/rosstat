"""Что видно о доставке писем со стороны сайта (ADR-0032, дополнение 18.11.2026):
отчёты DMARC, отказы по сервисам, DNS, журнал выпуска. Ничего не отправляется."""
import asyncio
import gzip
import io
import zipfile
from email.message import EmailMessage

from tests.test_mail import mail_env  # noqa: F401 — фикстура
from tests.test_mail_lifecycle import ARF, DSN

# Ключ DKIM селектора mail домена forecasteconomy.com на 18.11.2026 (RSA 1024).
KEY_1024 = ("v=DKIM1; k=rsa; t=s; p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDROkA9JpOOuJv5Dua6YaAP67sTfYGYMQnT9W8x55ff"
            "rKnlh7bR+XIomYsj+4pue37dupdi6rKtcZi4OC9MKFuROCTanYTRoUu63+yotEZ6w7k/Lj8VwMc+0JYg6qKGyE6tzSqgWSn/dtWuLIUr"
            "Osc/CGWIOd8doiYKux3KB+po4QIDAQAB")

DMARC_XML = b"""<?xml version="1.0" encoding="UTF-8" ?>
<feedback xmlns="urn:ietf:params:xml:ns:dmarc-2.0">
  <report_metadata><org_name>google.com</org_name><email>noreply-dmarc-support@google.com</email>
    <report_id>1</report_id><date_range><begin>1794873600</begin><end>1794959999</end></date_range></report_metadata>
  <policy_published><domain>forecasteconomy.com</domain><p>none</p></policy_published>
  <record><row><source_ip>93.77.172.69</source_ip><count>30</count>
      <policy_evaluated><disposition>none</disposition><dkim>pass</dkim><spf>pass</spf></policy_evaluated></row>
    <identifiers><header_from>forecasteconomy.com</header_from></identifiers></record>
  <record><row><source_ip>203.0.113.9</source_ip><count>2</count>
      <policy_evaluated><disposition>none</disposition><dkim>fail</dkim><spf>fail</spf></policy_evaluated></row>
    <identifiers><header_from>forecasteconomy.com</header_from></identifiers></record>
</feedback>"""


def _report_mail(payload: bytes, filename: str, ctype: str) -> bytes:
    msg = EmailMessage()
    msg["From"] = "noreply-dmarc-support@google.com"
    msg["Subject"] = "Report domain: forecasteconomy.com Submitter: google.com"
    msg.set_content("DMARC aggregate report")
    maintype, subtype = ctype.split("/")
    msg.add_attachment(payload, maintype=maintype, subtype=subtype, filename=filename)
    return msg.as_bytes()


def test_dmarc_report_gzip_and_zip():
    from app.services.mail import deliverability as dlv

    gz = _report_mail(gzip.compress(DMARC_XML), "google.com!forecasteconomy.com!1!2.xml.gz", "application/gzip")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("mail.ru!forecasteconomy.com.xml", DMARC_XML.replace(b"google.com</org_name>", b"Mail.Ru</org_name>"))
    zp = _report_mail(buf.getvalue(), "mail.ru!forecasteconomy.com.zip", "application/zip")

    kind, rep = dlv.classify(gz)
    assert kind == "dmarc" and rep.org == "google.com" and rep.messages == 32
    assert rep.records[0].dkim_aligned and rep.records[0].spf_aligned
    assert not rep.records[1].dkim_aligned
    kind2, rep2 = dlv.classify(zp)
    assert kind2 == "dmarc" and dlv.reporter_key(rep2.org) == "mail.ru"

    summary = dlv.dmarc_summary([rep, rep2], "forecasteconomy.com")
    assert summary["google.com"] == {"reports": 1, "messages": 32, "dkim_aligned": 30, "spf_aligned": 30,
                                     "dmarc_pass": 30, "not_none": 0}
    assert summary["mail.ru"]["messages"] == 32
    # отчёт о чужом домене в сводку не входит
    assert dlv.dmarc_summary([rep], "example.com") == {}


def test_dmarc_xml_refuses_entities_and_garbage():
    from app.services.mail import deliverability as dlv

    bomb = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><feedback>&a;</feedback>'
    assert dlv.parse_dmarc_xml(bomb) is None
    assert dlv.parse_dmarc_xml(b"not xml") is None
    assert dlv.parse_dmarc_xml(b"<other/>") is None
    # обычное письмо с картинкой — не отчёт
    msg = EmailMessage()
    msg["From"] = "person@example.com"
    msg.set_content("hi")
    msg.add_attachment(b"\x89PNG", maintype="image", subtype="png", filename="a.png")
    assert dlv.classify(msg.as_bytes()) == ("other", None)


def test_bounce_and_complaint_classified_without_addresses():
    from app.services.mail import deliverability as dlv

    gmail = DSN.replace(b"Reporting-MTA: dns; mx.yandex.ru\r\n\r\n",
                        b"Reporting-MTA: dns; forward105e.mail.yandex.net\r\n\r\n").replace(
        b"Status: 5.1.1\r\n", b"Status: 5.1.1\r\nRemote-MTA: dns; gmail-smtp-in.l.google.com\r\n")
    assert dlv.classify(gmail) == ("bounce", [("5.1.1", "gmail")])
    assert dlv.classify(DSN) == ("bounce", [("5.1.1", "other")])  # example.com, сервера нет
    assert dlv.classify(ARF) == ("complaint", 1)

    box = dlv.MailboxSurvey(folders={"INBOX": 3})
    box.bounces[("5.1.1", "gmail")] += 1
    box.complaints = 1
    text = dlv.format_report(None, box, {"gmail": {"sent": 32, "bounced": 1}}, "fe-weekly-01", 7)
    assert "отказ 5.1.1 (постоянный), gmail: 1" in text
    assert "отчётов DMARC нет" in text
    assert "@" not in text.replace("@forecasteconomy", "")  # адресов людей в сводке нет


def test_service_of():
    from app.services.mail.deliverability import service_of

    assert service_of("gmail-smtp-in.l.google.com") == "gmail"
    assert service_of("bk.ru") == "mailru"
    assert service_of("mx.yandex.net") == "yandex"
    assert service_of("icloud.com") == "icloud"
    assert service_of("ultradecor.com") == "other"


def test_dns_check_flags_missing_dmarc_mailbox(monkeypatch):
    """18.11.2026: rua=mailto:dmarc@… — ящика нет, сервер отвечает 550, отчёты терялись."""
    from app.services.mail import deliverability as dlv

    zone = {
        ("forecasteconomy.com", "MX"): ["10 mx.yandex.net."],
        ("forecasteconomy.com", "TXT"): ["v=spf1 redirect=_spf.yandex.net", "yandex-verification: 1"],
        ("mail._domainkey.forecasteconomy.com", "TXT"): [KEY_1024],
        ("_dmarc.forecasteconomy.com", "TXT"): ["v=DMARC1; p=none; rua=mailto:dmarc@forecasteconomy.com,mailto:x@vendor.example"],
    }
    monkeypatch.setattr(dlv, "_doh", lambda name, rtype: zone.get((name, rtype), []))
    probes = []

    def fake_probe(addr, mx, timeout=10.0):
        probes.append((addr, mx))
        return (550, "5.7.1 No such user!") if addr.startswith("dmarc@") else (250, "ok")

    monkeypatch.setattr(dlv, "rcpt_probe", fake_probe)
    res = dlv.check_dns("forecasteconomy.com")
    assert res["mx"] == ["mx.yandex.net"]
    assert res["spf"] == "v=spf1 redirect=_spf.yandex.net"
    assert res["dkim_bits"] == 1024
    assert res["dmarc_policy"] == "none"
    assert res["dmarc_rua"] == ["dmarc@forecasteconomy.com", "x@vendor.example"]
    assert res["dmarc_rua_check"]["dmarc@forecasteconomy.com"].startswith("НЕ ПРИНИМАЕТ (550")
    assert res["dmarc_rua_check"]["x@vendor.example"] == "чужой домен — не проверялся"
    assert probes == [("dmarc@forecasteconomy.com", "mx.yandex.net")]  # чужие адреса не трогаем
    text = dlv.format_report(res, None, None, None, 7)
    assert "DKIM mail: есть, ≈1024 бит" in text and "НЕ ПРИНИМАЕТ" in text


def test_dns_check_network_error_is_reported(monkeypatch):
    from app.services.mail import deliverability as dlv

    def boom(name, rtype):
        raise OSError("offline")

    monkeypatch.setattr(dlv, "_doh", boom)
    res = dlv.check_dns("forecasteconomy.com")
    assert res["error"] == "DNS не прочитан: OSError"


def test_dkim_key_bits():
    from app.services.mail.deliverability import dkim_key_bits

    assert dkim_key_bits(KEY_1024) == 1024
    assert dkim_key_bits("v=DKIM1; p=") is None or dkim_key_bits("v=DKIM1; p=") == 0
    assert dkim_key_bits("v=DKIM1; k=rsa") is None


def test_journal_by_service(mail_env):  # noqa: F811
    from app.models import MailEvent, MailMessage
    from app.services.mail import deliverability as dlv

    async def run():
        async with mail_env["session_maker"]() as db:
            rows = [
                MailMessage(kind="newsletter", campaign="fe-weekly-01", to_email="a@gmail.com", subject="s", status="sent"),
                MailMessage(kind="newsletter", campaign="fe-weekly-01", to_email="b@gmail.com", subject="s",
                            status="bounced", error="bounce:5.1.1"),
                MailMessage(kind="newsletter", campaign="fe-weekly-01", to_email="c@yandex.ru", subject="s",
                            status="failed", error="smtp_554:spam"),
                MailMessage(kind="newsletter", campaign="fe-weekly-01", to_email="d@bk.ru", subject="s", status="sent"),
                MailMessage(kind="newsletter", campaign="other", to_email="e@bk.ru", subject="s", status="sent"),
            ]
            db.add_all(rows)
            await db.flush()
            db.add(MailEvent(mail_id=rows[3].id, campaign="fe-weekly-01", kind="click", machine=False))
            db.add(MailEvent(mail_id=rows[3].id, campaign="fe-weekly-01", kind="click", machine=False))
            db.add(MailEvent(mail_id=rows[0].id, campaign="fe-weekly-01", kind="click", machine=True))
            await db.commit()
            return await dlv.journal_by_service(db, "fe-weekly-01")

    out = asyncio.run(run())
    assert out == {"gmail": {"sent": 1, "bounced": 1}, "yandex": {"spam_rejected": 1},
                   "mailru": {"sent": 1, "clicked": 1}}
