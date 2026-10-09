# Devlog

What broke during development and how it was fixed. Newest entries first.

Entry format:

```
## YYYY-MM-DD – <Jira key>: <short title>
**What broke:** ...
**Fix:** ...
```

---

## 2026-10-09 – TL-12: Python 3.15 and ruff

**What broke:** Ruff 0.16 warns on every run that its Python 3.15 support is still under
development when `target-version = "py315"`.
**Fix:** The project requires Python 3.15, but ruff targets `py314` for now. That setting only
affects which syntax upgrades ruff suggests. Switch to `py315` once ruff supports it fully.
