# Clojure Runtime Tests

## Requirement
These tests need a local Clojure runtime with `deps.edn` support.
This repo includes a vendored Babashka runtime under `bb_dist/` for Windows
execution. If you want a system-wide install instead, install Babashka from
https://github.com/babashka/babashka and ensure `bb` is on PATH.

## Run
From this directory with vendored bb:
- `D:\Projects\HermesAgentExpansion\bb_dist\bb.exe -cp src;test -m hermes.protocol-test`

With Clojure CLI:
- `clojure -M:test`

## Current status
Local test execution is verified on this host:
- `x-runtime/clojure/test/hermes/protocol_test.clj` passes via vendored Babashka.

## Windows CI commands
```powershell
# Clojure via vendored Babashka
D:\Projects\HermesAgentExpansion\bb_dist\bb.exe -cp src;test -m hermes.protocol-test

# Clojure/Java stable ABI via Foreign Function API
cd D:\Projects\HermesAgentExpansion\x-runtime\clojure\test\hermes
javac StableAbiTest.java
java --enable-native-access=ALL-UNNAMED StableAbiTest

# TypeScript via template test runner
cd D:\Projects\HermesAgentExpansion\x-runtime\templates\typescript
npm test
```
