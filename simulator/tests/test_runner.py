import random

from tl_simulator.catalog import RECEIVED, build_catalog
from tl_simulator.lab import default_lab
from tl_simulator.runner import MAIN_THREAD, run_test
from tl_simulator.schedule import Assignment


def _run(seed=1, family="HO"):
    lab = default_lab()
    test = next(t for t in build_catalog(lab.bands) if t.family == family)
    station = next(s for s in lab.stations if test.band in s.bands)
    return test, run_test(random.Random(seed), Assignment(test, station, "2.2"))


def test_lines_are_in_time_order():
    _, run = _run()
    offsets = [line.offset_ms for line in run.lines]
    assert offsets == sorted(offsets)


def test_duration_is_the_last_main_line():
    _, run = _run()
    last_main = [line for line in run.lines if line.thread == MAIN_THREAD][-1]
    assert run.duration_ms == last_main.offset_ms
    assert all(line.offset_ms <= run.duration_ms for line in run.lines)


def test_every_received_message_gets_a_passing_check():
    test, run = _run()
    checks = [line.message for line in run.lines if line.component == "CHECK"]
    received = [step.message for step in test.steps if step.direction == RECEIVED]
    assert len(checks) == len(received)
    for check, message in zip(checks, received, strict=True):
        assert check.startswith(f"PASS expect={message} ")


def test_log_interleaves_several_threads():
    _, run = _run()
    threads = [line.thread for line in run.lines]
    assert len(set(threads)) >= 3
    # Interleaved, not one block per thread: the thread changes many times.
    changes = sum(1 for a, b in zip(threads, threads[1:], strict=False) if a != b)
    assert changes > 5


def test_main_thread_starts_and_ends_the_test():
    test, run = _run()
    main = [line for line in run.lines if line.thread == MAIN_THREAD]
    assert main[0].message.startswith(f"start {test.name} ")
    assert main[-1].message == f"end {test.name} result=PASS"


def test_all_tests_pass_for_now():
    for seed in range(20):
        _, run = _run(seed)
        assert run.result == "PASS"
        assert all(line.level != "F" for line in run.lines)


def test_same_seed_same_run():
    assert _run(5)[1] == _run(5)[1]
