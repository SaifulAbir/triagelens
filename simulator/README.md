# Simulator

A synthetic 5G device test lab. It generates nightly test campaigns (JUnit-style results plus
logs) that the rest of TriageLens ingests, triages and evaluates against.

Everything it produces is **synthetic**. The log format and test framework are invented for this
project; test names follow public 3GPP procedures.

## Run it

```bash
pip install -e simulator
python -m tl_simulator generate --seed 42 --nights 20
```

Output goes to `data/synthetic/generated/` (gitignored). Add `--force` to replace an existing
campaign, or `--out <folder>` to write somewhere else.

**The same seed always produces byte-identical output**, on any OS. Labels and eval results depend
on this.

## Output

```
data/synthetic/generated/
├── lab.json                        # stations, bands, releases, test catalog
├── night-08/
│   ├── metadata.json               # date, suite version, firmware per station, failure count
│   ├── results.xml                 # JUnit-style; station, firmware, band, log path as properties
│   └── logs/STN-03/TC_HO_INTRA_FREQ_N3.log
└── ground_truth/                   # labels: never give this folder to the system under test
    ├── faults.json                 # every root cause in the scenario
    ├── split.json                  # build nights vs eval nights
    └── night-08.json               # one record per failing test
```

The log format is specified in [docs/log-format.md](../docs/log-format.md).

## Faults and ground truth

Every failure is caused on purpose by a fault from the scenario in `faults.py`, so the true cause
of every failure is known. **Labels come only from this scenario, never from an LLM.**

| Root cause | Category | Where / when | Ticket | Novel |
|---|---|---|---|---|
| RC-DEV-01 | device bug | Firmware 2.2, PDU tests on n28: no RRCReconfigurationComplete. Fixed in 2.3 | ISS-0103 | |
| RC-DEV-02 | device bug | Firmware 2.3, inter-frequency/inter-band handovers: RRC re-establishment | | yes |
| RC-INF-01 | test infrastructure | STN-04, nights 4 and 16: instrument connection lost | ISS-0088 | |
| RC-INF-02 | test infrastructure | STN-02, nights 9–10, TDD bands: license expired | | |
| RC-INF-03 | test infrastructure | STN-05, nights 14–17, HO/MEAS: RF path degrades | | yes |
| RC-SCR-01 | test script | Suite 4.1 (night 10+), MEAS A3: limit 200ms instead of 2000ms | ISS-0120 | |
| RC-CFG-01 | configuration | STN-01, night 6: station profile overrides the band | | |
| RC-CFG-02 | configuration | STN-03, night 18, TDD bands: wrong TDD pattern | | yes |
| RC-FLK-01 | flaky | HO PINGPONG and MEAS PERIODIC tests: ~5% miss a 500ms limit | ISS-0042 | |

- **Ticket** is a known issue in the legacy ticket system (TL-18). It is a separate field from
  the category: a known issue can still be a device bug.
- **Novel** faults have wordings that are not in any signature and appear only in eval nights.
- **Time split:** nights 1–10 are build nights (signatures and rules may be built from them);
  nights 11–20 are eval nights. Every category appears in both.
- **Overlapping faults:** if two faults hit the same test, the one that breaks it earliest wins
  (setup → radio → protocol → check), because the test never gets further.
- **Prompt injection:** some failing logs (RC-DEV-02, RC-INF-01) contain a line with instructions
  aimed at an AI. The label records `has_injection: true`; the category stays the same.

One ground-truth record per failing test:

```json
{"run_id": "night-14", "test": "TC_HO_INTER_FREQ_N3", "station": "STN-03", "firmware": "2.3",
 "band": "n3", "log": "logs/STN-03/TC_HO_INTER_FREQ_N3.log", "category": "device bug",
 "root_cause": "RC-DEV-02", "expected_cluster": "RC-DEV-02", "ticket": null, "novel": true,
 "has_injection": true, "evidence_lines": [35, 36]}
```

`evidence_lines` are line numbers in the log file that show the root cause.

## The lab

| | |
|---|---|
| Stations | 6 (`STN-01` to `STN-06`), each supporting a subset of bands; every band is on at least 2 stations |
| Bands | n1, n3, n28, n41, n78 |
| Firmware | 2.1 from night 1, 2.2 from night 7, 2.3 from night 13; rolled out 2 stations per night |
| Test suite | 4.0 from night 1, 4.1 from night 10; all stations update at once |
| Test catalog | 5 procedure families (REG, PDU, HO, RRC, MEAS) x 6 variants x 5 bands = 150 tests |
| Nights | 20 by default; every night runs the full catalog |

## Architecture

```mermaid
flowchart LR
    CLI[cli.py] --> CMP[campaign.py<br/>per night]
    LAB[lab.py<br/>stations, releases] --> CMP
    CAT[catalog.py<br/>150 test cases] --> CMP
    CMP --> SCH[schedule.py<br/>test → station]
    CMP --> FLT[faults.py<br/>which fault hits?]
    FLT --> EFF[effects.py<br/>how it breaks]
    CMP --> RUN[runner.py<br/>one test run]
    EFF --> RUN
    RUN --> NOI[noise.py<br/>background lines]
    RUN --> INJ[injection.py]
    RUN --> FMT[logformat.py<br/>render / parse]
    CMP --> JU[junit.py<br/>results.xml]
    CMP --> GT[groundtruth.py<br/>labels]
    CMP --> OUT[(night-NN/)]
    GT --> TRUTH[(ground_truth/)]
```

For each night, `campaign.py`:

1. creates a random generator seeded from `(seed, night)`,
2. asks `schedule.py` to give each test to a station that supports its band,
3. for each test, asks `faults.py` which fault (if any) breaks it, and `effects.py` how,
4. runs each station's queue in order with `runner.py`, advancing that station's clock,
5. writes each log with `logformat.py`, then `results.xml`, `metadata.json` and the night's
   ground truth.

| Module | Responsibility |
|---|---|
| `lab.py` | Lab model and which firmware / suite version is active on a given night |
| `catalog.py` | Test cases and their protocol steps (`>>` to the device, `<<` from it) |
| `schedule.py` | Assigns each test to a station for one night |
| `faults.py` | The fault scenario and which fault hits a test (earliest stage wins) |
| `effects.py` | How each kind of fault changes a test run, and which lines are evidence |
| `runner.py` | Simulates one test: setup, protocol steps with checks, failure, teardown; merges in noise |
| `noise.py` | Keepalives, instrument polls, harmless `W` and `E` lines |
| `injection.py` | Prompt-injection lines hidden in some failing logs |
| `groundtruth.py` | Per-failure labels, the fault list and the build/eval split |
| `logformat.py` | The invented log format: render and parse (the parser is the format's test) |
| `junit.py` | JUnit-style XML, one `<testsuite>` per procedure family |
| `campaign.py` | Orchestrates a night and writes files |
| `cli.py` | `generate` command |

## Design rules

- **One random generator per night**, seeded from `(seed, night)`. Changing one night never
  changes another: a fault added to night 3 leaves every other night byte-identical, and any night
  can be generated on its own.
- **No hidden randomness.** Nothing uses the global `random` module, the clock or `hash()`.
- **Unix line endings everywhere**, so files are byte-identical on Windows and Linux.
- **Standard library only.** No dependencies to install or pin.

## Numbers (seed 42, 20 nights)

3,000 test runs, 297 failures (about 10%) from 9 root causes, 39 of them with a prompt-injection
line. Every category appears in both build and eval nights; novel faults start on night 13.
