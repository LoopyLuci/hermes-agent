#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
if [ ! -d "$REPO_ROOT/.git" ]; then
  REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "$SCRIPT_DIR/../../..")"
fi
REPO_ROOT="$(cd "$REPO_ROOT" && pwd)"
KOTLIN="$(cd "$REPO_ROOT/x-runtime/kotlin/dist/kotlinc" && pwd)"
OUT="$REPO_ROOT/x-runtime/kotlin/out"
TEST_OUT="$REPO_ROOT/x-runtime/kotlin/test-out"
STDLIB="$KOTLIN/lib/kotlin-stdlib.jar"
TEST_STDLIB="$KOTLIN/lib/kotlin-test.jar"
COROUTINES="$REPO_ROOT/x-runtime/kotlin/lib/kotlinx-coroutines-core-jvm.jar"

MAIN_SOURCES=(
  src/jvmMain/kotlin/hermes/abi/StableAbi.kt
  src/jvmMain/kotlin/hermes/abi/WorkerLifecycle.kt
  src/jvmMain/kotlin/hermes/abi/CapabilityDsl.kt
  src/jvmMain/kotlin/hermes/abi/HotReloadChecker.kt
  src/jvmMain/kotlin/hermes/abi/WorkerRegistration.kt
)
TEST_SOURCES=(
  src/jvmTest/kotlin/hermes/abi/StableAbiTest.kt
  src/jvmTest/kotlin/hermes/abi/StableAbiCoroutineTest.kt
  src/jvmTest/kotlin/hermes/abi/WorkerLifecycleTest.kt
  src/jvmTest/kotlin/hermes/abi/CapabilityFlowTest.kt
  src/jvmTest/kotlin/hermes/abi/HotReloadEdgeCaseTest.kt
  src/jvmTest/kotlin/hermes/integration/SupervisorIntegrationTest.kt
)
JAVA_RUNNER="src/jvmTest/java/hermes/abi/StableAbiBenchmarkRunner.java"

mkdir -p "$OUT" "$TEST_OUT"

cd "$REPO_ROOT/x-runtime/kotlin"

if ! command -v kotlinc >/dev/null 2>&1; then
  if [ -x "$KOTLIN/bin/kotlinc" ]; then
    export PATH="$KOTLIN/bin:$PATH"
  fi
fi

if ! command -v kotlinc >/dev/null 2>&1; then
  echo "kotlinc not found; install Kotlin to $KOTLIN or add it to PATH" >&2
  exit 1
fi

kotlinc -jvm-target 21 -cp "$STDLIB" -d "$OUT" "${MAIN_SOURCES[@]}"

TEST_CP="$TEST_OUT:$OUT:$STDLIB:$TEST_STDLIB:$COROUTINES"
kotlinc -jvm-target 21 -cp "$TEST_CP" -d "$TEST_OUT" "${TEST_SOURCES[@]}"

if [ -f "$JAVA_RUNNER" ]; then
  javac -cp "$OUT:$STDLIB" -d "$TEST_OUT" "$JAVA_RUNNER"
fi

RUN_CP="$TEST_OUT:$OUT:$STDLIB:$TEST_STDLIB:$COROUTINES"
java --enable-native-access=ALL-UNNAMED -cp "$RUN_CP" hermes.abi.StableAbiTest
java --enable-native-access=ALL-UNNAMED -cp "$RUN_CP" hermes.abi.StableAbiCoroutineTest
java --enable-native-access=ALL-UNNAMED -cp "$RUN_CP" hermes.abi.WorkerLifecycleTest
java --enable-native-access=ALL-UNNAMED -cp "$RUN_CP" hermes.abi.CapabilityFlowTest
java --enable-native-access=ALL-UNNAMED -cp "$RUN_CP" hermes.abi.HotReloadEdgeCaseTest
if [ -f "$TEST_OUT/hermes/integration/SupervisorIntegrationTest.class" ]; then
  HERMES_SUPERVISOR_URL="http://127.0.0.1:18181" \
  HERMES_ABI_DLL="$REPO_ROOT/x-runtime/rust/target/release/hermes_runtime_abi.dll" \
  java --enable-native-access=ALL-UNNAMED -cp "$RUN_CP" hermes.integration.SupervisorIntegrationTest
fi

echo "Kotlin tests passed."
