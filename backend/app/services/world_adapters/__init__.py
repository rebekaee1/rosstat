"""Official-source adapters for the world data plane (`WorldSourceAdapter`)."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_SESSION_ATTRS = ("_session", "_html_session")


def close_http_resources(adapter: object | None) -> None:
    """Close ``requests.Session`` objects owned by a world adapter.

    urllib3 ``HTTPAdapter.__del__`` can pin connection pools in GC cycles;
    without an explicit ``close()`` sockets survive the adapter going out of
    scope. Safe on ``None`` and on sessions that are already closed.
    """
    if adapter is None:
        return
    seen: set[int] = set()
    for name in _SESSION_ATTRS:
        sess = getattr(adapter, name, None)
        if sess is None:
            continue
        ident = id(sess)
        if ident in seen:
            continue
        seen.add(ident)
        closer = getattr(sess, "close", None)
        if not callable(closer):
            continue
        try:
            closer()
        except Exception:
            logger.debug("adapter %s.close failed", name, exc_info=True)
