#!/usr/bin/env pwsh
<#
.SYNOPSIS
Kotlin module build/test/benchmark for Hermes x-runtime.
#>

param(
  [ValidateSet('build','test','benchmark','clean')]
  [string]$Command = 'test'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$KotlinRoot = (Get-Item $PSScriptRoot).Parent.FullName
$Kotlin = Join-Path $KotlinRoot 'dist/kotlinc'
$Out = Join-Path $KotlinRoot 'out'
$TestOut = Join-Path $KotlinRoot 'test-out'
$Stdlib = Join-Path $Kotlin 'lib/kotlin-stdlib.jar'
$TestStdlib = Join-Path $Kotlin 'lib/kotlin-test-1.5.31.jar'
$Coroutines = Join-Path $KotlinRoot 'lib/kotlinx-coroutines-core-jvm.jar'
$Compiler = Join-Path $Kotlin 'lib/kotlin-compiler.jar'

$mainSources = @(
  'src/jvmMain/kotlin/hermes/abi/StableAbi.kt',
  'src/jvmMain/kotlin/hermes/abi/WorkerLifecycle.kt',
  'src/jvmMain/kotlin/hermes/abi/CapabilityDsl.kt',
  'src/jvmMain/kotlin/hermes/abi/HotReloadChecker.kt',
  'src/jvmMain/kotlin/hermes/abi/WorkerRegistration.kt'
)
$testSources = @(
  'src/jvmTest/kotlin/hermes/abi/StableAbiTest.kt',
  'src/jvmTest/kotlin/hermes/abi/StableAbiCoroutineTest.kt',
  'src/jvmTest/kotlin/hermes/abi/WorkerLifecycleTest.kt',
  'src/jvmTest/kotlin/hermes/abi/CapabilityFlowTest.kt',
  'src/jvmTest/kotlin/hermes/abi/HotReloadEdgeCaseTest.kt',
  'src/jvmTest/kotlin/hermes/integration/SupervisorIntegrationTest.kt'
)

switch ($Command) {
  'clean' {
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue @($Out, $TestOut)
  }
  'build' {
    New-Item -ItemType Directory -Force -Path @($Out, $TestOut) | Out-Null
    $mainCmd = 'java -cp "' + $Compiler + '" org.jetbrains.kotlin.cli.jvm.K2JVMCompiler -jvm-target 21 -cp "' + $Stdlib + '" -d "' + $Out + '" ' + ($mainSources -join ' ')
    $testCp = "$TestOut;$Out;$Stdlib;$TestStdlib;$Coroutines"
    $testCmd = 'java -cp "' + $Compiler + '" org.jetbrains.kotlin.cli.jvm.K2JVMCompiler -jvm-target 21 -cp "' + $testCp + '" -d "' + $TestOut + '" ' + ($testSources -join ' ')
    Push-Location $KotlinRoot
    try {
      & cmd.exe /c $mainCmd
      & cmd.exe /c $testCmd
    }
    finally {
      Pop-Location
    }
  }
  'test' {
    & $PSCommandPath build
    $runCp = "$TestOut;$Out;$Stdlib;$TestStdlib;$Coroutines"
    & java --enable-native-access=ALL-UNNAMED -cp $runCp hermes.abi.StableAbiTest
    & java --enable-native-access=ALL-UNNAMED -cp $runCp hermes.abi.StableAbiCoroutineTest
    & java --enable-native-access=ALL-UNNAMED -cp $runCp hermes.abi.WorkerLifecycleTest
    & java --enable-native-access=ALL-UNNAMED -cp $runCp hermes.abi.CapabilityFlowTest
    & java --enable-native-access=ALL-UNNAMED -cp $runCp hermes.abi.HotReloadEdgeCaseTest
    $integrationClass = Join-Path $TestOut 'hermes/integration/SupervisorIntegrationTest.class'
    if (Test-Path $integrationClass) {
      $supervisorUrl = $env:HERMES_SUPERVISOR_URL
      if (-not [string]::IsNullOrWhiteSpace($supervisorUrl)) {
        & java --enable-native-access=ALL-UNNAMED -cp $runCp hermes.integration.SupervisorIntegrationTest
      }
    }
    Write-Host "`nKotlin tests passed."
  }
  'benchmark' {
    & $PSCommandPath build
    $benchCp = "$Out;$Stdlib"
    $benchCmd = 'java -cp "' + $Compiler + '" org.jetbrains.kotlin.cli.jvm.K2JVMCompiler -jvm-target 21 -cp "' + $benchCp + '" -d "' + $Out + '" ' + ($mainSources -join ' ')
    Push-Location $KotlinRoot
    try {
      & cmd.exe /c $benchCmd
    }
    finally {
      Pop-Location
    }
    $runCp = "$TestOut;$Out;$Stdlib;$TestStdlib;$Coroutines"
    & java --enable-native-access=ALL-UNNAMED -cp $runCp hermes.abi.StableAbiBenchmark
  }
}
