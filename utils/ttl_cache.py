from __future__ import annotations

import copy
import threading
import time
from collections.abc import Hashable
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class _CacheEntry:
    expires_at: float
    value: Any


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple((k, _freeze(v)) for k, v in sorted(value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(v) for v in value)
    if isinstance(value, set):
        return tuple(sorted(_freeze(v) for v in value))
    if isinstance(value, Hashable):
        return value
    return repr(value)


def _prune(cache: dict[Any, _CacheEntry], now: float, maxsize: int) -> None:
    expired_keys = [key for key, entry in cache.items() if entry.expires_at <= now]
    for key in expired_keys:
        cache.pop(key, None)

    while len(cache) > maxsize:
        oldest_key = min(cache, key=lambda key: cache[key].expires_at)
        cache.pop(oldest_key, None)


def ttl_cache(ttl_seconds: int, maxsize: int = 128) -> Callable[[F], F]:
    """
    짧은 TTL 기반 메모리 캐시.

    - 함수 인자를 불변 구조로 정규화해 key를 만듭니다.
    - 반환값은 deepcopy로 격리해 호출부가 캐시 원본을 변경하지 못하게 합니다.
    """

    def decorator(func: F) -> F:
        cache: dict[Any, _CacheEntry] = {}
        lock = threading.RLock()

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = (_freeze(args), _freeze(kwargs))
            now = time.monotonic()

            with lock:
                entry = cache.get(key)
                if entry is not None and entry.expires_at > now:
                    return copy.deepcopy(entry.value)

            result = func(*args, **kwargs)

            with lock:
                cache[key] = _CacheEntry(expires_at=now + ttl_seconds, value=copy.deepcopy(result))
                if len(cache) > maxsize:
                    _prune(cache, now, maxsize)

            return copy.deepcopy(result)

        return wrapper  # type: ignore[return-value]

    return decorator
