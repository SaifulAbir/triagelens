import random

from tl_simulator.noise import (
    HOST_THREAD,
    KEEPALIVE_THREAD,
    POLL_THREAD,
    background_lines,
)


def _lines(seed, duration_ms=10_000):
    return background_lines(random.Random(seed), "STN-01", duration_ms)


def test_lines_stay_inside_the_test_duration():
    for seed in range(50):
        for line in _lines(seed):
            assert 0 <= line.offset_ms <= 10_000


def test_one_keepalive_per_second():
    keepalives = [line for line in _lines(1) if line.thread == KEEPALIVE_THREAD]
    assert [line.offset_ms for line in keepalives] == list(range(1000, 10_000, 1000))
    assert keepalives[0].message == "keepalive seq=0"


def test_instrument_is_polled_regularly():
    polls = [line for line in _lines(1) if line.thread == POLL_THREAD]
    assert 3 <= len(polls) <= 5


def test_very_short_test_has_no_keepalives():
    assert not [line for line in _lines(1, duration_ms=999) if line.thread == KEEPALIVE_THREAD]


def test_zero_duration_produces_no_lines():
    for seed in range(20):
        assert _lines(seed, duration_ms=0) == []


def test_warnings_and_harmless_errors_appear_sometimes():
    levels = [
        line.level for seed in range(500) for line in _lines(seed) if line.thread == HOST_THREAD
    ]
    assert 100 < levels.count("W") < 200  # ~30% of 500
    assert 5 < levels.count("E") < 50  # ~5% of 500


def test_background_never_contains_fatal_lines():
    for seed in range(200):
        assert all(line.level != "F" for line in _lines(seed))


def test_same_seed_gives_same_lines():
    assert _lines(7) == _lines(7)
