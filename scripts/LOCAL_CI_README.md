# Local CI/CD Pipeline

This directory contains the fully local, GitHub-independent CI/CD pipeline for the Hermes Agent expansion.

## Runner

- `scripts/local_ci.py` — Python-based pipeline runner with no GitHub dependency.

## Usage

```bash
PYTHONPATH=. python scripts/local_ci.py --job verify --matrix '{"os":"local"}' --no-cache
PYTHONPATH=. python scripts/local_ci.py --job kotlin-verify --matrix '{"os":"local"}' --no-cache
```

### Arguments

- `--job verify` — runs the local verification job
- `--job kotlin-verify` — runs only the Kotlin verification job
- `--matrix '{"os":"local"}'` — matrix metadata for the job
- `--no-cache` — disables artifact caching
- `--artifacts-dir .cache/local-ci/artifacts` — optional JSON artifact output

## Jobs

- `verify` / `all`: Rust, Python, TypeScript, Kotlin, Clojure
- `kotlin-verify`: Kotlin-only verification with local compiler cache

## Behavior notes

- TypeScript tests are run only when TypeScript dependencies are available.
  - Set `LOCAL_CI_ENABLE_TS=1` to attempt `npm install` + `npx vitest run`.
  - If dependencies are missing, the step is skipped cleanly.
- Clojure tests run when `bb` or `clojure` is available.
  - If neither is available, the step is skipped cleanly.

## Features

- Rust build/test with local cache
- Python x-runtime tests with `PYTHONPATH=.`
- TypeScript tests via local `vitest` when dependencies are available
- Kotlin tests via bundled `kotlinc` wrapper
- Clojure tests via `bb` or Clojure CLI
- Terminal status reporting and JSON artifacts

## Design

This pipeline replaces GitHub Actions features with local equivalents:
- Source checkout: local git
- Caching: filesystem-based `.cache/local-ci/`
- Test execution: direct subprocess calls
- Status reporting: terminal output + JSON artifacts

## Validation

Run the pipeline locally to validate all x-runtime components:
- Python tests: `pytest tests/x-runtime -q`
- Rust tests: `cargo test -p hermes-runtime-supervisor --lib`
- Kotlin tests: `bash x-runtime/kotlin/scripts/build.sh test`
- Clojure tests: `bb -cp src;test -m hermes.protocol-test` in `x-runtime/clojure/`
