"""Серверная выгрузка таблиц (Excel/CSV) с гейтом по лимиту (ADR-0007 Phase 2).

Генерация файла перенесена с клиента на бэкенд: это (1) даёт жёсткий лимит
гостевых скачиваний, (2) снимает ~430 КБ xlsx из фронтового бандла. Трансформы
рядов (режимы графика) остаются на клиенте — сюда приходят уже готовые точки.
"""
import io
import logging
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import User
from app.security.auth import get_optional_user
from app.security import download_quota as dq

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/export", tags=["export"])

_MAX_POINTS = 100_000


class ExportPoint(BaseModel):
    date: str
    actual: float | None = None
    forecast: float | None = None


class ExportIn(BaseModel):
    format: str
    filename: str
    value_label: str = "Значение"
    points: list[ExportPoint]

    @field_validator("format")
    @classmethod
    def _fmt(cls, v: str) -> str:
        v = (v or "").lower()
        if v not in ("xlsx", "csv"):
            raise ValueError("format must be xlsx or csv")
        return v

    @field_validator("points")
    @classmethod
    def _points(cls, v: list) -> list:
        if not v:
            raise ValueError("no points")
        if len(v) > _MAX_POINTS:
            raise ValueError("too many points")
        return v


def _round(x: float | None) -> float | None:
    return None if x is None else round(float(x), 4)


def _point_year(date_str: str) -> int | None:
    """Год из ISO-даты точки ('2024-01-01', '2024', '2024-W03') — для гейта глубины."""
    head = (date_str or "").strip()[:4]
    return int(head) if head.isdigit() else None


def _limit_history(points: list[ExportPoint]) -> list[ExportPoint]:
    """Гостю отдаём только последние N лет истории; полный период — за регистрацию.

    Отсчёт от самой поздней точки набора (а не от текущей даты): прогноз уходит
    в будущее, поэтому ориентир — максимальный год среди переданных точек.
    """
    years = settings.download_anon_history_years
    if years <= 0:
        return points
    yrs = [y for p in points if (y := _point_year(p.date)) is not None]
    if not yrs:
        return points
    cutoff = max(yrs) - years
    limited = [p for p in points if (y := _point_year(p.date)) is None or y > cutoff]
    return limited or points


def _split(points: list[ExportPoint]):
    facts = [(p.date, _round(p.actual)) for p in points if p.actual is not None]
    forecasts = [
        (p.date, _round(p.forecast))
        for p in points
        if p.forecast is not None and p.actual is None
    ]
    return facts, forecasts


def _build_xlsx(facts, forecasts, value_label: str) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Факт"
    ws.append(["Дата", value_label])
    for date, val in facts:
        ws.append([date, val])
    if forecasts:
        ws2 = wb.create_sheet("Прогноз")
        ws2.append(["Дата", f"Прогноз {value_label}"])
        for date, val in forecasts:
            ws2.append([date, val])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _build_csv(facts, forecasts, value_label: str) -> bytes:
    lines = [";".join(["Дата", value_label, "Тип"])]
    for date, val in facts:
        lines.append(";".join([date, "" if val is None else f"{val:.4f}", "факт"]))
    for date, val in forecasts:
        lines.append(";".join([date, "" if val is None else f"{val:.4f}", "прогноз"]))
    return ("\ufeff" + "\n".join(lines)).encode("utf-8")


def _content_disposition(filename: str) -> str:
    ascii_fallback = "export." + (filename.rsplit(".", 1)[-1] if "." in filename else "dat")
    return f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quote(filename)}"


@router.get("/quota")
async def export_quota(
    request: Request,
    user: User | None = Depends(get_optional_user),
):
    """Сколько гостевых выгрузок осталось — для состояния кнопок UI (без инкремента).

    Авторизованный пользователь: unlimited=True. Гость: remaining из счётчика fe_dl.
    """
    if user is not None:
        return {"unlimited": True, "remaining": None, "limit": settings.download_anon_limit,
                "history_years": 0}
    dl_id = request.cookies.get(dq.DL_COOKIE)
    remaining = await dq.remaining_anon_downloads(dl_id)
    return {"unlimited": False, "remaining": remaining, "limit": settings.download_anon_limit,
            "history_years": settings.download_anon_history_years}


@router.post("/table")
async def export_table(
    body: ExportIn,
    request: Request,
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    set_cookie_id: str | None = None
    if user is None:
        dl_id = request.cookies.get(dq.DL_COOKIE)
        if not dl_id:
            dl_id = dq.new_download_id()
            set_cookie_id = dl_id
        allowed = await dq.consume_anon_download(dl_id)
        if not allowed:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "download_limit",
                    "message": "Лимит бесплатных выгрузок исчерпан. Войдите в аккаунт для безлимитного скачивания.",
                },
            )

    # Полный период истории — бонус за регистрацию: гостю обрезаем глубину.
    points = body.points if user is not None else _limit_history(body.points)
    facts, forecasts = _split(points)
    if body.format == "xlsx":
        data = _build_xlsx(facts, forecasts, body.value_label)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        data = _build_csv(facts, forecasts, body.value_label)
        media = "text/csv; charset=utf-8"

    resp = Response(content=data, media_type=media)
    resp.headers["Content-Disposition"] = _content_disposition(body.filename)
    if user is None:
        remaining = await dq.remaining_anon_downloads(set_cookie_id or request.cookies.get(dq.DL_COOKIE))
        resp.headers["X-Download-Remaining"] = str(remaining)
        resp.headers["Access-Control-Expose-Headers"] = "X-Download-Remaining"
    if set_cookie_id is not None:
        kw = {"httponly": True, "secure": settings.auth_cookie_secure, "samesite": "lax", "path": "/"}
        if settings.auth_cookie_domain:
            kw["domain"] = settings.auth_cookie_domain
        resp.set_cookie(dq.DL_COOKIE, set_cookie_id, max_age=settings.download_anon_window_seconds, **kw)
    return resp
