"""The test catalog: test cases named after public 3GPP procedures.

5 procedure families x 6 variants x 5 bands = 150 test cases.
"""

from dataclasses import dataclass

SENT = ">>"  # tester -> device
RECEIVED = "<<"  # device -> tester

DEFAULT_TIMEOUT_MS = 2000
FAST_TIMEOUT_MS = 500
# Tests that check tight timing. They use the fast limit and are the ones that can be flaky.
TIMING_SENSITIVE = {("HO", "PINGPONG"), ("MEAS", "PERIODIC")}


@dataclass(frozen=True)
class Step:
    direction: str
    message: str


@dataclass(frozen=True)
class TestCase:
    __test__ = False  # stop pytest from collecting this class

    name: str
    family: str
    variant: str
    band: str
    steps: tuple[Step, ...]
    timeout_ms: int = DEFAULT_TIMEOUT_MS


REGISTRATION = (
    Step(RECEIVED, "RRCSetupRequest"),
    Step(SENT, "RRCSetup"),
    Step(RECEIVED, "RegistrationRequest"),
    Step(SENT, "AuthenticationRequest"),
    Step(RECEIVED, "AuthenticationResponse"),
    Step(SENT, "SecurityModeCommand"),
    Step(RECEIVED, "SecurityModeComplete"),
    Step(SENT, "RegistrationAccept"),
    Step(RECEIVED, "RegistrationComplete"),
)

# Every family except REG registers the device first, then runs its own procedure.
FAMILY_STEPS: dict[str, tuple[Step, ...]] = {
    "REG": REGISTRATION,
    "PDU": REGISTRATION
    + (
        Step(RECEIVED, "PDUSessionEstablishmentRequest"),
        Step(SENT, "RRCReconfiguration"),
        Step(RECEIVED, "RRCReconfigurationComplete"),
        Step(SENT, "PDUSessionEstablishmentAccept"),
    ),
    "HO": REGISTRATION
    + (
        Step(SENT, "RRCReconfiguration"),
        Step(RECEIVED, "MeasurementReport"),
        Step(SENT, "RRCReconfiguration"),
        Step(RECEIVED, "RRCReconfigurationComplete"),
    ),
    "RRC": REGISTRATION
    + (
        Step(SENT, "RRCReconfiguration"),
        Step(RECEIVED, "RRCReconfigurationComplete"),
        Step(SENT, "UECapabilityEnquiry"),
        Step(RECEIVED, "UECapabilityInformation"),
    ),
    "MEAS": REGISTRATION
    + (
        Step(SENT, "RRCReconfiguration"),
        Step(RECEIVED, "RRCReconfigurationComplete"),
        Step(RECEIVED, "MeasurementReport"),
        Step(RECEIVED, "MeasurementReport"),
    ),
}

FAMILY_VARIANTS: dict[str, tuple[str, ...]] = {
    "REG": ("INITIAL", "GUTI", "MOBILITY", "PERIODIC", "EMERGENCY", "REREG"),
    "PDU": ("IPV4", "IPV6", "IPV4V6", "MULTI", "MODIFY", "RELEASE"),
    "HO": ("INTRA_FREQ", "INTER_FREQ", "INTER_BAND", "CONDITIONAL", "PINGPONG", "LOADED"),
    "RRC": ("SCELL_ADD", "SCELL_RELEASE", "BWP_SWITCH", "DRX", "MIMO_LAYERS", "SRS"),
    "MEAS": ("A1", "A2", "A3", "A4", "A5", "PERIODIC"),
}


def build_catalog(bands: tuple[str, ...]) -> tuple[TestCase, ...]:
    return tuple(
        TestCase(
            name=f"TC_{family}_{variant}_{band.upper()}",
            family=family,
            variant=variant,
            band=band,
            steps=FAMILY_STEPS[family],
            timeout_ms=_timeout_for(family, variant),
        )
        for family, variants in FAMILY_VARIANTS.items()
        for variant in variants
        for band in bands
    )


def _timeout_for(family: str, variant: str) -> int:
    return FAST_TIMEOUT_MS if (family, variant) in TIMING_SENSITIVE else DEFAULT_TIMEOUT_MS
