"""Simulate one test execution and produce its log lines."""

import random
from dataclasses import dataclass

from tl_simulator.catalog import RECEIVED, TestCase
from tl_simulator.logformat import LogLine
from tl_simulator.noise import background_lines
from tl_simulator.schedule import Assignment

MAIN_THREAD = "w2"

# (delay since the previous event in ms, level, component, message)
type Event = tuple[int, str, str, str]


@dataclass(frozen=True)
class SimulatedRun:
    lines: tuple[LogLine, ...]
    duration_ms: int
    result: str


def run_test(rng: random.Random, assignment: Assignment) -> SimulatedRun:
    """Run a test and interleave its own lines with background noise."""
    events = _test_events(rng, assignment.test, assignment.firmware)
    main = _to_lines(events, assignment.station.name)
    duration_ms = main[-1].offset_ms
    noise = background_lines(rng, assignment.station.name, duration_ms)
    # sorted() is stable, so the test's own lines stay first when offsets are equal.
    lines = sorted(main + noise, key=lambda line: line.offset_ms)
    return SimulatedRun(tuple(lines), duration_ms, "PASS")


def _test_events(rng: random.Random, test: TestCase, firmware: str) -> list[Event]:
    power = rng.choice((-95.0, -88.0, -82.0, -75.0))
    events: list[Event] = [
        (0, "I", "FRAME", f"start {test.name} variant={test.variant} fw={firmware}"),
        (rng.randint(50, 200), "I", "INSTR", f"SET:CELL:BAND {test.band}"),
        (rng.randint(20, 80), "I", "INSTR", f"SET:RF:POWER {power} dBm"),
        (rng.randint(300, 900), "I", "INSTR", "CELL:ON"),
        (rng.randint(2000, 6000), "I", "FRAME", "cell synced"),
    ]
    for step in test.steps:
        took = rng.randint(20, 400)
        txn = rng.getrandbits(16)
        events.append((took, "I", "PROTO", f"{step.direction} {step.message} txn=0x{txn:04x}"))
        if step.direction == RECEIVED:
            check = f"PASS expect={step.message} within={test.timeout_ms}ms took={took}ms"
            events.append((rng.randint(1, 5), "I", "CHECK", check))
    events.append((rng.randint(100, 400), "I", "INSTR", "CELL:OFF"))
    events.append((rng.randint(10, 50), "I", "FRAME", f"end {test.name} result=PASS"))
    return events


def _to_lines(events: list[Event], station: str) -> list[LogLine]:
    lines = []
    offset = 0
    for delay, level, component, message in events:
        offset += delay
        lines.append(LogLine(offset, station, MAIN_THREAD, level, component, message))
    return lines
