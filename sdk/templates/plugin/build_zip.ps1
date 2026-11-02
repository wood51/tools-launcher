param([Parameter(Mandatory=$true)][string]$Project)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath $Project).Path
$manifest = Get-Content -LiteralPath (Join-Path $projectRoot 'extension.json') -Raw | ConvertFrom-Json
if ($manifest.id -notmatch '^[a-z0-9][a-z0-9_-]*$' -or $manifest.version -notmatch '^\d+\.\d+\.\d+$') {
  throw 'Identifiant ou version du manifeste invalide.'
}
$outputs = Join-Path $projectRoot 'outputs'
New-Item -ItemType Directory -Path $outputs -Force | Out-Null
$destination = Join-Path $outputs ($manifest.id + '-' + $manifest.version + '.zip')
$temporaryZip = Join-Path $outputs ([guid]::NewGuid().ToString('N') + '.tmp.zip')
$tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
$stage = Join-Path $tempRoot ('tools-sdk-' + [guid]::NewGuid().ToString('N'))
$package = Join-Path $stage $manifest.id
New-Item -ItemType Directory -Path $package -Force | Out-Null
try {
  Get-ChildItem -LiteralPath $projectRoot -Recurse -File | Where-Object {
    $relative = $_.FullName.Substring($projectRoot.Length).TrimStart('\')
    $relative -notmatch '(^|\\)(\.venv|venv|data|tests|outputs|__pycache__|\.git|\.pytest_cache)(\\|$)' -and
    $_.Name -notin @('.env', 'SIGNATURE.json', 'PROJECT.md', 'AGENTS.md') -and
    $_.Name -notlike '.env.*' -and
    $_.Extension -notin @('.pyc', '.zip', '.key', '.pem', '.pfx', '.p12', '.bak')
  } | ForEach-Object {
    $relative = $_.FullName.Substring($projectRoot.Length).TrimStart('\')
    $target = Join-Path $package $relative
    New-Item -ItemType Directory -Path (Split-Path $target) -Force | Out-Null
    Copy-Item -LiteralPath $_.FullName -Destination $target
  }
  Compress-Archive -LiteralPath $package -DestinationPath $temporaryZip
  Move-Item -LiteralPath $temporaryZip -Destination $destination -Force
} finally {
  if (Test-Path -LiteralPath $temporaryZip) { Remove-Item -LiteralPath $temporaryZip -Force }
  $resolvedStage = [System.IO.Path]::GetFullPath($stage)
  if (-not $resolvedStage.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
      (Split-Path $resolvedStage -Leaf) -notlike 'tools-sdk-*') { throw 'Dossier temporaire inattendu.' }
  if (Test-Path -LiteralPath $resolvedStage) { Remove-Item -LiteralPath $resolvedStage -Recurse -Force }
}
Write-Host "ZIP local non signe : $destination"
