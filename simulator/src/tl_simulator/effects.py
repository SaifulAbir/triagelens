"""How each kind of fault changes a test run.

A fault breaks a test at one of four stages. When two faults hit the same test, the earlier stage
wins, because the test never gets further than that point.
"""

import random
from collections.abc import Callable
from dataclasses import dataclass

from tl_simulator.catalog import RECEIVED, TestCase

SETUP = 0  # the station fails before the device can connect
RADIO = 1  # bad radio conditions, visible as soon as the protocol starts
PROTOCOL = 2  # the device answers wrongly or not at all
CHECK = 3  # the device answers, but a check fails

WRONG_A3_LIMIT_MS = 200


@dataclass(frozen=True)
class Event:
    """One line of the test's own log, timed relative to the previous event."""

    delay_ms: int
    level: str
    component: str
    message: str
    evidence: bool = False  # ground truth: this line shows the root cause


@dataclass(frozen=True)
class Failure:
    """What one fault does to one test run."""

    message: str  # short reason for results.xml
    events: tuple[Event, ...]  # written where the test breaks
    at_step: int | None = None  # protocol step that breaks; None means during setup
    preamble: tuple[Event, ...] = ()  # written right after setup, e.g. radio warnings
    teardown: str = "CELL:OFF"


type FailureBuilder = Callable[[random.Random, TestCase], Failure]


def instrument_lost(rng: random.Random, test: TestCase) -> Failure:
    wait = rng.randint(4000, 6000)
    return Failure(
        message="instrument not reachable",
        events=(
            _evidence(
                wait, "E", "INSTR", f"connection lost: QUERY:CELL:STATE? no answer in {wait}ms"
            ),
            _evidence(rng.randint(1000, 3000), "E", "INSTR", "reconnect attempt 1 failed"),
            _evidence(rng.randint(10, 50), "F", "FRAME", "abort: instrument not reachable"),
        ),
        teardown="CELL:OFF skipped: instrument not connected",
    )


def license_expired(rng: random.Random, test: TestCase) -> Failure:
    return Failure(
        message="cell could not be started: license expired",
        events=(
            _evidence(
                rng.randint(50, 200),
                "E",
                "INSTR",
                "CELL:ON rejected: option 'NR-TDD' license expired",
            ),
            _evidence(rng.randint(10, 50), "F", "FRAME", "abort: cell could not be started"),
        ),
    )


def band_override(rng: random.Random, test: TestCase) -> Failure:
    warning = f"band override from station profile: n77 (requested {test.band})"
    return _device_not_attached(rng, test, _evidence(rng.randint(50, 200), "W", "INSTR", warning))


def tdd_mismatch(rng: random.Random, test: TestCase) -> Failure:
    warning = "TDD pattern DDDSU does not match station profile DDDFU"
    return _device_not_attached(rng, test, _evidence(rng.randint(50, 200), "W", "INSTR", warning))


def rx_degraded(rng: random.Random, test: TestCase) -> Failure:
    warnings = []
    for _ in range(rng.randint(2, 3)):
        level = rng.uniform(-108.0, -101.0)
        message = f"RX level {level:.1f} dBm below threshold -100.0 dBm"
        warnings.append(_evidence(rng.randint(200, 600), "W", "INSTR", message))
    return Failure(
        message="no MeasurementReport from device",
        at_step=_first_step(test, "MeasurementReport"),
        preamble=tuple(warnings),
        events=(_no_answer(test, "MeasurementReport"),),
    )


def no_response(rng: random.Random, test: TestCase) -> Failure:
    return Failure(
        message="no RRCReconfigurationComplete from device",
        at_step=_first_step(test, "RRCReconfigurationComplete"),
        events=(_no_answer(test, "RRCReconfigurationComplete"),),
    )


def reestablishment(rng: random.Random, test: TestCase) -> Failure:
    txn = rng.getrandbits(16)
    request = f"<< RRCReestablishmentRequest cause=handoverFailure txn=0x{txn:04x}"
    check = "FAIL expect=RRCReconfigurationComplete got=RRCReestablishmentRequest"
    return Failure(
        message="handover failed: device sent RRCReestablishmentRequest",
        at_step=_first_step(test, "RRCReconfigurationComplete"),
        events=(
            _evidence(rng.randint(50, 300), "I", "PROTO", request),
            _evidence(rng.randint(1, 5), "E", "CHECK", check),
        ),
    )


def wrong_limit(rng: random.Random, test: TestCase) -> Failure:
    """Test script bug: the limit is wrong, so a normal answer time fails the check."""
    index = _first_step(test, "MeasurementReport")
    took = rng.randint(WRONG_A3_LIMIT_MS + 50, 400)
    return _late_answer(rng, index, "MeasurementReport", WRONG_A3_LIMIT_MS, took)


def timing_overrun(rng: random.Random, test: TestCase) -> Failure:
    """Flaky: the device answers a few milliseconds after a tight limit."""
    index = _last_received_step(test)
    took = test.timeout_ms + rng.randint(5, 60)
    return _late_answer(rng, index, test.steps[index].message, test.timeout_ms, took)


EFFECTS: dict[str, tuple[int, FailureBuilder]] = {
    "instrument_lost": (SETUP, instrument_lost),
    "license_expired": (SETUP, license_expired),
    "band_override": (SETUP, band_override),
    "tdd_mismatch": (SETUP, tdd_mismatch),
    "rx_degraded": (RADIO, rx_degraded),
    "no_response": (PROTOCOL, no_response),
    "reestablishment": (PROTOCOL, reestablishment),
    "wrong_limit": (CHECK, wrong_limit),
    "timing_overrun": (CHECK, timing_overrun),
}


def stage_of(effect: str) -> int:
    return EFFECTS[effect][0]


def build_failure(effect: str, rng: random.Random, test: TestCase) -> Failure:
    return EFFECTS[effect][1](rng, test)


def _device_not_attached(rng: random.Random, test: TestCase, warning: Event) -> Failure:
    return Failure(
        message="device did not attach: no RRCSetupRequest",
        events=(
            warning,
            _no_answer(test, "RRCSetupRequest"),
            _evidence(rng.randint(10, 50), "F", "FRAME", "abort: device did not attach"),
        ),
    )


def _late_answer(
    rng: random.Random, index: int, message: str, limit_ms: int, took_ms: int
) -> Failure:
    txn = rng.getrandbits(16)
    return Failure(
        message=f"{message} took {took_ms}ms, limit {limit_ms}ms",
        at_step=index,
        events=(
            Event(took_ms, "I", "PROTO", f"<< {message} txn=0x{txn:04x}"),
            _evidence(
                rng.randint(1, 5),
                "E",
                "CHECK",
                f"FAIL expect={message} within={limit_ms}ms took={took_ms}ms",
            ),
        ),
    )


def _no_answer(test: TestCase, message: str) -> Event:
    check = f"FAIL expect={message} within={test.timeout_ms}ms took=none"
    return _evidence(test.timeout_ms, "E", "CHECK", check)


def _evidence(delay_ms: int, level: str, component: str, message: str) -> Event:
    return Event(delay_ms, level, component, message, evidence=True)


def _first_step(test: TestCase, message: str) -> int:
    """Index of the first step with this message. Raises ValueError if the test has none."""
    return [step.message for step in test.steps].index(message)


def _last_received_step(test: TestCase) -> int:
    return max(i for i, step in enumerate(test.steps) if step.direction == RECEIVED)
