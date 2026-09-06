from __future__ import annotations

import asyncio
from collections import defaultdict


_payment_locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)


def payment_lock(payment_request_id: int) -> asyncio.Lock:
    """Return the process-wide lock used by bot and HTTP payment reviewers."""

    return _payment_locks[payment_request_id]
