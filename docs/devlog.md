# Devlog

What broke during development and how it was fixed. Newest entries first.

Entry format:

```
## YYYY-MM-DD – <Jira key>: <short title>
**What broke:** ...
**Fix:** ...
```

---

## 2026-10-10 – TL-16: background noise on zero-length tests

**What broke:** A test checking a zero-length run found a "harmless warning" at offset 0. The
noise generator put occasional warnings anywhere in `[0, duration]`, and for duration 0 that is
still offset 0.
**Fix:** `background_lines` returns nothing when the duration is 0 or less. A run with no time
has no room for background noise.

## 2026-10-10 – TL-16: JUnit time attribute for short tests

**What broke:** A first version formatted the JUnit `time` attribute by stripping leading zeros
from `0012.345`. Durations under one second would have become `.500`. Caught in review before
any test ran.
**Fix:** A separate `_seconds()` helper using integer division (`500 -> "0.500"`), with a test.

## 2026-10-10 – TL-16: ruff sorted our own package as third-party

**What broke:** `ruff check` flagged the import blocks in the simulator tests. Ruff didn't know
`tl_simulator` is ours, so it wanted it in the same group as `pytest`.
**Fix:** `src = [".", "simulator/src"]` in the root `[tool.ruff]` settings.

## 2026-10-09 – TL-12: Python 3.15 and ruff

**What broke:** Ruff 0.16 warns on every run that its Python 3.15 support is still under
development when `target-version = "py315"`.
**Fix:** The project requires Python 3.15, but ruff targets `py314` for now. That setting only
affects which syntax upgrades ruff suggests. Switch to `py315` once ruff supports it fully.
