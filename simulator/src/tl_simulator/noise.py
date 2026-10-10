"""Background log lines that have nothing to do with the test result.

Real logs are mostly noise: keepalives, instrument polling and warnings nobody acts on.
Some harmless lines are even at level E, so "has an error line" never means "failed".
"""

import random

from tl_simulator.logformat import LogLine

KEEPALIVE_THREAD = "w9"
POLL_THREAD = "w1"
HOST_THREAD = "w4"

KEEPALIVE_INTERVAL_MS = 1000
POLL_INTERVAL_MS = 2500
POLL_JITTER_MS = 200
WARNING_CHANCE = 0.3
ERROR_CHANCE = 0.05

# (component, message template, lowest {n}, highest {n})
HARMLESS_WARNINGS = (
    ("HOST", "disk usage {n}% on /var/lab", 80, 92),
    ("HOST", "NTP offset {n}ms exceeds soft limit 25ms", 26, 60),
    ("FRAME", "config key 'rf.legacy_gain' is deprecated, using 'rf.gain' ({n} uses)", 1, 9),
    ("INSTR", "fan speed {n}% above nominal", 70, 95),
)
HARMLESS_ERRORS = (
    ("HOST", "NTP sync failed, retrying in {n}s", 2, 10),
    ("FRAME", "telemetry upload failed (attempt {n}), will retry", 1, 3),
)


def background_lines(rng: random.Random, station: str, duration_ms: int) -> list[LogLine]:
    if duration_ms <= 0:
        return []
    lines = _keepalives(station, duration_ms) + _instrument_polls(rng, station, duration_ms)
    if rng.random() < WARNING_CHANCE:
        lines.append(_harmless_line(rng, station, duration_ms, "W", HARMLESS_WARNINGS))
    if rng.random() < ERROR_CHANCE:
        lines.append(_harmless_line(rng, station, duration_ms, "E", HARMLESS_ERRORS))
    return lines


def _keepalives(station: str, duration_ms: int) -> list[LogLine]:
    return [
        LogLine(offset, station, KEEPALIVE_THREAD, "D", "FRAME", f"keepalive seq={seq}")
        for seq, offset in enumerate(
            range(KEEPALIVE_INTERVAL_MS, duration_ms, KEEPALIVE_INTERVAL_MS)
        )
    ]


def _instrument_polls(rng: random.Random, station: str, duration_ms: int) -> list[LogLine]:
    lines = []
    offset = rng.randint(0, POLL_INTERVAL_MS)
    while offset < duration_ms:
        temperature = round(rng.uniform(38.0, 43.0), 1)
        message = f"QUERY:RF:STATUS? -> OK temp={temperature}C"
        lines.append(LogLine(offset, station, POLL_THREAD, "D", "INSTR", message))
        offset += POLL_INTERVAL_MS + rng.randint(-POLL_JITTER_MS, POLL_JITTER_MS)
    return lines


def _harmless_line(
    rng: random.Random,
    station: str,
    duration_ms: int,
    level: str,
    templates: tuple[tuple[str, str, int, int], ...],
) -> LogLine:
    component, template, low, high = rng.choice(templates)
    message = template.format(n=rng.randint(low, high))
    return LogLine(rng.randint(0, duration_ms), station, HOST_THREAD, level, component, message)
