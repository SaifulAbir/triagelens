from datetime import date

from tl_simulator.lab import default_lab, firmware_on, night_date, suite_on


def test_default_lab_size():
    lab = default_lab()
    assert len(lab.stations) == 6
    assert len(lab.firmware) == 3
    assert len(lab.bands) == 5


def test_every_band_is_supported_by_at_least_two_stations():
    # Needed later to tell "one bad station" apart from "fails everywhere".
    lab = default_lab()
    for band in lab.bands:
        assert sum(band in station.bands for station in lab.stations) >= 2


def test_station_bands_are_known_bands():
    lab = default_lab()
    for station in lab.stations:
        assert set(station.bands) <= set(lab.bands)


def test_first_firmware_is_installed_everywhere_on_night_one():
    lab = default_lab()
    assert {firmware_on(lab, i, 1) for i in range(len(lab.stations))} == {"2.1"}


def test_firmware_rolls_out_two_stations_per_night():
    lab = default_lab()  # 2.2 is released on night 7
    on_night_7 = [firmware_on(lab, i, 7) for i in range(6)]
    on_night_8 = [firmware_on(lab, i, 8) for i in range(6)]
    on_night_9 = [firmware_on(lab, i, 9) for i in range(6)]
    assert on_night_7 == ["2.2", "2.2", "2.1", "2.1", "2.1", "2.1"]
    assert on_night_8 == ["2.2", "2.2", "2.2", "2.2", "2.1", "2.1"]
    assert on_night_9 == ["2.2"] * 6


def test_firmware_never_goes_backwards():
    lab = default_lab()
    for index in range(len(lab.stations)):
        versions = [firmware_on(lab, index, night) for night in range(1, 21)]
        assert versions == sorted(versions)


def test_last_night_runs_latest_firmware_everywhere():
    lab = default_lab()
    assert {firmware_on(lab, i, 20) for i in range(6)} == {"2.3"}


def test_suite_switches_exactly_on_release_night():
    lab = default_lab()  # suite 4.1 is released on night 10
    assert suite_on(lab, 9) == "4.0"
    assert suite_on(lab, 10) == "4.1"
    assert suite_on(lab, 20) == "4.1"


def test_night_date_counts_from_first_night():
    lab = default_lab()
    assert night_date(lab, 1) == lab.first_night
    assert night_date(lab, 31) == date(2026, 4, 1)
