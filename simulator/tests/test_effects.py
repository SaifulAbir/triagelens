import random

import pytest

from tl_simulator.catalog import build_catalog
from tl_simulator.effects import (
    CHECK,
    EFFECTS,
    PROTOCOL,
    RADIO,
    SETUP,
    WRONG_A3_LIMIT_MS,
    build_failure,
    stage_of,
)
from tl_simulator.lab import default_lab

CATALOG = build_catalog(default_lab().bands)


def _test(prefix):
    return next(t for t in CATALOG if t.name.startswith(prefix))


def test_stages_are_ordered_by_how_early_the_test_breaks():
    assert SETUP < RADIO < PROTOCOL < CHECK


@pytest.mark.parametrize(
    ("effect", "stage"),
    [
        ("instrument_lost", SETUP),
        ("license_expired", SETUP),
        ("band_override", SETUP),
        ("tdd_mismatch", SETUP),
        ("rx_degraded", RADIO),
        ("no_response", PROTOCOL),
        ("reestablishment", PROTOCOL),
        ("wrong_limit", CHECK),
        ("timing_overrun", CHECK),
    ],
)
def test_stage_of_each_effect(effect, stage):
    assert stage_of(effect) == stage


@pytest.mark.parametrize("effect", [e for e in EFFECTS if stage_of(e) == SETUP])
def test_setup_failures_break_before_any_protocol_step(effect):
    failure = build_failure(effect, random.Random(1), _test("TC_PDU_"))
    assert failure.at_step is None
    assert failure.events[-1].level == "F"


def test_no_response_breaks_at_the_reconfiguration_complete():
    test = _test("TC_PDU_")
    failure = build_failure("no_response", random.Random(1), test)
    assert test.steps[failure.at_step].message == "RRCReconfigurationComplete"
    assert "took=none" in failure.events[-1].message


def test_reestablishment_breaks_at_the_handover_complete():
    test = _test("TC_HO_INTER_BAND_")
    failure = build_failure("reestablishment", random.Random(1), test)
    assert test.steps[failure.at_step].message == "RRCReconfigurationComplete"
    assert "RRCReestablishmentRequest" in failure.events[0].message


def test_wrong_limit_always_fails_with_a_normal_answer_time():
    test = _test("TC_MEAS_A3_")
    for seed in range(100):
        failure = build_failure("wrong_limit", random.Random(seed), test)
        check = failure.events[-1].message
        took = int(check.split("took=")[1].removesuffix("ms"))
        assert f"within={WRONG_A3_LIMIT_MS}ms" in check
        assert WRONG_A3_LIMIT_MS < took <= 400  # 400ms would pass the correct 2000ms limit


def test_timing_overrun_misses_the_limit_by_a_few_ms():
    test = _test("TC_MEAS_PERIODIC_")
    for seed in range(100):
        failure = build_failure("timing_overrun", random.Random(seed), test)
        took = int(failure.events[-1].message.split("took=")[1].removesuffix("ms"))
        assert test.timeout_ms < took <= test.timeout_ms + 60


def test_timing_overrun_hits_the_last_received_step():
    test = _test("TC_HO_PINGPONG_")
    failure = build_failure("timing_overrun", random.Random(1), test)
    received = [i for i, step in enumerate(test.steps) if step.direction == "<<"]
    assert failure.at_step == received[-1]


def test_rx_degraded_warns_before_failing():
    failure = build_failure("rx_degraded", random.Random(1), _test("TC_MEAS_"))
    assert 2 <= len(failure.preamble) <= 3
    assert all("below threshold" in event.message for event in failure.preamble)


def test_instrument_lost_skips_cell_off():
    failure = build_failure("instrument_lost", random.Random(1), _test("TC_REG_"))
    assert failure.teardown.startswith("CELL:OFF skipped")


@pytest.mark.parametrize("effect", sorted(EFFECTS))
def test_every_failure_has_evidence_and_a_message(effect):
    prefix = {"rx_degraded": "TC_MEAS_", "wrong_limit": "TC_MEAS_A3_"}.get(effect, "TC_HO_")
    failure = build_failure(effect, random.Random(1), _test(prefix))
    assert failure.message
    assert any(event.evidence for event in failure.events)


def test_effect_on_a_test_without_the_trigger_step_is_an_error():
    with pytest.raises(ValueError):
        build_failure("wrong_limit", random.Random(1), _test("TC_REG_"))
