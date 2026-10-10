"""Ground truth checked against a full 20-night campaign."""

import json
import xml.etree.ElementTree as ET

import pytest

from tl_simulator.campaign import generate_campaign
from tl_simulator.faults import CATEGORIES, SCENARIO
from tl_simulator.groundtruth import GROUND_TRUTH_DIR, split_summary
from tl_simulator.lab import default_lab
from tl_simulator.logformat import parse_line

NIGHTS = 20


@pytest.fixture(scope="module")
def campaign(tmp_path_factory):
    out = tmp_path_factory.mktemp("full")
    generate_campaign(out, seed=42, nights=NIGHTS)
    return out


def _labels(campaign):
    labels = []
    for night in range(1, NIGHTS + 1):
        path = campaign / GROUND_TRUTH_DIR / f"night-{night:02d}.json"
        labels += json.loads(path.read_text(encoding="utf-8"))
    return labels


def _night(label):
    return int(label["run_id"].removeprefix("night-"))


def _failed_tests(campaign, run_id):
    root = ET.parse(campaign / run_id / "results.xml").getroot()
    return {case.get("name") for case in root.iter("testcase") if case.find("failure") is not None}


def test_ground_truth_is_outside_the_night_folders(campaign):
    assert (campaign / GROUND_TRUTH_DIR / "faults.json").is_file()
    assert (campaign / GROUND_TRUTH_DIR / "split.json").is_file()
    for night_dir in campaign.glob("night-*"):
        assert not any("ground" in path.name for path in night_dir.rglob("*"))


def test_exactly_one_label_per_failed_test(campaign):
    labels = _labels(campaign)
    for night in range(1, NIGHTS + 1):
        run_id = f"night-{night:02d}"
        labelled = [label["test"] for label in labels if label["run_id"] == run_id]
        assert len(labelled) == len(set(labelled))
        assert set(labelled) == _failed_tests(campaign, run_id)


def test_every_root_cause_appears(campaign):
    assert {label["root_cause"] for label in _labels(campaign)} == {f.root_cause for f in SCENARIO}


def test_every_category_appears_in_build_and_eval_nights(campaign):
    build = default_lab().build_nights
    labels = _labels(campaign)
    assert {label["category"] for label in labels if _night(label) <= build} == set(CATEGORIES)
    assert {label["category"] for label in labels if _night(label) > build} == set(CATEGORIES)


def test_novel_faults_only_in_eval_nights(campaign):
    novel = [label for label in _labels(campaign) if label["novel"]]
    assert novel
    assert all(_night(label) > default_lab().build_nights for label in novel)


def test_labels_match_the_fault_definition(campaign):
    by_id = {fault.root_cause: fault for fault in SCENARIO}
    for label in _labels(campaign):
        fault = by_id[label["root_cause"]]
        assert label["category"] == fault.category
        assert label["ticket"] == fault.ticket
        assert label["novel"] == fault.novel
        assert label["expected_cluster"] == label["root_cause"]


def test_evidence_lines_point_at_real_failure_lines(campaign):
    for label in _labels(campaign):
        rows = (campaign / label["run_id"] / label["log"]).read_text(encoding="utf-8").splitlines()
        assert label["evidence_lines"]
        evidence = [parse_line(rows[number - 1]) for number in label["evidence_lines"]]
        assert all(line is not None for line in evidence), label
        assert evidence[-1].level in ("E", "F"), label


def test_some_failures_carry_an_injection(campaign):
    injected = [label for label in _labels(campaign) if label["has_injection"]]
    assert injected
    assert {label["root_cause"] for label in injected} <= {"RC-DEV-02", "RC-INF-01"}


def test_failure_rate_is_realistic(campaign):
    assert 0.05 < len(_labels(campaign)) / (150 * NIGHTS) < 0.2


def test_split_file(campaign):
    split = json.loads((campaign / GROUND_TRUTH_DIR / "split.json").read_text(encoding="utf-8"))
    assert split["build_nights"] == list(range(1, 11))
    assert split["eval_nights"] == list(range(11, 21))


def test_split_with_fewer_nights_than_the_build_period():
    split = split_summary(default_lab(), nights=3)
    assert split["build_nights"] == [1, 2, 3]
    assert split["eval_nights"] == []


def test_faults_file_lists_the_whole_scenario(campaign):
    path = campaign / GROUND_TRUTH_DIR / "faults.json"
    faults = json.loads(path.read_text(encoding="utf-8"))
    assert [fault["root_cause"] for fault in faults] == [f.root_cause for f in SCENARIO]
