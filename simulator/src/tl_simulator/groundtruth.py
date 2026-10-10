"""Ground truth: the true cause of every failing test.

Labels come only from the fault scenario, never from an LLM. They are written to a separate
ground_truth/ folder so the system under test never sees them.
"""

from dataclasses import asdict, dataclass

from tl_simulator.faults import Fault
from tl_simulator.junit import TestResult
from tl_simulator.lab import Lab
from tl_simulator.runner import SimulatedRun

GROUND_TRUTH_DIR = "ground_truth"


@dataclass(frozen=True)
class FailureLabel:
    run_id: str
    test: str
    station: str
    firmware: str
    band: str
    log: str
    category: str
    root_cause: str
    expected_cluster: str  # failures with the same root cause belong in one cluster
    ticket: str | None
    novel: bool
    has_injection: bool
    evidence_lines: tuple[int, ...]


def label_for(run_id: str, result: TestResult, fault: Fault, run: SimulatedRun) -> FailureLabel:
    return FailureLabel(
        run_id=run_id,
        test=result.test.name,
        station=result.station,
        firmware=result.firmware,
        band=result.test.band,
        log=result.log_path,
        category=fault.category,
        root_cause=fault.root_cause,
        expected_cluster=fault.root_cause,
        ticket=fault.ticket,
        novel=fault.novel,
        has_injection=run.has_injection,
        evidence_lines=run.evidence_lines,
    )


def labels_summary(labels: list[FailureLabel]) -> list[dict[str, object]]:
    return [asdict(label) for label in labels]


def faults_summary(faults: tuple[Fault, ...]) -> list[dict[str, object]]:
    return [asdict(fault) for fault in faults]


def split_summary(lab: Lab, nights: int) -> dict[str, object]:
    build = min(lab.build_nights, nights)
    return {
        "build_nights": list(range(1, build + 1)),
        "eval_nights": list(range(build + 1, nights + 1)),
        "rule": "Signatures and rules may only be built from build nights. "
        "Evals run on eval nights, which include novel faults.",
    }
