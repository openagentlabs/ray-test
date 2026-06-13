"""
Tiny dependency-free helper module for the chunked-upload bookkeeping.

Lives in its own file so unit tests can import the merging logic without
dragging in the FastAPI / auth / litellm stack. The router module
(``app.api.chunked_upload``) re-exports these names.
"""

from __future__ import annotations

from typing import List, Tuple

# ``(start, end_exclusive)``; lists kept sorted and non-overlapping.
Interval = Tuple[int, int]


def add_interval(intervals: List[Interval], s: int, e: int) -> None:
    """Insert ``(s, e)`` into ``intervals`` and merge in place.

    Caller is responsible for any required locking. Zero/negative-length
    inputs are silently ignored so retry loops can blindly re-add ranges.
    """
    if e <= s:
        return
    out: List[Interval] = []
    placed = False
    new = (s, e)
    for iv in intervals:
        if not placed and new[0] < iv[0]:
            out.append(new)
            placed = True
        out.append(iv)
    if not placed:
        out.append(new)

    merged: List[Interval] = []
    for cur in out:
        if not merged or cur[0] > merged[-1][1]:
            merged.append(cur)
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], cur[1]))
    intervals[:] = merged


def bytes_received(intervals: List[Interval]) -> int:
    return sum(e - s for s, e in intervals)


def is_complete(intervals: List[Interval], total: int) -> bool:
    return (
        len(intervals) == 1
        and intervals[0][0] == 0
        and intervals[0][1] >= total
    )
