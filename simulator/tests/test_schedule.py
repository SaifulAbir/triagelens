import random

from tl_simulator.catalog import build_catalog
from tl_simulator.lab import default_lab, firmware_on
from tl_simulator.schedule import assign_stations


def _queues(seed=1, night=8):
    lab = default_lab()
    return lab, assign_stations(random.Random(seed), lab, build_catalog(lab.bands), night)


def test_every_test_is_assigned_exactly_once():
    lab, queues = _queues()
    names = [a.test.name for queue in queues.values() for a in queue]
    assert sorted(names) == sorted(t.name for t in build_catalog(lab.bands))


def test_station_supports_the_band_of_each_assigned_test():
    _, queues = _queues()
    for queue in queues.values():
        for assignment in queue:
            assert assignment.test.band in assignment.station.bands


def test_assignment_uses_the_station_firmware_for_that_night():
    lab, queues = _queues(night=8)  # mid-rollout of 2.2
    for index, station in enumerate(lab.stations):
        for assignment in queues[station.name]:
            assert assignment.firmware == firmware_on(lab, index, 8)


def test_every_station_gets_work():
    _, queues = _queues()
    assert all(queues.values())


def test_different_seeds_spread_tests_differently():
    _, first = _queues(seed=1)
    _, second = _queues(seed=2)
    assert first != second
