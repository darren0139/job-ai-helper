param(
    [Parameter(Mandatory=$true)][string]$SourceRepository,
    [Parameter(Mandatory=$true)][string]$NewCandidate,
    [string]$PythonExecutable = 'python'
)
$ErrorActionPreference = 'Stop'
$bundle = $PSScriptRoot
$manifest = Get-Content (Join-Path $bundle 'manifest.json') -Raw | ConvertFrom-Json
if (Test-Path -LiteralPath $NewCandidate) { throw 'Choose a new, nonexistent directory.' }
git clone --no-hardlinks --single-branch --branch master -c core.autocrlf=false $SourceRepository $NewCandidate
if ($LASTEXITCODE) { throw 'Independent clone failed' }
if ((git -C $NewCandidate rev-parse HEAD) -ne $manifest.target_commit) { throw 'Master identity changed; review required' }
& $PythonExecutable -B (Join-Path $bundle 'prepare_master_text.py') $NewCandidate --check
if ($LASTEXITCODE) { throw 'Baseline preparation preflight failed' }
& $PythonExecutable -B (Join-Path $bundle 'prepare_master_text.py') $NewCandidate
if ($LASTEXITCODE) { throw 'Baseline preparation failed' }
foreach ($name in $manifest.application_order) {
    $patch = Join-Path $bundle $name
    if ((Get-FileHash -LiteralPath $patch -Algorithm SHA256).Hash.ToLowerInvariant() -ne $manifest.patches.$name) {
        throw "Changed patch: $name"
    }
    git -C $NewCandidate apply --check --whitespace=error $patch
    if ($LASTEXITCODE) { throw "Incompatible patch: $name" }
    git -C $NewCandidate apply --whitespace=error $patch
    if ($LASTEXITCODE) { throw "Failed applying: $name" }
}
Write-Host 'Applied B0, B1, B2, B3 to an independent checkout. No commit or merge performed.'
