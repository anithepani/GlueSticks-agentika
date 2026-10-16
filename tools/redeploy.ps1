# Rebuild + deploy Witness on Alternate Clouds after a git push.
#
# Alternate Clouds never rebuilds on a plain `git push`. This script performs the
# supported order: Rebuild -> wait for the new image -> Deploy -> verify /health.
#
# Prerequisite: an authenticated CLI. If `acc whoami --json` is not authenticated,
# run `npx -y @alternatefutures/acc login --email` first (unauthenticated commands
# open an interactive login and hang).
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File tools/redeploy.ps1
#   powershell -ExecutionPolicy Bypass -File tools/redeploy.ps1 -Region eu

param(
    [string]$Project = "witness-agentika",
    [string]$ServiceId = "cmvbc3e5706exe41rs9g87kmn",
    [string]$Url = "https://alternate-echo-whale-5578-github-app.alternatefutures.ai",
    [string]$Region = "",
    [int]$BuildTimeoutMinutes = 45
)

$ErrorActionPreference = "Stop"

function Acc {
    npx -y @alternatefutures/acc @args
}

Write-Host "1/4 Checking CLI authentication ..."
$who = Acc whoami --json | Out-String
if ($who -notmatch '"authenticated"\s*:\s*true') {
    Write-Host "Not authenticated. Run first:"
    Write-Host "  npx -y @alternatefutures/acc login --email"
    exit 1
}

$full = (git rev-parse HEAD).Trim()
$short = $full.Substring(0, 7)
Write-Host "2/4 Rebuilding service $ServiceId for commit $short ..."
Acc services -p $Project rebuild $ServiceId

Write-Host "    Waiting for the builder to publish image tag $short (up to $BuildTimeoutMinutes min) ..."
$deadline = (Get-Date).AddMinutes($BuildTimeoutMinutes)
$info = ""
do {
    Start-Sleep -Seconds 45
    $info = Acc services -p $Project info $ServiceId | Out-String
    if ($info -match $short) { break }
} while ((Get-Date) -lt $deadline)

if ($info -notmatch $short) {
    Write-Host "Build did not publish an image for $short within the timeout."
    Write-Host "Check the build in the dashboard, then re-run this script."
    exit 1
}

Write-Host "3/4 Deploying ..."
if ($Region -ne "") {
    Acc services -p $Project deploy $ServiceId --region $Region -y
} else {
    Acc services -p $Project deploy $ServiceId -y
}

Write-Host "4/4 Verifying $Url/health ..."
Start-Sleep -Seconds 20
try {
    $resp = Invoke-WebRequest -Uri "$Url/health" -UseBasicParsing -TimeoutSec 30
    Write-Host "HTTP $($resp.StatusCode): $($resp.Content)"
} catch {
    Write-Host "Health check did not return 200 yet: $($_.Exception.Message)"
    Write-Host "A stale provider ingress can return nginx 404/503; re-run deploy (not just Save)."
    exit 1
}
