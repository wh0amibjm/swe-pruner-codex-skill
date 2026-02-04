param(
  [string]$ModelPath = "",
  [int]$Port = 8000,
  [string]$Host = "127.0.0.1"
)

if ($ModelPath -eq "") {
  if ($env:SWEPRUNER_MODEL_PATH) {
    $ModelPath = $env:SWEPRUNER_MODEL_PATH
  } else {
    $ModelPath = "$HOME\.cache\swe-pruner\model"
  }
}

$weights = Join-Path $ModelPath "model.safetensors"
if (!(Test-Path $weights)) {
  Write-Error "Missing model weights: $weights`nRun: powershell -ExecutionPolicy Bypass -File scripts/download_model.ps1 -Out `"$ModelPath`""
  exit 1
}

$cmd = Get-Command swe-pruner -ErrorAction SilentlyContinue
if ($cmd) {
  & $cmd.Source serve --host $Host --port $Port --model-path $ModelPath
} else {
  python -m swe_pruner.online_serving serve --host $Host --port $Port --model-path $ModelPath
}

