"""Bounded file construction off the ASGI loop, preserving request locale.

One active builder and three queued jobs per worker process. A disconnected
request must not release admission while its thread still holds a workbook.
"""
from __future__ import annotations

import asyncio
import threading
from functools import partial

import anyio
from fastapi import HTTPException

_LIMITER = anyio.CapacityLimiter(1)
_SLOTS = threading.BoundedSemaphore(4)


class ExportAdmission:
    """A slot reserved before quota consumption, then transferred to a worker."""

    def __init__(self):
        self.slots = _SLOTS
        self.transferred = False
        self.released = False
        if not self.slots.acquire(blocking=False):
            raise HTTPException(status_code=503, detail="Export renderer busy; retry shortly",
                                headers={"Retry-After": "5"})

    def release(self):
        if not self.released:
            self.released = True
            self.slots.release()


async def reserve_export_admission():
    admission = ExportAdmission()
    try:
        yield admission
    finally:
        # Quota/auth rejection never starts a worker. A started job owns its slot
        # beyond the lifetime of a cancelled HTTP request.
        if not admission.transferred:
            admission.release()


async def render_export_async(builder, /, *args, admission: ExportAdmission | None = None) -> bytes:
    admission = admission or ExportAdmission()
    if admission.released or admission.transferred:
        raise RuntimeError("Export admission already used")
    try:
        # AnyIO copies ContextVars (including locale) to its worker thread.
        job = asyncio.create_task(anyio.to_thread.run_sync(partial(builder, *args), limiter=_LIMITER))
    except BaseException:
        admission.release()
        raise
    admission.transferred = True
    job.add_done_callback(lambda _job: admission.release())
    # Cancellation of the HTTP task does not cancel admission/worker ownership.
    return await asyncio.shield(job)
