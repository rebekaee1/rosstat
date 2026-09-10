"""Bounded PNG rendering outside the public ASGI event loop.

One renderer per process, at most three waiting renders. Cancellation cannot
release a running worker's capacity early; the concurrent future owns the slot.
Locale ContextVars are copied into the worker. Cached PNGs bypass this helper.
"""
from __future__ import annotations

import asyncio
import contextvars
import threading
from concurrent.futures import ThreadPoolExecutor
from functools import partial

from fastapi import HTTPException

_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="og-render")
_SLOTS = threading.BoundedSemaphore(4)


async def render_og_async(render, /, **kwargs) -> bytes:
    slots = _SLOTS
    if not slots.acquire(blocking=False):
        raise HTTPException(
            status_code=503, detail="Image renderer busy; retry shortly",
            headers={"Retry-After": "5"},
        )
    try:
        ctx = contextvars.copy_context()
        future = _EXECUTOR.submit(ctx.run, partial(render, **kwargs))
    except BaseException:
        slots.release()
        raise
    future.add_done_callback(lambda _future: slots.release())
    return await asyncio.wrap_future(future)
