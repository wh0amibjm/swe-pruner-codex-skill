param(
  [string]$Out = "$HOME\.cache\swe-pruner\model",
  [string]$Repo = "ayanami-kitasan/code-pruner",
  [string]$Revision = ""
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = Join-Path $scriptDir "download_model.py"

$argsList = @("--repo", $Repo, "--out", $Out)
if ($Revision -ne "") {
  $argsList += @("--revision", $Revision)
}

python $py @argsList

