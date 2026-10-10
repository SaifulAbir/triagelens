"""Write JUnit-style results.xml for one run."""

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime

from tl_simulator.catalog import TestCase


@dataclass(frozen=True)
class TestResult:
    __test__ = False  # stop pytest from collecting this class

    test: TestCase
    station: str
    firmware: str
    start: datetime
    duration_ms: int
    log_path: str  # relative to the run folder, with forward slashes
    outcome: str = "passed"
    failure_message: str | None = None


def results_xml(run_id: str, results: list[TestResult]) -> bytes:
    """One <testsuite> per procedure family, in the order the results are given."""
    root = ET.Element("testsuites", _summary(run_id, results))
    for family, group in _group_by_family(results).items():
        suite = ET.SubElement(root, "testsuite", _summary(family, group))
        suite.set("timestamp", _iso(min(result.start for result in group)))
        for result in group:
            _add_testcase(suite, result)
    ET.indent(root)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"


def _summary(name: str, results: list[TestResult]) -> dict[str, str]:
    failures = sum(1 for result in results if result.outcome == "failed")
    total_ms = sum(result.duration_ms for result in results)
    return {
        "name": name,
        "tests": str(len(results)),
        "failures": str(failures),
        "time": _seconds(total_ms),
    }


def _add_testcase(suite: ET.Element, result: TestResult) -> None:
    case = ET.SubElement(
        suite,
        "testcase",
        {
            "classname": result.test.family,
            "name": result.test.name,
            "time": _seconds(result.duration_ms),
        },
    )
    properties = ET.SubElement(case, "properties")
    for name, value in (
        ("station", result.station),
        ("firmware", result.firmware),
        ("band", result.test.band),
        ("start", _iso(result.start)),
        ("log", result.log_path),
    ):
        ET.SubElement(properties, "property", {"name": name, "value": value})
    if result.outcome == "failed":
        ET.SubElement(case, "failure", {"message": result.failure_message or ""})


def _group_by_family(results: list[TestResult]) -> dict[str, list[TestResult]]:
    groups: dict[str, list[TestResult]] = {}
    for result in results:
        groups.setdefault(result.test.family, []).append(result)
    return groups


def _seconds(milliseconds: int) -> str:
    """JUnit time attribute: seconds with three decimals, e.g. 500 -> '0.500'."""
    seconds, millis = divmod(milliseconds, 1000)
    return f"{seconds}.{millis:03d}"


def _iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")
