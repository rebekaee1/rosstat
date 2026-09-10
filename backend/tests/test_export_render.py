"""Export worker admission and cancellation must protect the public event loop."""
import asyncio
import threading

import anyio
import pytest
from fastapi import HTTPException

from app.services import export_render
from app.services.locale import set_locale, reset_locale, get_locale


def test_export_thread_preserves_locale_and_keeps_loop_responsive(monkeypatch):
    async def scenario():
        monkeypatch.setattr(export_render, '_LIMITER', anyio.CapacityLimiter(1))
        monkeypatch.setattr(export_render, '_SLOTS', threading.BoundedSemaphore(1))
        started, release = threading.Event(), threading.Event()
        loop_thread = threading.get_ident()
        def build():
            started.set()
            assert release.wait(3)
            assert threading.get_ident() != loop_thread
            return get_locale().encode()
        token = set_locale('en')
        try:
            job = asyncio.create_task(export_render.render_export_async(build))
            for _ in range(100):
                if started.is_set():break
                await asyncio.sleep(.005)
            assert started.is_set()  # loop progressed while builder waits in thread
            with pytest.raises(HTTPException) as error:
                await export_render.render_export_async(build)
            assert error.value.status_code == 503
            job.cancel()
            with pytest.raises(asyncio.CancelledError):await job
            with pytest.raises(HTTPException):await export_render.render_export_async(build)
            release.set()
            for _ in range(100):
                await asyncio.sleep(.005)
                try:
                    assert await export_render.render_export_async(lambda: get_locale().encode()) == b'en'
                    break
                except HTTPException:continue
            else:pytest.fail('slot was not returned after worker completion')
        finally:
            release.set()
            reset_locale(token)
    asyncio.run(scenario())


def test_builder_error_returns_admission(monkeypatch):
    async def scenario():
        monkeypatch.setattr(export_render, '_LIMITER', anyio.CapacityLimiter(1))
        monkeypatch.setattr(export_render, '_SLOTS', threading.BoundedSemaphore(1))
        def fail():raise ValueError('builder failed')
        with pytest.raises(ValueError):await export_render.render_export_async(fail)
        assert await export_render.render_export_async(lambda: b'ok') == b'ok'
    asyncio.run(scenario())


def test_export_route_offloads_the_complete_builder(auth_client, monkeypatch):
    from app.api import export
    from app.config import settings
    monkeypatch.setattr(settings, 'download_anon_limit', 1)
    seen = []
    async def worker(builder, body, authenticated, *, admission):
        seen.append((builder, body.format, authenticated))
        return b'worker-result'
    monkeypatch.setattr(export, 'render_export_async', worker)
    response = auth_client.post('/api/v1/export/table', json={
        'format': 'csv', 'filename': 'result.csv',
        'points': [{'date': '2026-01-01', 'actual': 1}],
    })
    assert response.status_code == 200
    assert response.content == b'worker-result'
    assert seen == [(export._build_table, 'csv', False)]


def test_busy_renderer_does_not_consume_download_quota(auth_client, monkeypatch):
    from app.config import settings
    from app.security import download_quota as dq
    monkeypatch.setattr(settings, 'download_anon_limit', 1)
    slots = threading.BoundedSemaphore(1)
    monkeypatch.setattr(export_render, '_SLOTS', slots)
    consumed = []
    original_consume = dq.consume_anon_download
    async def consume(download_id):
        consumed.append(download_id)
        return await original_consume(download_id)
    monkeypatch.setattr(dq, 'consume_anon_download', consume)
    body = {'format': 'csv', 'filename': 'result.csv',
            'points': [{'date': '2026-01-01', 'actual': 1}]}
    assert slots.acquire(blocking=False)
    try:
        for _ in range(2):
            response = auth_client.post('/api/v1/export/table', json=body)
            assert response.status_code == 503
            assert response.headers['retry-after'] == '5'
        assert consumed == []
    finally:
        slots.release()
    assert auth_client.post('/api/v1/export/table', json=body).status_code == 200
    assert len(consumed) == 1
    assert auth_client.post('/api/v1/export/table', json=body).status_code == 403
    # Rejected quota checks also release their admission reservation.
    assert slots.acquire(blocking=False)
    slots.release()
