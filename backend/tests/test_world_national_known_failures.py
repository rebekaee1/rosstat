"""Известные отказы мировых источников (нет ключа, сервер не пускают) не красят ночную сводку (09.11.2026)."""

from app.services import world_national_ingest as w

# Тексты ошибок из живого прогона 08.11.2026 (прод).
NIGHT = {
    "au": [("au-policy-rate", "RbaStatsError: RBA GET https://www.rba.gov.au/statistics/tables/csv/f1-data.csv HTTP 403: <HTML>Access Denied")],
    "cn": [("cn-industrial-production", "NbsStatsError: NBS EasyQuery unreachable from this network (indicator=A020101)")],
    "jp": [("jp-cpi-all", "estat adapter requires RUSTATS_ESTAT_APP_ID (free appId from https://www.e-stat.go.jp/api/)")],
    "mx": [("mx-cpi-all", "BanxicoSieError: Banxico SIE requires RUSTATS_BANXICO_API_TOKEN (Bmx-Token)"),
           ("mx-policy-rate", "BanxicoSieError: Banxico SIE requires RUSTATS_BANXICO_API_TOKEN (Bmx-Token)")],
}


def test_known_failures_are_split_from_real_ones():
    failed = dict(NIGHT, us=[("us-cpi", "ValueError: Source payload identity does not match requested series")])
    real, known = w.split_failed_series(failed)
    assert real == {"us": failed["us"]}
    assert known[w.KNOWN_NOT_CONFIGURED] == {"jp": 1, "mx": 2}
    assert known[w.KNOWN_BLOCKED] == {"au": 1, "cn": 1}


def test_transient_timeout_stays_an_error():
    assert w.classify_series_error("ReadTimeout: HTTPSConnectionPool(host='api.stlouisfed.org') read timed out") == "error"


def test_known_line_is_plain_words():
    _real, known = w.split_failed_series(NIGHT)
    line = w._known_line(known)
    assert "нужен бесплатный ключ: jp 1, mx 2" in line
    assert "не пускает наш сервер: au 1, cn 1" in line
    assert w._known_line({w.KNOWN_NOT_CONFIGURED: {}, w.KNOWN_BLOCKED: {}}) == ""
