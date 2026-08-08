#!/usr/bin/env python3
"""Local CI/CD pipeline runner with no GitHub dependency.

Replicates selected verification steps as local jobs:
- source checkout/prepare
- cache restore/store for Rust
- Rust build/test
- Python test execution with PYTHONPATH=.
- optional language steps, skipped when unavailable
- status reporting in terminal and optional JSON artifact
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional


REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = REPO_ROOT / ".cache" / "local-ci"
RUST_CACHE = CACHE_DIR / "rust"


@dataclass
class StepResult:
    name: str
    ok: bool = True
    started: float = field(default_factory=time.time)
    finished: float = field(default_factory=time.time)
    duration: float = 0.0
    output: str = ""

    def finish(self, ok: bool, output: str) -> "StepResult":
        self.finished = time.time()
        self.duration = self.finished - self.started
        self.ok = ok
        self.output = output
        return self


@dataclass
class JobContext:
    matrix: dict[str, str]
    cache: bool = True
    clean: bool = False
    artifacts_dir: Optional[Path] = None

    def cache_key(self, name: str, inputs: list[str]) -> str:
        blob = json.dumps({"matrix": self.matrix, "inputs": inputs}, sort_keys=True, default=str)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def run(
    cmd: list[str],
    cwd: Path = REPO_ROOT,
    env: Optional[dict[str, str]] = None,
    timeout: Optional[int] = None,
) -> StepResult:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    start = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            env=merged_env,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return StepResult(name=" ".join(cmd), ok=True, started=start).finish(True, proc.stdout + proc.stderr)
    except FileNotFoundError as exc:
        return StepResult(name=" ".join(cmd), ok=False, started=start).finish(False, f"missing executable: {exc.filename}")
    except subprocess.CalledProcessError as exc:
        return StepResult(name=" ".join(cmd), ok=False, started=start).finish(False, exc.stdout + exc.stderr)
    except subprocess.TimeoutExpired as exc:
        return StepResult(name=" ".join(cmd), ok=False, started=start).finish(False, f"timeout after {timeout}s: {exc.cmd}")


def cache_restore(step: str, key: str) -> tuple[bool, Path]:
    store = CACHE_DIR / step / key
    if store.exists():
        return True, store
    return False, store


def cache_save(step: str, key: str, source: Path) -> None:
    target = CACHE_DIR / step / key
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.exists():
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)


def job_verify(ctx: JobContext) -> list[StepResult]:
    results: list[StepResult] = []
    results.append(run(["git", "rev-parse", "--show-toplevel"], cwd=REPO_ROOT))

    cargo = shutil.which("cargo")
    python_exec = sys.executable if shutil.which(sys.executable) else shutil.which("python") or shutil.which("python3")
    has_pip = bool(python_exec)

    rust_key = ctx.cache_key("rust", ["x-runtime/rust/Cargo.toml", "x-runtime/rust/supervisor/Cargo.toml"])
    hit, rust_store = cache_restore("rust", rust_key)
    if hit and ctx.cache:
        results.append(StepResult(name="Restore Rust cache", ok=True, output=f"cache={rust_store}").finish(True, ""))
    else:
        results.append(StepResult(name="Restore Rust cache", ok=True, output="miss").finish(True, ""))

    if cargo:
        rust = run([cargo, "build", "--release", "-p", "hermes-runtime-protocol"], cwd=REPO_ROOT / "x-runtime" / "rust")
        rust.name = "Build Rust protocol crate"
        results.append(rust)
        if rust.ok and ctx.cache:
            cache_save("rust", rust_key, RUST_CACHE)
    else:
        results.append(StepResult(name="Build Rust protocol crate", ok=False).finish(False, "cargo not found; skipping"))
        results.append(StepResult(name="Run Rust supervisor tests", ok=False).finish(False, "cargo not found; skipping"))

    if python_exec and has_pip:
        pip = run([python_exec, "-m", "pip", "install", "--upgrade", "pip"])
        pip.name = "Install pip"
        results.append(pip)
        deps = run([python_exec, "-m", "pip", "install", "pytest", "pyyaml", "httpx"])
        deps.name = "Install Python dependencies"
        results.append(deps)
    else:
        results.append(StepResult(name="Install pip", ok=False).finish(False, "python/pip not found; skipping"))
        results.append(StepResult(name="Install Python dependencies", ok=False).finish(False, "python/pip not found; skipping"))

    if cargo:
        abi = run([cargo, "build", "--release", "-p", "hermes-runtime-abi"], cwd=REPO_ROOT / "x-runtime" / "rust")
    abi.name = "Build Rust ABI crate"
    results.append(abi)
    py = run([sys.executable, "-m", "pytest", "tests/x-runtime", "-q"], cwd=REPO_ROOT, env={"PYTHONPATH": str(REPO_ROOT)})
    py.name = "Run Python x-runtime tests"
    results.append(py)

    node_modules = REPO_ROOT / "x-runtime" / "typescript" / "node_modules"
    ts_enabled = os.environ.get("LOCAL_CI_ENABLE_TS") == "1"
    ts_ready = node_modules.exists() and any(p.is_dir() and p.name != ".vite" for p in node_modules.iterdir())
    install_ts = None
    ts = None
    if ts_ready or ts_enabled:
        install_ts = run(["cmd.exe", "/c", "npm install --no-audit --no-fund"], cwd=REPO_ROOT / "x-runtime" / "typescript", timeout=60)
        install_ts.name = "Install TypeScript dependencies"
        results.append(install_ts)
        if install_ts.ok:
            ts = run(["cmd.exe", "/c", "npx vitest run"], cwd=REPO_ROOT / "x-runtime" / "typescript", timeout=120)
            ts.name = "Run TypeScript tests"
            results.append(ts)
    if not ts_ready or not ts:
        skip_ts = StepResult(name="Skip TypeScript tests", ok=True).finish(True, "TypeScript tests unavailable in this environment")
        results.append(skip_ts)

    kotlin_zip = REPO_ROOT / "x-runtime" / "kotlin" / "dist" / "kotlin-compiler.zip"
    kotlin_dir = REPO_ROOT / "x-runtime" / "kotlin" / "dist" / "kotlinc"
    kotlin_key = ctx.cache_key("kotlin", [str(kotlin_zip) if kotlin_zip.exists() else "missing"])
    hit, kotlin_store = cache_restore("kotlin", kotlin_key)
    if hit and ctx.cache and kotlin_dir.exists():
        results.append(StepResult(name="Restore Kotlin cache", ok=True, output=f"cache={kotlin_store}").finish(True, ""))
    elif not kotlin_dir.exists() and kotlin_zip.exists():
        unzip = run(["unzip", "-q", "-o", str(kotlin_zip)], cwd=REPO_ROOT)
        unzip.name = "Install Kotlin compiler"
        results.append(unzip)
        if unzip.ok:
            cache_save("kotlin", kotlin_key, kotlin_dir)

    kotlin_bin = None
    if os.name == "nt":
        for candidate in [
            REPO_ROOT / "x-runtime" / "kotlin" / "dist" / "kotlinc" / "bin" / "kotlinc.bat",
            REPO_ROOT / "x-runtime" / "kotlin" / "dist" / "kotlinc" / "bin" / "kotlinc",
        ]:
            if candidate.exists():
                kotlin_bin = candidate
                break
    else:
        candidate = REPO_ROOT / "x-runtime" / "kotlin" / "dist" / "kotlinc" / "bin" / "kotlinc"
        if candidate.exists():
            kotlin_bin = candidate

    if not kotlin_bin:
        results.append(StepResult(name="Check Kotlin compiler", ok=True).finish(True, "kotlinc not available on this host; skipping Kotlin tests"))
        kotlin_skip = StepResult(name="Skip Kotlin tests", ok=True)
        kotlin_skip = kotlin_skip.finish(True, "kotlinc not available on this host")
        results.append(kotlin_skip)
        return results

    build_script = REPO_ROOT / "x-runtime" / "kotlin" / "scripts" / ("build.ps1" if os.name == "nt" else "build.sh")
    if not build_script.exists():
        results.append(StepResult(name="Run Kotlin tests", ok=False).finish(False, f"missing {build_script}"))
        return results

    if os.name != "nt":
        run(["chmod", "+x", str(build_script)], cwd=REPO_ROOT)

    cmd = ["pwsh", str(build_script), "test"] if os.name == "nt" else ["bash", str(build_script), "test"]
    start = time.time()
    try:
        proc = subprocess.run(cmd, cwd=str(REPO_ROOT / "x-runtime" / "kotlin"), check=True, capture_output=True, text=True)
        results.append(StepResult(name="Run Kotlin tests", ok=True, started=start).finish(True, proc.stdout + proc.stderr))
    except FileNotFoundError as exc:
        results.append(StepResult(name="Run Kotlin tests", ok=False, started=start).finish(False, f"missing executable: {exc.filename}"))
    except subprocess.CalledProcessError as exc:
        results.append(StepResult(name="Run Kotlin tests", ok=False, started=start).finish(False, exc.stdout + exc.stderr))

    return results


def job_kotlin_verify(ctx: JobContext) -> list[StepResult]:
    results: list[StepResult] = []
    results.append(run(["git", "rev-parse", "--show-toplevel"], cwd=REPO_ROOT))

    kotlin_zip = REPO_ROOT / "x-runtime" / "kotlin" / "dist" / "kotlin-compiler.zip"
    kotlin_dir = REPO_ROOT / "x-runtime" / "kotlin" / "dist" / "kotlinc"
    kotlin_key = ctx.cache_key("kotlin", [str(kotlin_zip) if kotlin_zip.exists() else "missing"])
    hit, kotlin_store = cache_restore("kotlin", kotlin_key)
    if hit and ctx.cache and kotlin_dir.exists():
        results.append(StepResult(name="Restore Kotlin cache", ok=True, output=f"cache={kotlin_store}").finish(True, ""))
    elif not kotlin_dir.exists() and kotlin_zip.exists():
        unzip = run(["unzip", "-q", "-o", str(kotlin_zip)], cwd=REPO_ROOT)
        unzip.name = "Install Kotlin compiler"
        results.append(unzip)
        if unzip.ok:
            cache_save("kotlin", kotlin_key, kotlin_dir)

    kotlin_bin = None
    if os.name == "nt":
        for candidate in [
            REPO_ROOT / "x-runtime" / "kotlin" / "dist" / "kotlinc" / "bin" / "kotlinc.bat",
            REPO_ROOT / "x-runtime" / "kotlin" / "dist" / "kotlinc" / "bin" / "kotlinc",
        ]:
            if candidate.exists():
                kotlin_bin = candidate
                break
    else:
        candidate = REPO_ROOT / "x-runtime" / "kotlin" / "dist" / "kotlinc" / "bin" / "kotlinc"
        if candidate.exists():
            kotlin_bin = candidate

    if not kotlin_bin:
        results.append(StepResult(name="Check Kotlin compiler", ok=True).finish(True, "kotlinc not available on this host; skipping Kotlin tests"))
        kotlin_skip = StepResult(name="Skip Kotlin tests", ok=True)
        kotlin_skip = kotlin_skip.finish(True, "kotlinc not available on this host")
        results.append(kotlin_skip)
        return results

    build_script = REPO_ROOT / "x-runtime" / "kotlin" / "scripts" / ("build.ps1" if os.name == "nt" else "build.sh")
    if not build_script.exists():
        results.append(StepResult(name="Run Kotlin tests", ok=False).finish(False, f"missing {build_script}"))
        return results

    if os.name != "nt":
        run(["chmod", "+x", str(build_script)], cwd=REPO_ROOT)

    cmd = ["pwsh", str(build_script), "test"] if os.name == "nt" else ["bash", str(build_script), "test"]
    start = time.time()
    try:
        proc = subprocess.run(cmd, cwd=str(REPO_ROOT / "x-runtime" / "kotlin"), check=True, capture_output=True, text=True)
        results.append(StepResult(name="Run Kotlin tests", ok=True, started=start).finish(True, proc.stdout + proc.stderr))
    except FileNotFoundError as exc:
        results.append(StepResult(name="Run Kotlin tests", ok=False, started=start).finish(False, f"missing executable: {exc.filename}"))
    except subprocess.CalledProcessError as exc:
        results.append(StepResult(name="Run Kotlin tests", ok=False, started=start).finish(False, exc.stdout + exc.stderr))

    return results


def job_verify(ctx: JobContext) -> list[StepResult]:
    results: list[StepResult] = []
    results.append(run(["git", "rev-parse", "--show-toplevel"], cwd=REPO_ROOT))

    cargo = shutil.which("cargo")
    python_exec = sys.executable if shutil.which(sys.executable) else shutil.which("python") or shutil.which("python3")
    has_pip = bool(python_exec)

    rust_key = ctx.cache_key("rust", ["x-runtime/rust/Cargo.toml", "x-runtime/rust/supervisor/Cargo.toml"])
    hit, rust_store = cache_restore("rust", rust_key)
    if hit and ctx.cache:
        results.append(StepResult(name="Restore Rust cache", ok=True, output=f"cache={rust_store}").finish(True, ""))
    else:
        results.append(StepResult(name="Restore Rust cache", ok=True, output="miss").finish(True, ""))

    if cargo:
        rust = run([cargo, "build", "--release", "-p", "hermes-runtime-protocol"], cwd=REPO_ROOT / "x-runtime" / "rust")
        rust.name = "Build Rust protocol crate"
        results.append(rust)
        if rust.ok and ctx.cache:
            cache_save("rust", rust_key, RUST_CACHE)
    else:
        results.append(StepResult(name="Build Rust protocol crate", ok=False).finish(False, "cargo not found; skipping"))
        results.append(StepResult(name="Run Rust supervisor tests", ok=False).finish(False, "cargo not found; skipping"))

    if python_exec and has_pip:
        pip = run([python_exec, "-m", "pip", "install", "--upgrade", "pip"])
        pip.name = "Install pip"
        results.append(pip)
        deps = run([python_exec, "-m", "pip", "install", "pytest", "pyyaml", "httpx"])
        deps.name = "Install Python dependencies"
        results.append(deps)
    else:
        results.append(StepResult(name="Install pip", ok=False).finish(False, "python/pip not found; skipping"))
        results.append(StepResult(name="Install Python dependencies", ok=False).finish(False, "python/pip not found; skipping"))

    if cargo:
        abi = run([cargo, "build", "--release", "-p", "hermes-runtime-abi"], cwd=REPO_ROOT / "x-runtime" / "rust")
    abi.name = "Build Rust ABI crate"
    results.append(abi)
    py = run([sys.executable, "-m", "pytest", "tests/x-runtime", "-q"], cwd=REPO_ROOT, env={"PYTHONPATH": str(REPO_ROOT)})
    py.name = "Run Python x-runtime tests"
    results.append(py)

    install_ts = run(["cmd.exe", "/c", "npm install --no-audit --no-fund"], cwd=REPO_ROOT / "x-runtime" / "typescript", timeout=60)
    install_ts.name = "Install TypeScript dependencies"
    results.append(install_ts)
    ts = None
    node_modules = REPO_ROOT / "x-runtime" / "typescript" / "node_modules"
    ts_enabled = os.environ.get("LOCAL_CI_ENABLE_TS") == "1"
    ts_ready = node_modules.exists() and any(p.is_dir() and p.name != ".vite" for p in node_modules.iterdir())
    if ts_ready or ts_enabled:
        ts = run(["cmd.exe", "/c", "npx vitest run"], cwd=REPO_ROOT / "x-runtime" / "typescript", timeout=120)
        ts.name = "Run TypeScript tests"
        results.append(ts)
    if not ts_ready or not ts:
        skip_ts = StepResult(name="Skip TypeScript tests", ok=True).finish(True, "TypeScript tests unavailable in this environment")
        results.append(skip_ts)

    results.extend(job_kotlin_verify(ctx))

    bb = shutil.which("bb")
    clojure = shutil.which("clojure")
    clojure_dir = REPO_ROOT / "x-runtime" / "clojure"
    clj = None
    if bb:
        clj = run(["bb", "-cp", "src;test", "-m", "hermes.protocol-test"], cwd=clojure_dir)
        clj.name = "Run Clojure tests"
        results.append(clj)
    elif clojure:
        clj = run([clojure, "-M:test"], cwd=clojure_dir)
        clj.name = "Run Clojure tests"
        results.append(clj)
    else:
        results.append(StepResult(name="Skip Clojure tests", ok=True).finish(True, "bb/clojure not available; skipping"))

    return results
    if not ctx.artifacts_dir:
        return None
    ctx.artifacts_dir.mkdir(parents=True, exist_ok=True)
    artifact = ctx.artifacts_dir / f"{job_name}-{ctx.matrix.get('os','local')}.json"
    payload = {
        "job": job_name,
        "matrix": ctx.matrix,
        "results": [
            {
                "name": r.name,
                "ok": r.ok,
                "duration_s": round(r.duration, 3),
                "output": r.output[-4000:],
            }
            for r in results
        ],
        "ok": all(r.ok for r in results),
    }
    artifact.write_text(json.dumps(payload, indent=2))
    return artifact


def render(results: list[StepResult], title: str) -> None:
    width = min(shutil.get_terminal_size(fallback=(80, 24)).columns, 120)
    print("=" * width)
    print(f"LOCAL CI: {title}")
    print("=" * width)
    for result in results:
        status = "PASS" if result.ok else "FAIL"
        print(f"[{status}] {result.name} ({result.duration:.2f}s)")
        if not result.ok or result.output:
            snippet = (result.output or "").strip().splitlines()[-8:]
            for line in snippet:
                print(f"      {line}")
    print("-" * width)
    print(f"Overall: {'PASS' if all(r.ok for r in results) else 'FAIL'}")


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local CI/CD pipeline runner")
    parser.add_argument("--job", default="verify", choices=["verify", "all", "kotlin-verify"])
    parser.add_argument("--matrix", default='{"os":"local"}')
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--artifacts-dir", default=str(CACHE_DIR / "artifacts"))
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    try:
        matrix = json.loads(args.matrix)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid --matrix JSON: {exc}")

    ctx = JobContext(
        matrix=matrix,
        cache=not args.no_cache,
        clean=args.clean,
        artifacts_dir=Path(args.artifacts_dir),
    )

    job_name = args.job
    if job_name == "all":
        job_name = "verify"

    if job_name == "verify":
        results = job_verify(ctx)
    elif job_name == "kotlin-verify":
        results = job_kotlin_verify(ctx)
    else:
        raise SystemExit(f"Unknown job: {job_name}")

    render(results, job_name)
    artifact = write_artifacts(ctx, results, job_name)
    if artifact:
        print(f"Artifact: {artifact}")
    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
