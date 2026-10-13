import random

import pytest

from tl_simulator.catalog import RECEIVED, build_catalog
from tl_simulator.effects import EFFECTS, build_failure
from tl_simulator.injection import INJECTIONS
from tl_simulator.lab import default_lab
from tl_simulator.noise import HOST_THREAD
from tl_simulator.runner import FIRST_LINE_NUMBER, MAIN_THREAD, run_test
from tl_simulator.schedule import Assignment

# A test each effect can apply to.
EFFECT_TESTS = {
    "instrument_lost": "TC_REG_",
    "license_expired": "TC_REG_",
    "band_override": "TC_REG_",
    "tdd_mismatch": "TC_REG_",
    "rx_degraded": "TC_MEAS_",
    "no_response": "TC_PDU_",
    "reestablishment": "TC_HO_INTER_FREQ_",
    "wrong_limit": "TC_MEAS_A3_",
    "timing_overrun": "TC_HO_PINGPONG_",
}


def _assignment(prefix="TC_HO_"):
    lab = default_lab()
    test = next(t for t in build_catalog(lab.bands) if t.name.startswith(prefix))
    station = next(s for s in lab.stations if test.band in s.bands)
    return Assignment(test, station, "2.2")


def _run(seed=1, family="HO"):
    assignment = _assignment(f"TC_{family}_")
    return assignment.test, run_test(random.Random(seed), assignment)


def _failed_run(effect, prefix, seed=1, injection=False):
    assignment = _assignment(prefix)
    rng = random.Random(seed)
    failure = build_failure(effect, rng, assignment.test)
    return run_test(rng, assignment, failure, injection)


def _file_line(run, number):
    """The parsed log line at a 1-based file line number (line 1 is the header)."""
    return run.lines[number - FIRST_LINE_NUMBER]


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


def test_without_a_failure_the_test_passes():
    for seed in range(20):
        _, run = _run(seed)
        assert run.result == "PASS"
        assert run.failure_message is None
        assert run.evidence_lines == ()
        assert all(line.level != "F" for line in run.lines)


def test_same_seed_same_run():
    assert _run(5)[1] == _run(5)[1]


def test_effect_table_covers_every_effect():
    assert set(EFFECT_TESTS) == set(EFFECTS)


@pytest.mark.parametrize("effect", sorted(EFFECTS))
def test_failed_run_ends_with_fail(effect):
    run = _failed_run(effect, EFFECT_TESTS[effect])
    main = [line for line in run.lines if line.thread == MAIN_THREAD]
    assert run.result == "FAIL"
    assert run.failure_message
    assert main[-1].message.endswith("result=FAIL")
    assert run.duration_ms == main[-1].offset_ms


@pytest.mark.parametrize("effect", sorted(EFFECTS))
def test_evidence_line_numbers_point_at_the_evidence(effect):
    assignment = _assignment(EFFECT_TESTS[effect])
    failure = build_failure(effect, random.Random(3), assignment.test)
    run = run_test(random.Random(3), assignment, failure)
    expected = {event.message for event in failure.preamble + failure.events if event.evidence}
    found = {_file_line(run, number).message for number in run.evidence_lines}
    assert found == expected
    for number in run.evidence_lines:
        assert _file_line(run, number).thread == MAIN_THREAD


def test_setup_failure_never_reaches_the_protocol():
    run = _failed_run("instrument_lost", "TC_HO_")
    assert not [line for line in run.lines if line.component == "PROTO"]
    assert not [line for line in run.lines if line.message == "cell synced"]


def test_protocol_failure_stops_after_the_broken_step():
    run = _failed_run("reestablishment", "TC_HO_INTER_FREQ_")
    checks = [line.message for line in run.lines if line.component == "CHECK"]
    assert checks[-1].startswith("FAIL ")
    assert all(check.startswith("PASS ") for check in checks[:-1])


def test_radio_warnings_come_before_the_protocol():
    run = _failed_run("rx_degraded", "TC_MEAS_")
    main = [line for line in run.lines if line.thread == MAIN_THREAD]
    first_warning = next(i for i, line in enumerate(main) if "RX level" in line.message)
    first_proto = next(i for i, line in enumerate(main) if line.component == "PROTO")
    assert first_warning < first_proto


def test_injection_adds_one_host_line_that_is_not_evidence():
    run = _failed_run("reestablishment", "TC_HO_INTER_FREQ_", injection=True)
    injected = [line for line in run.lines if line.message in INJECTIONS]
    assert len(injected) == 1
    assert injected[0].thread == HOST_THREAD
    assert run.has_injection
    number = run.lines.index(injected[0]) + FIRST_LINE_NUMBER
    assert number not in run.evidence_lines
