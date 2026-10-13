"""Simulate one test execution and produce its log lines."""

import random
from dataclasses import dataclass

from tl_simulator.catalog import RECEIVED, Step, TestCase
from tl_simulator.effects import Event, Failure
from tl_simulator.injection import injection_line
from tl_simulator.logformat import LogLine
from tl_simulator.noise import background_lines
from tl_simulator.schedule import Assignment

MAIN_THREAD = "w2"
FIRST_LINE_NUMBER = 2  # line 1 of every log file is the header


@dataclass(frozen=True)
class SimulatedRun:
    lines: tuple[LogLine, ...]
    duration_ms: int
    result: str
    failure_message: str | None = None
    evidence_lines: tuple[int, ...] = ()  # line numbers in the log file
    has_injection: bool = False


def run_test(
    rng: random.Random,
    assignment: Assignment,
    failure: Failure | None = None,
    injection: bool = False,
) -> SimulatedRun:
    """Run a test, optionally broken by a failure, and interleave it with background noise."""
    station = assignment.station.name
    events = _test_events(rng, assignment.test, assignment.firmware, failure)
    main = list(zip(_to_lines(events, station), [event.evidence for event in events], strict=True))
    duration_ms = main[-1][0].offset_ms

    extra = background_lines(rng, station, duration_ms)
    if injection:
        extra.append(injection_line(rng, station, duration_ms))

    # sorted() is stable, so the test's own lines stay first when offsets are equal.
    tagged = sorted(main + [(line, False) for line in extra], key=lambda pair: pair[0].offset_ms)
    evidence = tuple(
        number
        for number, (_, is_evidence) in enumerate(tagged, start=FIRST_LINE_NUMBER)
        if is_evidence
    )
    return SimulatedRun(
        lines=tuple(line for line, _ in tagged),
        duration_ms=duration_ms,
        result="PASS" if failure is None else "FAIL",
        failure_message=None if failure is None else failure.message,
        evidence_lines=evidence,
        has_injection=injection,
    )


def _test_events(
    rng: random.Random, test: TestCase, firmware: str, failure: Failure | None
) -> list[Event]:
    events = _setup_events(rng, test, firmware)
    if failure is not None and failure.at_step is None:
        events += failure.events  # broken during setup: the protocol never starts
    else:
        events.append(Event(rng.randint(2000, 6000), "I", "FRAME", "cell synced"))
        stop = len(test.steps) if failure is None else failure.at_step
        if failure is not None:
            events += failure.preamble
        for step in test.steps[:stop]:
            events += _step_events(rng, test, step)
        if failure is not None:
            events += failure.events
    result = "PASS" if failure is None else "FAIL"
    teardown = "CELL:OFF" if failure is None else failure.teardown
    events.append(Event(rng.randint(100, 400), "I", "INSTR", teardown))
    events.append(Event(rng.randint(10, 50), "I", "FRAME", f"end {test.name} result={result}"))
    return events


def _setup_events(rng: random.Random, test: TestCase, firmware: str) -> list[Event]:
    power = rng.choice((-95.0, -88.0, -82.0, -75.0))
    return [
        Event(0, "I", "FRAME", f"start {test.name} variant={test.variant} fw={firmware}"),
        Event(rng.randint(50, 200), "I", "INSTR", f"SET:CELL:BAND {test.band}"),
        Event(rng.randint(20, 80), "I", "INSTR", f"SET:RF:POWER {power} dBm"),
        Event(rng.randint(300, 900), "I", "INSTR", "CELL:ON"),
    ]


def _step_events(rng: random.Random, test: TestCase, step: Step) -> list[Event]:
    took = rng.randint(20, 400)
    txn = rng.getrandbits(16)
    events = [Event(took, "I", "PROTO", f"{step.direction} {step.message} txn=0x{txn:04x}")]
    if step.direction == RECEIVED:
        check = f"PASS expect={step.message} within={test.timeout_ms}ms took={took}ms"
        events.append(Event(rng.randint(1, 5), "I", "CHECK", check))
    return events


def _to_lines(events: list[Event], station: str) -> list[LogLine]:
    lines = []
    offset = 0
    for event in events:
        offset += event.delay_ms
        line = LogLine(offset, station, MAIN_THREAD, event.level, event.component, event.message)
        lines.append(line)
    return lines
