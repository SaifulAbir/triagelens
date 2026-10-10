"""The invented TriageLens log format: a header line, one line per event, a footer line.

See docs/log-format.md for the full spec and examples.
"""

import re
from dataclasses import dataclass
from datetime import datetime

LEVELS = ("D", "I", "W", "E", "F")
COMPONENTS = ("FRAME", "PROTO", "INSTR", "CHECK", "HOST")

LINE_RE = re.compile(
    r"^\+(?P<seconds>\d{4,})\.(?P<millis>\d{3}) "
    r"(?P<station>\S+) (?P<thread>w\d+) (?P<level>[DIWEF]) "
    r"(?P<component>[A-Z]+) +(?P<message>.*)$"
)
HEADER_RE = re.compile(
    r"^== TLRUN (?P<run_id>\S+) test=(?P<test>\S+) stn=(?P<station>\S+) "
    r"fw=(?P<firmware>\S+) band=(?P<band>\S+) start=(?P<start>\S+) ==$"
)
FOOTER_RE = re.compile(
    r"^== END result=(?P<result>[A-Z]+) duration=(?P<duration>\d{4,}\.\d{3})s ==$"
)


@dataclass(frozen=True)
class LogLine:
    offset_ms: int
    station: str
    thread: str
    level: str
    component: str
    message: str


def render_line(line: LogLine) -> str:
    return (
        f"+{format_offset(line.offset_ms)} {line.station} {line.thread} {line.level} "
        f"{line.component:<6} {line.message}"
    )


def parse_line(text: str) -> LogLine | None:
    """Parse one log line. Returns None for header, footer or malformed lines."""
    match = LINE_RE.match(text)
    if match is None:
        return None
    return LogLine(
        offset_ms=int(match["seconds"]) * 1000 + int(match["millis"]),
        station=match["station"],
        thread=match["thread"],
        level=match["level"],
        component=match["component"],
        message=match["message"],
    )


def render_header(
    run_id: str, test: str, station: str, firmware: str, band: str, start: datetime
) -> str:
    started = start.strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        f"== TLRUN {run_id} test={test} stn={station} fw={firmware} band={band} start={started} =="
    )


def render_footer(result: str, duration_ms: int) -> str:
    return f"== END result={result} duration={format_offset(duration_ms)}s =="


def render_log(header: str, lines: list[LogLine], footer: str) -> str:
    body = [render_line(line) for line in lines]
    return "\n".join([header, *body, footer]) + "\n"


def format_offset(offset_ms: int) -> str:
    """Milliseconds as seconds with exactly three decimals, at least four integer digits."""
    seconds, millis = divmod(offset_ms, 1000)
    return f"{seconds:04d}.{millis:03d}"
