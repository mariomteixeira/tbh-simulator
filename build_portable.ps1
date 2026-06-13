# Gera o pacote PORTATIL do TBH Copilot (pra PC sem Python):
#   - Python embutido (embeddable, ~15MB) + dependencias ja instaladas
#   - o app (server, simulador, painel web buildado, gamedata, launcher)
#   - auto-update apontando pro seu GitHub (botao "Atualizar" no launcher)
#
# Uso (uma vez, no SEU PC):
#   powershell -ExecutionPolicy Bypass -File build_portable.ps1 -Repo usuario/tbh-simulator
#
# Sai em dist-portable\TBH-Copilot (e um .zip do lado). Copie/extraia no PC
# dela e rode "TBH Copilot.bat". Updates: voce da git push; ela clica Atualizar.

param(
  [Parameter(Mandatory = $true)][string]$Repo,   # ex: usuario/tbh-simulator
  [string]$Branch = "main",
  [string]$PyVersion = "3.12.10"
)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$out = Join-Path $root "dist-portable\TBH-Copilot"

Write-Host "== TBH Copilot portatil ==" -ForegroundColor Cyan
if (Test-Path $out) { Remove-Item $out -Recurse -Force }
New-Item -ItemType Directory -Force $out | Out-Null

# -- 1) Python embutido -------------------------------------------------------
$pyDir = Join-Path $out "python"
$pyZip = Join-Path $env:TEMP "python-$PyVersion-embed-amd64.zip"
if (-not (Test-Path $pyZip)) {
  Write-Host "baixando Python $PyVersion embeddable..."
  Invoke-WebRequest "https://www.python.org/ftp/python/$PyVersion/python-$PyVersion-embed-amd64.zip" -OutFile $pyZip
}
Expand-Archive $pyZip -DestinationPath $pyDir -Force

# habilita o site-packages no runtime embutido (descomenta 'import site')
$pth = Get-ChildItem $pyDir -Filter "python*._pth" | Select-Object -First 1
(Get-Content $pth.FullName) -replace '^#\s*import site', 'import site' | Set-Content $pth.FullName

# -- 2) pip + dependencias ----------------------------------------------------
$getpip = Join-Path $env:TEMP "get-pip.py"
if (-not (Test-Path $getpip)) {
  Invoke-WebRequest "https://bootstrap.pypa.io/get-pip.py" -OutFile $getpip
}
& "$pyDir\python.exe" $getpip --no-warn-script-location | Out-Null
& "$pyDir\python.exe" -m pip install -r (Join-Path $root "requirements.txt") `
    --no-warn-script-location --quiet
Write-Host "dependencias instaladas"

# -- 3) arquivos do app -------------------------------------------------------
$files = @("server.py", "simulator.py", "store.py", "tbh_tracker.py",
           "tbh_painel.pyw", "updater.py", "fetch_gamedata.py",
           "requirements.txt", "README.md")
foreach ($f in $files) { Copy-Item (Join-Path $root $f) $out }
Copy-Item (Join-Path $root "gamedata") (Join-Path $out "gamedata") -Recurse
New-Item -ItemType Directory -Force (Join-Path $out "frontend") | Out-Null
Copy-Item (Join-Path $root "frontend\dist") (Join-Path $out "frontend\dist") -Recurse

# -- 4) config de update + versao --------------------------------------------
@{ repo = $Repo; branch = $Branch } | ConvertTo-Json |
  Set-Content (Join-Path $out "update_config.json")
$sha = (git -C $root rev-parse HEAD).Trim()
Set-Content (Join-Path $out ".version") $sha

# -- 5) atalho de inicio ------------------------------------------------------
@'
@echo off
start "" "%~dp0python\pythonw.exe" "%~dp0tbh_painel.pyw"
'@ | Set-Content (Join-Path $out "TBH Copilot.bat") -Encoding ascii

# -- 6) zip -------------------------------------------------------------------
$zip = Join-Path $root "dist-portable\TBH-Copilot.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path $out -DestinationPath $zip
Write-Host ""
Write-Host "PRONTO:" -ForegroundColor Green
Write-Host "  pasta: $out"
Write-Host "  zip:   $zip  ($([math]::Round((Get-Item $zip).Length/1MB,1)) MB)"
Write-Host ""
Write-Host "No PC dela: extrair o zip e rodar 'TBH Copilot.bat'."
Write-Host "Updates: voce da git push; ela clica em 'Atualizar' no painel."
