param(
    [string]$DebugBundle = "test_inputs\phase6b_debug_bundle.json",
    [int]$Runs = 3,
    [int]$MaxProjects = 3,
    [int]$MaxBullets = 3,
    [string]$AnalysisModel = "openai/gpt-5.6-terra",
    [ValidateSet("low", "medium", "high")]
    [string]$ReasoningEffort = "low"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $DebugBundle)) {
    throw "Debug bundle not found: $DebugBundle"
}

python -m scripts.run_tailoring_stability_trial `
    --debug-bundle $DebugBundle `
    --runs $Runs `
    --max-projects $MaxProjects `
    --max-bullets $MaxBullets `
    --analysis-model $AnalysisModel `
    --reasoning-effort $ReasoningEffort `
    --strict

exit $LASTEXITCODE
