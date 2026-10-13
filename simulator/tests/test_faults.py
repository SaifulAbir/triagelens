import random

import pytest

from tl_simulator.catalog import build_catalog
from tl_simulator.effects import EFFECTS, build_failure
from tl_simulator.faults import CATEGORIES, SCENARIO, Fault, select_fault
from tl_simulator.lab import default_lab, firmware_on, suite_on
from tl_simulator.schedule import Assignment

LAB = default_lab()
CATALOG = build_catalog(LAB.bands)
BY_ID = {fault.root_cause: fault for fault in SCENARIO}


def _assignment(test_name, station="STN-06", firmware="2.2"):
    test = next(t for t in CATALOG if t.name == test_name)
    station = next(s for s in LAB.stations if s.name == station)
    return Assignment(test, station, firmware)


def _select(assignment, night=5, suite="4.0", seed=1):
    return select_fault(random.Random(seed), SCENARIO, night, suite, assignment)


def test_root_causes_are_unique():
    assert len(BY_ID) == len(SCENARIO)


def test_every_fault_has_a_known_category_and_effect():
    for fault in SCENARIO:
        assert fault.category in CATEGORIES
        assert fault.effect in EFFECTS


def test_every_category_is_covered():
    assert {fault.category for fault in SCENARIO} == set(CATEGORIES)


def test_ticket_ids_use_the_issue_format():
    for fault in SCENARIO:
        if fault.ticket is not None:
            assert fault.ticket.startswith("ISS-")


@pytest.mark.parametrize("fault", SCENARIO, ids=lambda fault: fault.root_cause)
def test_effect_works_on_every_test_in_scope(fault):
    # A fault scoped to a test that lacks its trigger step would crash generation.
    for test in CATALOG:
        test_in_scope = fault.tests is None or test.name.startswith(fault.tests)
        band_in_scope = fault.bands is None or test.band in fault.bands
        if test_in_scope and band_in_scope:
            build_failure(fault.effect, random.Random(1), test)


def test_healthy_test_has_no_fault():
    assert _select(_assignment("TC_REG_INITIAL_N1")) is None


def test_device_bug_on_firmware_22_only():
    assignment = _assignment("TC_PDU_IPV4_N28", firmware="2.2")
    assert _select(assignment, night=8).root_cause == "RC-DEV-01"
    fixed = _assignment("TC_PDU_IPV4_N28", firmware="2.3")
    assert _select(fixed, night=15) is None


def test_device_bug_only_on_its_band():
    assert _select(_assignment("TC_PDU_IPV4_N78", firmware="2.2"), night=8) is None


def test_test_script_bug_starts_with_the_new_suite():
    assignment = _assignment("TC_MEAS_A3_N1")
    assert _select(assignment, suite="4.0") is None
    assert _select(assignment, suite="4.1").root_cause == "RC-SCR-01"


def test_station_fault_hits_every_test_on_that_station_and_night():
    for test in CATALOG:
        station = "STN-04"
        if test.band in next(s.bands for s in LAB.stations if s.name == station):
            fault = _select(_assignment(test.name, station=station), night=4)
            assert fault.root_cause == "RC-INF-01"


def test_station_fault_does_not_hit_other_nights_or_stations():
    assert _select(_assignment("TC_REG_INITIAL_N1", station="STN-04"), night=5) is None
    assert _select(_assignment("TC_REG_INITIAL_N1", station="STN-06"), night=4) is None


def test_earliest_stage_wins_station_down_beats_device_bug():
    # Night 16 on STN-04 with firmware 2.3: both RC-INF-01 and RC-DEV-02 are in scope.
    assignment = _assignment("TC_HO_INTER_FREQ_N1", station="STN-04", firmware="2.3")
    assert _select(assignment, night=16).root_cause == "RC-INF-01"


def test_earliest_stage_wins_radio_beats_device_bug():
    assignment = _assignment("TC_HO_INTER_FREQ_N28", station="STN-05", firmware="2.3")
    assert _select(assignment, night=15).root_cause == "RC-INF-03"


def test_tie_goes_to_the_fault_listed_first():
    first = Fault("RC-A", "flaky", "", "timing_overrun")
    second = Fault("RC-B", "flaky", "", "timing_overrun")
    assignment = _assignment("TC_REG_INITIAL_N1")
    fault = select_fault(random.Random(1), (first, second), 1, "4.0", assignment)
    assert fault.root_cause == "RC-A"


def test_flaky_fails_about_five_percent_of_runs():
    assignment = _assignment("TC_MEAS_PERIODIC_N1")
    hits = sum(_select(assignment, seed=seed) is not None for seed in range(4000))
    assert 140 < hits < 260  # 5% of 4000 = 200


def test_novel_faults_cannot_appear_in_build_nights():
    for fault in SCENARIO:
        if fault.novel:
            for night in range(1, LAB.build_nights + 1):
                for test in CATALOG:
                    for index, station in enumerate(LAB.stations):
                        assignment = Assignment(test, station, firmware_on(LAB, index, night))
                        assert not fault.in_scope(night, suite_on(LAB, night), assignment)
