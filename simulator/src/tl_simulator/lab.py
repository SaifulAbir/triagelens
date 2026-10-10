"""The synthetic test lab: stations, bands, firmware releases and test-suite versions."""

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class Station:
    name: str
    bands: tuple[str, ...]


@dataclass(frozen=True)
class Release:
    """A firmware or test-suite version and the night it is released."""

    version: str
    night: int


@dataclass(frozen=True)
class Lab:
    stations: tuple[Station, ...]
    bands: tuple[str, ...]
    firmware: tuple[Release, ...]
    suite: tuple[Release, ...]
    first_night: date
    stations_upgraded_per_night: int = 2


def default_lab() -> Lab:
    return Lab(
        stations=(
            Station("STN-01", ("n1", "n3", "n78")),
            Station("STN-02", ("n1", "n28", "n78")),
            Station("STN-03", ("n3", "n41", "n78")),
            Station("STN-04", ("n1", "n3", "n28", "n41")),
            Station("STN-05", ("n28", "n41", "n78")),
            Station("STN-06", ("n1", "n3", "n28", "n41", "n78")),
        ),
        bands=("n1", "n3", "n28", "n41", "n78"),
        firmware=(Release("2.1", 1), Release("2.2", 7), Release("2.3", 13)),
        suite=(Release("4.0", 1), Release("4.1", 10)),
        first_night=date(2026, 3, 2),
    )


def firmware_on(lab: Lab, station_index: int, night: int) -> str:
    """Firmware installed on a station on a given night.

    The first release is installed everywhere from night 1. Later releases roll out a few
    stations per night, so for a few nights the lab runs mixed firmware.
    """
    delay = station_index // lab.stations_upgraded_per_night
    return _latest_release(lab.firmware, night - delay)


def suite_on(lab: Lab, night: int) -> str:
    """Test-suite version on a given night. All stations update at once."""
    return _latest_release(lab.suite, night)


def night_date(lab: Lab, night: int) -> date:
    return lab.first_night + timedelta(days=night - 1)


def _latest_release(releases: tuple[Release, ...], night: int) -> str:
    current = releases[0].version
    for release in releases[1:]:
        if night >= release.night:
            current = release.version
    return current
