"""Generate a full campaign: one folder per night with results.xml, logs and metadata."""

import json
import random
from datetime import UTC, datetime, time, timedelta
from pathlib import Path

from tl_simulator import __version__
from tl_simulator.catalog import TestCase, build_catalog
from tl_simulator.junit import TestResult, results_xml
from tl_simulator.lab import Lab, default_lab, firmware_on, night_date, suite_on
from tl_simulator.logformat import render_footer, render_header, render_log
from tl_simulator.runner import run_test
from tl_simulator.schedule import Assignment, assign_stations

NIGHT_START = time(22, 0, tzinfo=UTC)
MIN_GAP_MS = 5_000
MAX_GAP_MS = 20_000


def generate_campaign(out_dir: Path, seed: int, nights: int, lab: Lab | None = None) -> None:
    lab = lab or default_lab()
    catalog = build_catalog(lab.bands)
    _write_json(out_dir / "lab.json", _lab_summary(lab, catalog))
    for night in range(1, nights + 1):
        generate_night(out_dir, seed, night, lab, catalog)


def generate_night(
    out_dir: Path, seed: int, night: int, lab: Lab, catalog: tuple[TestCase, ...]
) -> list[TestResult]:
    """Generate one night.

    Each night gets its own random generator seeded from (seed, night). With one shared generator,
    any change to one night (e.g. an injected fault drawing extra random numbers) would shift every
    later night. This way nights are isolated and each one can be generated on its own.
    """
    rng = random.Random(f"{seed}-night-{night}")
    run_id = f"night-{night:02d}"
    run_dir = out_dir / run_id
    night_start = datetime.combine(night_date(lab, night), NIGHT_START)

    results = []
    for queue in assign_stations(rng, lab, catalog, night).values():
        clock = night_start
        for assignment in queue:
            result = _run_and_write(rng, run_id, run_dir, assignment, clock)
            results.append(result)
            clock += timedelta(
                milliseconds=result.duration_ms + rng.randint(MIN_GAP_MS, MAX_GAP_MS)
            )

    catalog_order = {test.name: index for index, test in enumerate(catalog)}
    results.sort(key=lambda result: catalog_order[result.test.name])
    (run_dir / "results.xml").write_bytes(results_xml(run_id, results))
    _write_json(run_dir / "metadata.json", _night_metadata(lab, seed, night, run_id, results))
    return results


def _run_and_write(
    rng: random.Random, run_id: str, run_dir: Path, assignment: Assignment, start: datetime
) -> TestResult:
    run = run_test(rng, assignment)
    test, station = assignment.test, assignment.station.name
    header = render_header(run_id, test.name, station, assignment.firmware, test.band, start)
    log_path = f"logs/{station}/{test.name}.log"
    _write_text(
        run_dir / log_path,
        render_log(header, list(run.lines), render_footer(run.result, run.duration_ms)),
    )
    return TestResult(test, station, assignment.firmware, start, run.duration_ms, log_path)


def _lab_summary(lab: Lab, catalog: tuple[TestCase, ...]) -> dict[str, object]:
    return {
        "stations": [{"name": s.name, "bands": list(s.bands)} for s in lab.stations],
        "bands": list(lab.bands),
        "firmware_releases": [{"version": r.version, "night": r.night} for r in lab.firmware],
        "suite_releases": [{"version": r.version, "night": r.night} for r in lab.suite],
        "tests": [
            {"name": t.name, "family": t.family, "variant": t.variant, "band": t.band}
            for t in catalog
        ],
    }


def _night_metadata(
    lab: Lab, seed: int, night: int, run_id: str, results: list[TestResult]
) -> dict[str, object]:
    return {
        "run_id": run_id,
        "night": night,
        "date": night_date(lab, night).isoformat(),
        "suite_version": suite_on(lab, night),
        "firmware": {s.name: firmware_on(lab, i, night) for i, s in enumerate(lab.stations)},
        "tests": len(results),
        "seed": seed,
        "generator": f"tl_simulator {__version__}",
    }


def _write_json(path: Path, data: dict[str, object]) -> None:
    _write_text(path, json.dumps(data, indent=2) + "\n")


def _write_text(path: Path, text: str) -> None:
    # Always "\n" line endings, so output is byte-identical on Windows and Linux.
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
