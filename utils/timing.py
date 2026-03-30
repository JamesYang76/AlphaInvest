from __future__ import annotations

import time


def start_timer() -> float:
    return time.perf_counter()


def elapsed_ms(started_at: float) -> float:
    return (time.perf_counter() - started_at) * 1000


def format_elapsed_ms(started_at: float) -> str:
    return f"{elapsed_ms(started_at):.1f}ms"
