import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta

from tl_simulator.catalog import build_catalog
from tl_simulator.junit import TestResult, results_xml
from tl_simulator.lab import default_lab

START = datetime(2026, 3, 2, 22, 0, tzinfo=UTC)


def _results(count=3, **changes):
    tests = build_catalog(default_lab().bands)
    results = []
    for index, test in enumerate(tests[:count]):
        values = {
            "test": test,
            "station": "STN-01",
            "firmware": "2.1",
            "start": START + timedelta(minutes=index),
            "duration_ms": 1500,
            "log_path": f"logs/STN-01/{test.name}.log",
        }
        results.append(TestResult(**(values | changes)))
    return results


def _parse(results):
    return ET.fromstring(results_xml("night-01", results))


def test_totals_on_root():
    root = _parse(_results())
    assert root.tag == "testsuites"
    assert root.get("name") == "night-01"
    assert root.get("tests") == "3"
    assert root.get("failures") == "0"
    assert root.get("time") == "4.500"


def test_short_durations_are_formatted_correctly():
    root = _parse(_results(count=1, duration_ms=500))
    assert root.find("testsuite/testcase").get("time") == "0.500"


def test_one_suite_per_family():
    tests = build_catalog(default_lab().bands)
    families = {t.family for t in tests}
    results = [
        TestResult(t, "STN-01", "2.1", START, 1000, f"logs/STN-01/{t.name}.log") for t in tests
    ]
    root = _parse(results)
    assert {suite.get("name") for suite in root.findall("testsuite")} == families
    assert len(root.findall("testsuite/testcase")) == 150


def test_testcase_properties():
    case = _parse(_results(count=1)).find("testsuite/testcase")
    properties = {p.get("name"): p.get("value") for p in case.findall("properties/property")}
    assert properties["station"] == "STN-01"
    assert properties["firmware"] == "2.1"
    assert properties["log"].startswith("logs/STN-01/")
    assert properties["start"] == "2026-03-02T22:00:00Z"


def test_suite_timestamp_is_earliest_start():
    suite = _parse(_results()).find("testsuite")
    assert suite.get("timestamp") == "2026-03-02T22:00:00Z"


def test_passing_tests_have_no_failure_element():
    assert _parse(_results()).find("testsuite/testcase/failure") is None


def test_failed_tests_get_a_failure_element():
    root = _parse(_results(outcome="failed", failure_message="timeout <RRC> & more"))
    assert root.get("failures") == "3"
    failure = root.find("testsuite/testcase/failure")
    assert failure.get("message") == "timeout <RRC> & more"  # escaped and read back intact


def test_output_is_utf8_xml_with_declaration():
    data = results_xml("night-01", _results())
    assert data.startswith(b"<?xml version='1.0' encoding='utf-8'?>")
    assert b"\r\n" not in data
