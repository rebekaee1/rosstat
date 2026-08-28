"""Тесты парсера официального графика публикаций Росстата (rosstat_plan.py)."""

from __future__ import annotations

import io
import zipfile
from datetime import date
from xml.sax.saxutils import escape

from app.services.calendar_sources.official_calendar import (
    fetch_rosstat_plan_candidates_safe,
)
from app.services.calendar_sources.rosstat_plan import (
    build_rosstat_plan_candidates,
    parse_schedule_docx,
    resolve_schedule_doc_url,
)


def _docx_bytes(document_xml: str) -> bytes:
    """Минимальный docx (zip + word/document.xml) как реальный график."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml", document_xml)
    return buf.getvalue()


def _tr(*cells: str) -> str:
    tcs = "".join(
        f"<w:tc><w:p><w:r><w:t xml:space=\"preserve\">{escape(c)}</w:t></w:r></w:p></w:tc>"
        for c in cells
    )
    return f"<w:tr>{tcs}</w:tr>"


SCHEDULE_XML = "".join([
    "<w:document><w:body><w:tbl>",
    _tr("№", "НАИМЕНОВАНИЕ ТЕМЫ", "ДАТА"),
    _tr("", "ЯНВАРЬ", ""),
    _tr("1", "Об оценке индекса потребительских цен с 1 по 5 января 2026 года", "14 января"),
    _tr("2", "О потребительских ценах на нефтепродукты", "14 января"),
    _tr("3", "Об индексе потребительских цен в декабре 2025 года", "16 января"),
    _tr("4", "О социально-экономическом положении России (декабрь 2025 года)", "30 января"),
    _tr("", "ФЕВРАЛЬ", ""),
    _tr("5", "Об индексе потребительских цен в январе 2026 года", "9 февраля"),
    _tr("6", "О просроченной задолженности по заработной плате на конец января 2026 года", "19 февраля"),
    _tr("", "АПРЕЛЬ", ""),
    _tr("7", "Об индексе цен производителей промышленных товаров в марте 2026 года", "8 апреля"),
    _tr("8", "О промышленном производстве в I квартале 2026 года", "18 апреля"),
    _tr("", "ИЮЛЬ", ""),
    _tr("9", "О валовом внутреннем продукте в I квартале 2026 года", "17 июля"),
    _tr("10", "Об индексе потребительских цен в июне 2026 года", "10 июля"),
    _tr("", "СЕНТЯБРЬ", ""),
    _tr("11", "О промышленном производстве в январе-августе 2026 года", "23 сентября"),
    "</w:tbl></w:body></w:document>",
])

SCHEDULE_DOCX = _docx_bytes(SCHEDULE_XML)

PLAN_PAGE_HTML = (
    '<div class="publication-item">'
    "<h3>График размещения срочных информаций и справок на сайте Росстата</h3>"
    '<a href="/storage/mediabank/Grafik_srochn_2026.docx">Grafik_srochn_2026.docx</a>'
    "</div>"
)

TODAY = date(2026, 8, 27)
DOC_URL = "https://rosstat.gov.ru/storage/mediabank/Grafik_srochn_2026.docx"


class TestResolveScheduleDocUrl:
    def test_extracts_docx_link(self):
        url = resolve_schedule_doc_url(PLAN_PAGE_HTML)
        assert url == DOC_URL

    def test_requires_schedule_card(self):
        html = '<a href="/storage/mediabank/Grafik_srochn_2026.docx">x</a>'
        assert resolve_schedule_doc_url(html) is None

    def test_absolute_link(self):
        html = (
            "График размещения срочных информаций "
            '<a href="https://rosstat.gov.ru/storage/mediabank/Grafik_srochn_2026.docx">d</a>'
        )
        assert resolve_schedule_doc_url(html) == DOC_URL


class TestParseScheduleDocx:
    def test_dates_and_titles(self):
        rows = parse_schedule_docx(SCHEDULE_DOCX, year=2026)
        by_date = {d: t for d, t in rows}
        assert date(2026, 1, 14) in by_date
        assert by_date[date(2026, 1, 16)] == (
            "Об индексе потребительских цен в декабре 2025 года"
        )
        assert by_date[date(2026, 7, 17)].startswith("О валовом внутреннем продукте")
        assert (date(2026, 9, 23), "О промышленном производстве в январе-августе 2026 года") in rows

    def test_month_block_switches_current_month(self):
        rows = parse_schedule_docx(SCHEDULE_DOCX, year=2026)
        months = {d.month for d, _ in rows}
        assert months == {1, 2, 4, 7, 9}

    def test_no_header_rows_in_output(self):
        rows = parse_schedule_docx(SCHEDULE_DOCX, year=2026)
        titles = [t for _, t in rows]
        assert all("НАИМЕНОВАНИЕ" not in t for t in titles)
        assert not any(t == "ЯНВАРЬ" for t in titles)


class TestBuildCandidates:
    def _build(self, months_ahead=3, today=TODAY):
        return build_rosstat_plan_candidates(
            SCHEDULE_DOCX, doc_url=DOC_URL, year=2026, today=today, months_ahead=months_ahead,
        )

    def test_window_filters_old_and_future(self):
        # Окно: [today−14, today+3 мес] → февраль/апрель/июль отпадают,
        # сентябрь 23-го — в окне (27 авг + 3 мес).
        events = self._build()
        dates = {c.scheduled_date for c in events}
        assert date(2026, 9, 23) in dates
        assert all(d >= date(2026, 8, 13) for d in dates)

    def test_cpi_maps_all_slices(self):
        events = [c for c in self._build(months_ahead=2) if c.scheduled_date == date(2026, 9, 23)]
        assert events  # сентябрьская тема — ИПП
        july = build_rosstat_plan_candidates(
            SCHEDULE_DOCX, doc_url=DOC_URL, year=2026,
            today=date(2026, 7, 1), months_ahead=1,
        )
        codes = {c.indicator_code for c in july if c.scheduled_date == date(2026, 7, 17)}
        assert codes == {"gdp-nominal", "gdp-real"}

    def test_ppi_priority_over_ipi(self):
        # «О промышленном производстве в I квартале» → ipi;
        # «Об индексе цен производителей промышленных товаров» → ppi.
        candidates = build_rosstat_plan_candidates(
            SCHEDULE_DOCX, doc_url=DOC_URL, year=2026,
            today=date(2026, 4, 1), months_ahead=1,
        )
        by_code = {c.indicator_code for c in candidates if c.scheduled_date == date(2026, 4, 8)}
        assert by_code == {"ppi"}
        ipi = {c.indicator_code for c in candidates if c.scheduled_date == date(2026, 4, 18)}
        assert ipi == {"ipi"}

    def test_provenance_fields_complete(self):
        candidates = build_rosstat_plan_candidates(
            SCHEDULE_DOCX, doc_url=DOC_URL, year=2026, today=TODAY, months_ahead=2,
        )
        assert candidates
        for c in candidates:
            assert c.date_confidence == "official_explicit"
            assert c.source == "rosstat"
            assert c.source_url == DOC_URL
            assert c.source_event_uid
            # stable_key нормализует пробелы: «август 2026» → «август-2026»
            expected_ref = (c.reference_period or "na").replace(" ", "-") if c.reference_period else "na"
            assert c.event_key == f"rosstat:plan:{c.indicator_code}:{expected_ref}:r{c.metadata['release_ordinal']}"
            assert c.metadata["schedule_doc"] == DOC_URL
            assert c.metadata["schedule_year"] == 2026
            # source_hash детерминирован и покрывает provenance-контракт
            h1, h2 = c.source_hash(), c.source_hash()
            assert h1 == h2 and len(h1) == 64

    def test_reference_period_month(self):
        candidates = build_rosstat_plan_candidates(
            SCHEDULE_DOCX, doc_url=DOC_URL, year=2026,
            today=date(2026, 2, 1), months_ahead=1,
        )
        cpi = next(c for c in candidates if c.scheduled_date == date(2026, 2, 9))
        assert cpi.reference_period == "январь 2026"

    def test_reference_period_quarter(self):
        candidates = build_rosstat_plan_candidates(
            SCHEDULE_DOCX, doc_url=DOC_URL, year=2026,
            today=date(2026, 7, 1), months_ahead=1,
        )
        gdp = next(c for c in candidates if c.indicator_code == "gdp-real")
        assert gdp.reference_period == "Q1 2026"

    def test_reference_period_month_range(self):
        # «О промышленном производстве в январе-августе 2026 года» → август 2026.
        candidates = build_rosstat_plan_candidates(
            SCHEDULE_DOCX, doc_url=DOC_URL, year=2026, today=TODAY, months_ahead=2,
        )
        ipi = next(c for c in candidates if c.indicator_code == "ipi")
        assert ipi.reference_period == "август 2026"

    def test_unmapped_topics_skipped(self):
        # Нефтепродукты и просроченная задолженность не мапятся.
        rows = parse_schedule_docx(SCHEDULE_DOCX, year=2026)
        titles = [t for _, t in rows]
        assert any("нефтепродукты" in t for t in titles)
        candidates = build_rosstat_plan_candidates(
            SCHEDULE_DOCX, doc_url=DOC_URL, year=2026,
            today=date(2026, 1, 1), months_ahead=1,
        )
        codes = {c.indicator_code for c in candidates}
        assert "wages-nominal" not in codes

    def test_cpi_weekly_estimate_excluded(self):
        candidates = build_rosstat_plan_candidates(
            SCHEDULE_DOCX, doc_url=DOC_URL, year=2026,
            today=date(2026, 1, 1), months_ahead=1,
        )
        assert all(c.scheduled_date != date(2026, 1, 14) for c in candidates)


class TestFlag:
    def test_disabled_by_default(self, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "calendar_rosstat_plan_enabled", False, raising=False)
        assert fetch_rosstat_plan_candidates_safe(today=TODAY, months_ahead=2) == []

    def test_enabled_runs_pipeline(self, monkeypatch):
        from app.config import settings
        from app.services.calendar_sources import official_calendar, rosstat_plan

        monkeypatch.setattr(settings, "calendar_rosstat_plan_enabled", True, raising=False)

        captured = {}

        def fake_fetch(*, today, months_ahead, session=None):
            captured["months_ahead"] = months_ahead
            return build_rosstat_plan_candidates(
                SCHEDULE_DOCX, doc_url=DOC_URL, year=2026, today=today, months_ahead=months_ahead,
            )

        monkeypatch.setattr(rosstat_plan, "fetch_rosstat_plan_candidates", fake_fetch)
        events = official_calendar.fetch_rosstat_plan_candidates_safe(today=TODAY, months_ahead=2)
        assert captured["months_ahead"] == 2
        assert events

    def test_source_error_returns_empty(self, monkeypatch):
        from app.config import settings
        from app.services.calendar_sources import official_calendar, rosstat_plan

        monkeypatch.setattr(settings, "calendar_rosstat_plan_enabled", True, raising=False)

        def boom(*, today, months_ahead, session=None):
            raise RuntimeError("network down")

        monkeypatch.setattr(rosstat_plan, "fetch_rosstat_plan_candidates", boom)
        assert official_calendar.fetch_rosstat_plan_candidates_safe(
            today=TODAY, months_ahead=2,
        ) == []


class TestDedupExplicitOverRule:
    def _rule(self, code, ref, scheduled):
        from app.services.calendar_sources.common import CalendarCandidate

        return CalendarCandidate(
            event_key=f"rosstat:{code}:{ref.replace(' ', '-')}",
            title="Rule title",
            event_type="data_release",
            source="rosstat",
            indicator_code=code,
            scheduled_date=scheduled,
            date_confidence="official_rule",
            reference_period=ref,
            importance=2,
            source_url="https://rosstat.gov.ru",
        )

    def test_explicit_shadows_rule_same_ref(self):
        from app.services.calendar_sources.common import CalendarCandidate
        from app.services.calendar_sources.official_calendar import (
            prefer_explicit_plan_candidates,
        )

        explicit = CalendarCandidate(
            event_key="rosstat:plan:cpi:август-2026:r1",
            title="Индекс потребительских цен (ИПЦ)",
            event_type="data_release",
            source="rosstat",
            indicator_code="cpi",
            scheduled_date=date(2026, 9, 11),
            date_confidence="official_explicit",
            reference_period="август 2026",
            importance=3,
            source_url=DOC_URL,
            source_event_uid="rosstat-plan-cpi-август 2026-r1-2026-09-11",
        )
        rule = self._rule("cpi", "август 2026", date(2026, 9, 9))
        other = self._rule("ppi", "август 2026", date(2026, 9, 16))
        kept = prefer_explicit_plan_candidates([rule, explicit, other])
        assert explicit in kept
        assert rule not in kept
        assert other in kept  # чужой ref-период не затронут

    def test_rule_without_explicit_kept(self):
        from app.services.calendar_sources.official_calendar import (
            prefer_explicit_plan_candidates,
        )

        rule = self._rule("wages-nominal", "август 2026", date(2026, 9, 9))
        assert prefer_explicit_plan_candidates([rule]) == [rule]

    def test_explicit_without_ref_does_not_shadow(self):
        # Explicit без распознанного ref-периода не должен уронить rule-строку.
        from app.services.calendar_sources.common import CalendarCandidate
        from app.services.calendar_sources.official_calendar import (
            prefer_explicit_plan_candidates,
        )

        explicit_no_ref = CalendarCandidate(
            event_key="rosstat:plan:ipi:None:r1",
            title="Индекс промышленного производства (ИПП)",
            event_type="data_release",
            source="rosstat",
            indicator_code="ipi",
            scheduled_date=date(2026, 9, 23),
            date_confidence="official_explicit",
            reference_period=None,
            importance=2,
            source_url=DOC_URL,
        )
        rule = self._rule("ipi", "август 2026", date(2026, 9, 16))
        kept = prefer_explicit_plan_candidates([rule, explicit_no_ref])
        assert rule in kept and explicit_no_ref in kept
