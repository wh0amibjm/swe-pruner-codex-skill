param(
  [Parameter(Mandatory = $true)][string]$File,
  [Parameter(Mandatory = $true)][string]$Query,
  [string]$Url = "",
  [double]$Threshold = 0.5,
  [int]$ContextLines = 1,
  [int]$MaxBytes = 0,
  [string]$Label = "",
  [switch]$AlwaysKeepFirstFrags,
  [int]$ChunkOverlapTokens = 50,
  [switch]$NoLineNumbers,
  [switch]$NoHeader,
  [switch]$Json
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = Join-Path $scriptDir "pcat.py"

$effectiveUrl = $Url
if ($effectiveUrl -eq "") {
  if ($env:PRUNER_URL) {
    $effectiveUrl = $env:PRUNER_URL
  } else {
    $effectiveUrl = "http://127.0.0.1:8000/prune"
  }
}

$connectUrl = $effectiveUrl
try {
  $u0 = [Uri]$effectiveUrl
  # `0.0.0.0` is a bind-all address, not a connectable host. Use loopback for client calls.
  if ($u0.Host -eq "0.0.0.0") {
    $b0 = [UriBuilder]$u0
    $b0.Host = "127.0.0.1"
    $connectUrl = $b0.Uri.AbsoluteUri
  }
} catch {
  $connectUrl = $effectiveUrl
}

$healthUrl = $connectUrl.TrimEnd("/")
if ($healthUrl.EndsWith("/prune")) {
  $healthUrl = $healthUrl.Substring(0, $healthUrl.Length - "/prune".Length) + "/health"
} else {
  $healthUrl = $healthUrl + "/health"
}

function Test-PrunerHealth {
  param([string]$HealthUrl)
  try {
    $resp = Invoke-RestMethod -Method Get -Uri $HealthUrl -TimeoutSec 2 -ErrorAction Stop
    return $true
  } catch {
    return $false
  }
}

function Start-PrunerServer {
  param([string]$PruneUrl)
  try {
    $u = [Uri]$PruneUrl
    $port = if ($u.Port -gt 0) { $u.Port } else { 8000 }
    $host = if ($u.Host) { $u.Host } else { "127.0.0.1" }

    $isLocalHost = $host -in @("127.0.0.1", "localhost", "::1", "0.0.0.0")
    if (!$isLocalHost) {
      return
    }

    $bindHost = $host
    if ($bindHost -eq "0.0.0.0") {
      $bindHost = "127.0.0.1"
    }

    $serverScript = Join-Path $scriptDir "run_server.ps1"
    if (!(Test-Path $serverScript)) {
      return
    }

    $argList = @(
      "-NoProfile",
      "-ExecutionPolicy", "Bypass",
      "-File", $serverScript,
      "-Host", $bindHost,
      "-Port", "$port"
    )

    $psExe = (Get-Command pwsh -ErrorAction SilentlyContinue).Source
    if (!$psExe) {
      $psExe = (Get-Command powershell -ErrorAction SilentlyContinue).Source
    }
    if (!$psExe) {
      return
    }

    Start-Process -FilePath $psExe -ArgumentList $argList -WindowStyle Hidden | Out-Null
  } catch {
    # Ignore start failures; pcat.py will show a helpful connection error message.
  }
}

if (!(Test-PrunerHealth -HealthUrl $healthUrl)) {
  Start-PrunerServer -PruneUrl $connectUrl
  $sw = [System.Diagnostics.Stopwatch]::StartNew()
  while ($sw.Elapsed.TotalSeconds -lt 20) {
    Start-Sleep -Milliseconds 500
    if (Test-PrunerHealth -HealthUrl $healthUrl) {
      break
    }
  }
}

$argsList = @("--file", $File, "--query", $Query, "--threshold", "$Threshold", "--context-lines", "$ContextLines", "--chunk-overlap-tokens", "$ChunkOverlapTokens")
if ($connectUrl -ne "") { $argsList += @("--url", $connectUrl) }
if ($MaxBytes -gt 0) { $argsList += @("--max-bytes", "$MaxBytes") }
if ($Label -ne "") { $argsList += @("--label", $Label) }
if ($AlwaysKeepFirstFrags) { $argsList += "--always-keep-first-frags" }
if ($NoLineNumbers) { $argsList += "--no-line-numbers" }
if ($NoHeader) { $argsList += "--no-header" }
if ($Json) { $argsList += "--json" }

python $py @argsList
