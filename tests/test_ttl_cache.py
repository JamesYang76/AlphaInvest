from utils.ttl_cache import ttl_cache


def test_ttl_cache_reuses_result_within_ttl():
    calls = {"count": 0}

    @ttl_cache(ttl_seconds=60, maxsize=8)
    def cached_sum(values: list[int]) -> dict[str, int]:
        calls["count"] += 1
        return {"total": sum(values)}

    first = cached_sum([1, 2, 3])
    second = cached_sum([1, 2, 3])

    assert first == {"total": 6}
    assert second == {"total": 6}
    assert calls["count"] == 1


def test_ttl_cache_returns_isolated_copies():
    @ttl_cache(ttl_seconds=60, maxsize=8)
    def cached_payload() -> dict[str, list[int]]:
        return {"values": [1, 2, 3]}

    first = cached_payload()
    first["values"].append(4)

    second = cached_payload()

    assert second == {"values": [1, 2, 3]}
