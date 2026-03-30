from __future__ import annotations

import concurrent.futures as futures
from typing import Callable, TypeVar

T = TypeVar("T")


class OperationTimeoutError(TimeoutError):
    pass


def call_with_timeout(
    func: Callable[[], T],
    *,
    timeout_seconds: float,
    timeout_message: str,
) -> T:
    with futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(func)
        try:
            return future.result(timeout=timeout_seconds)
        except futures.TimeoutError as exc:
            future.cancel()
            raise OperationTimeoutError(timeout_message) from exc
