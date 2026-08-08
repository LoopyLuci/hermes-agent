#!/usr/bin/env pwsh
<#
.SYNOPSIS
Unified cross-language verification for Hermes x-runtime ABI and tests.
#>

param(
  [switch]$SkipKotlin
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = 'D:\Projects\HermesAgentExpansion'
Push-Location $RepoRoot

try {
  Write-Host "`n[1/4] Building Rust ABI..."
  Push-Location (Join-Path $RepoRoot 'x-runtime/rust')
  try {
    cargo build --release -p hermes-runtime-abi
  } finally {
    Pop-Location
  }

  Write-Host "`n[2/4] Running Python x-runtime tests..."
  python -m unittest discover -s (Join-Path $RepoRoot 'tests/x-runtime') -v

  Write-Host "`n[3/4] Running TypeScript tests..."
  Push-Location (Join-Path $RepoRoot 'x-runtime/typescript')
  try {
    npx vitest run
  } finally {
    Pop-Location
  }

  Write-Host "`n[4/4] Running Java/Kotlin ABI tests..."
  $javaHome = 'C:\Program Files\Android\openjdk\jdk-21.0.8'
  $kotlin = Join-Path $RepoRoot 'x-runtime/kotlin/dist/kotlinc'
  $env:JAVA_HOME = $javaHome
  $env:PATH = Join-Path $javaHome 'bin;' + $env:PATH

  $abiDll = Join-Path $RepoRoot 'x-runtime/rust/target/release/hermes_runtime_abi.dll'
  if (-not (Test-Path $abiDll)) { throw "ABI DLL not found: $abiDll" }

  $javaTestDir = Join-Path $RepoRoot 'x-runtime/kotlin/src/jvmTest/kotlin/hermes'
  if (Test-Path (Join-Path $javaTestDir 'integration/SupervisorIntegrationTest.kt')) {
    Write-Host "Java/Kotlin supervisor integration present, deferring build to build.ps1"
  } else {
    Write-Warning "Java/Kotlin supervisor integration test not found at $javaTestDir/integration/SupervisorIntegrationTest.kt"
  }

  if (-not $SkipKotlin) {
    $buildScript = Join-Path $kotlin 'scripts/build.ps1'
    if (-not (Test-Path $buildScript)) { throw "Kotlin build script not found: $buildScript" }
    Push-Location (Join-Path $RepoRoot 'x-runtime/kotlin')
    try {
      & $buildScript test
    } finally {
      Pop-Location
    }
  } else {
    Write-Host "Skipping Kotlin tests due to -SkipKotlin"
  }

  Write-Host "`nCross-language verification passed."
} finally {
  Pop-Location
}
