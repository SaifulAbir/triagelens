from datetime import UTC, datetime

import pytest

from tl_simulator.logformat import (
    FOOTER_RE,
    HEADER_RE,
    LogLine,
    format_offset,
    parse_line,
    render_footer,
    render_header,
    render_line,
    render_log,
)


def _line(**changes):
    values = {
        "offset_ms": 12345,
        "station": "STN-03",
        "thread": "w2",
        "level": "I",
        "component": "PROTO",
        "message": ">> RRCReconfiguration txn=0x3f2a",
    }
    return LogLine(**(values | changes))


def test_render_line_layout():
    assert render_line(_line()) == "+0012.345 STN-03 w2 I PROTO  >> RRCReconfiguration txn=0x3f2a"


@pytest.mark.parametrize(
    ("offset_ms", "expected"),
    [(0, "0000.000"), (7, "0000.007"), (1000, "0001.000"), (12345678, "12345.678")],
)
def test_format_offset(offset_ms, expected):
    assert format_offset(offset_ms) == expected


@pytest.mark.parametrize(
    "line",
    [
        _line(),
        _line(offset_ms=0),
        _line(offset_ms=12345678),  # more than four integer digits
        _line(component="CHECK", message="PASS expect=X within=2000ms took=31ms"),
        _line(message="contains == and  double  spaces and a trailing space "),
        _line(level="E", component="HOST", message="NTP sync failed, retrying in 5s"),
        _line(thread="w10"),
        _line(message=""),
    ],
)
def test_parse_is_inverse_of_render(line):
    assert parse_line(render_line(line)) == line


@pytest.mark.parametrize(
    "text",
    [
        "",
        "0012.345 STN-03 w2 I PROTO  missing plus sign",
        "+12.345 STN-03 w2 I PROTO  too few integer digits",
        "+0012.34 STN-03 w2 I PROTO  two decimals",
        "+0012.345 STN-03 w2 X PROTO  unknown level",
        "+0012.345 STN-03 t2 I PROTO  bad thread",
        "+0012.345 STN-03 w2 I proto  lowercase component",
        "== END result=PASS duration=0013.100s ==",
    ],
)
def test_parse_rejects_malformed_lines(text):
    assert parse_line(text) is None


def test_header_round_trip():
    start = datetime(2026, 3, 7, 22, 14, 2, tzinfo=UTC)
    header = render_header("night-06", "TC_HO_A3_N78", "STN-03", "2.2", "n78", start)
    match = HEADER_RE.match(header)
    assert match is not None
    assert match["test"] == "TC_HO_A3_N78"
    assert match["start"] == "2026-03-07T22:14:02Z"


def test_footer_round_trip():
    match = FOOTER_RE.match(render_footer("PASS", 13100))
    assert match is not None
    assert match["duration"] == "0013.100"


def test_render_log_has_header_lines_footer_and_final_newline():
    text = render_log("HEADER", [_line(), _line(offset_ms=20000)], "FOOTER")
    assert text.endswith("\n")
    rows = text.splitlines()
    assert rows[0] == "HEADER"
    assert rows[-1] == "FOOTER"
    assert len(rows) == 4
