"""Decide which station runs each test on a given night."""

import random
from dataclasses import dataclass

from tl_simulator.catalog import TestCase
from tl_simulator.lab import Lab, Station, firmware_on


@dataclass(frozen=True)
class Assignment:
    test: TestCase
    station: Station
    firmware: str


def assign_stations(
    rng: random.Random, lab: Lab, catalog: tuple[TestCase, ...], night: int
) -> dict[str, list[Assignment]]:
    """Give every test to a random station that supports its band.

    Returns each station's queue in run order, keyed by station name.
    """
    queues: dict[str, list[Assignment]] = {station.name: [] for station in lab.stations}
    for test in catalog:
        index = rng.choice(
            [i for i, station in enumerate(lab.stations) if test.band in station.bands]
        )
        station = lab.stations[index]
        firmware = firmware_on(lab, index, night)
        queues[station.name].append(Assignment(test, station, firmware))
    return queues
