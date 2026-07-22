# Task Scheduler-friendly launcher for the Daily Research Loop.
# v0: run this MANUALLY. Scheduling is wired last (see README).
#
# Resolves a Python 3.12+ interpreter (the engine's hard requirement) without
# depending on the current shell's PATH, then runs the orchestrator and logs.
#
# Manual run:   pwsh -File research-loop\scripts\run-daily.ps1 run
#               pwsh -File research-loop\scripts\run-daily.ps1 validate
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$orchestrator = Join-Path $root "src\orchestrator.py"

# --- Resolve Python 3.12+ (current user's per-user path first, then discovery) ---
# Derived from $env:LOCALAPPDATA so it is user-agnostic (no baked-in username).
$py = $null
$localAppData = if ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { Join-Path $env:USERPROFILE "AppData\Local" }
$candidates = @(
  (Join-Path $localAppData "Programs\Python\Python313\python.exe"),
  (Join-Path $localAppData "Programs\Python\Python312\python.exe")
)
foreach ($c in $candidates) { if (Test-Path $c) { $py = $c; break } }
if (-not $py) {
  foreach ($name in @("python3.13", "python3.12", "py")) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($cmd) { $py = $cmd.Source; break }
  }
}
if (-not $py) { throw "No Python 3.12+ found. Install Python 3.13 and retry." }

# --- Ensure gh is reachable so the engine's GitHub source activates --------
$ghDir = "C:\Program Files\GitHub CLI"
if ((Test-Path $ghDir) -and ($env:PATH -notlike "*$ghDir*")) {
  $env:PATH = "$ghDir;$env:PATH"
}

# --- Run + log -------------------------------------------------------------
$logDir = Join-Path $root "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir ("run-" + (Get-Date -Format "yyyy-MM-dd") + ".log")

$cmdArgs = if ($args.Count -gt 0) { $args } else { @("run") }
Write-Output "[$(Get-Date -Format o)] launching: $py $orchestrator $cmdArgs" | Tee-Object -FilePath $log -Append
& $py $orchestrator @cmdArgs 2>&1 | Tee-Object -FilePath $log -Append
exit $LASTEXITCODE
