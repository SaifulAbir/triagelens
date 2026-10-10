import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

import pytest

from tl_simulator.campaign import generate_campaign, generate_night
from tl_simulator.catalog import build_catalog
from tl_simulator.lab import default_lab
from tl_simulator.logformat import FOOTER_RE, HEADER_RE, parse_line


def _files(root):
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


@pytest.fixture(scope="module")
def campaign(tmp_path_factory):
    out = tmp_path_factory.mktemp("campaign")
    generate_campaign(out, seed=42, nights=2)
    return out


def test_layout(campaign):
    assert (campaign / "lab.json").is_file()
    for night in ("night-01", "night-02"):
        assert (campaign / night / "results.xml").is_file()
        assert (campaign / night / "metadata.json").is_file()
        assert (campaign / night / "logs").is_dir()


def test_one_log_per_result(campaign):
    root = ET.parse(campaign / "night-01" / "results.xml").getroot()
    logs = [p.get("value") for p in root.iter("property") if p.get("name") == "log"]
    assert len(logs) == 150
    for log in logs:
        assert (campaign / "night-01" / log).is_file()
    assert len(list((campaign / "night-01" / "logs").rglob("*.log"))) == 150


def test_every_log_line_matches_the_format(campaign):
    for log in (campaign / "night-01" / "logs").rglob("*.log"):
        rows = log.read_text(encoding="utf-8").splitlines()
        assert HEADER_RE.match(rows[0]), log
        assert FOOTER_RE.match(rows[-1]), log
        for row in rows[1:-1]:
            assert parse_line(row) is not None, f"{log}: {row!r}"


def test_files_use_unix_line_endings(campaign):
    for content in _files(campaign).values():
        assert b"\r\n" not in content


def test_metadata(campaign):
    metadata = json.loads((campaign / "night-01" / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["run_id"] == "night-01"
    assert metadata["date"] == "2026-03-02"
    assert metadata["tests"] == 150
    assert metadata["suite_version"] == "4.0"
    assert set(metadata["firmware"].values()) == {"2.1"}


def test_tests_on_one_station_do_not_overlap(campaign):
    root = ET.parse(campaign / "night-01" / "results.xml").getroot()
    by_station = {}
    for case in root.iter("testcase"):
        props = {p.get("name"): p.get("value") for p in case.iter("property")}
        start = datetime.fromisoformat(props["start"])
        duration = timedelta(seconds=float(case.get("time")))
        by_station.setdefault(props["station"], []).append((start, duration))
    for runs in by_station.values():
        runs.sort()
        for (start, duration), (next_start, _) in zip(runs, runs[1:], strict=False):
            assert start + duration <= next_start


def test_same_seed_gives_identical_files(campaign, tmp_path):
    generate_campaign(tmp_path, seed=42, nights=2)
    assert _files(tmp_path) == _files(campaign)


def test_different_seed_gives_different_files(campaign, tmp_path):
    generate_campaign(tmp_path, seed=43, nights=2)
    assert _files(tmp_path) != _files(campaign)


def test_a_night_generated_alone_matches_the_same_night_in_a_campaign(campaign, tmp_path):
    # A shared generator across nights would fail this: night 2 alone would start from a
    # different point in the random sequence than night 2 after night 1.
    lab = default_lab()
    generate_night(tmp_path, seed=42, night=2, lab=lab, catalog=build_catalog(lab.bands))
    assert _files(tmp_path / "night-02") == _files(campaign / "night-02")
