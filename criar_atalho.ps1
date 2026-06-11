# Cria (ou atualiza) o atalho "TBH Copilot" na Area de Trabalho, apontando pro
# painelzinho de controle (tbh_painel.pyw) rodando com pythonw (sem terminal).
#
# Uso:  powershell -ExecutionPolicy Bypass -File criar_atalho.ps1

$root = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }

# pythonw.exe do mesmo Python que esta no PATH (o que tem fastapi/uvicorn)
$pyExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if ($pyExe) {
    $pyw = Join-Path (Split-Path -Parent $pyExe) "pythonw.exe"
} else {
    $pyw = (Get-Command pythonw -ErrorAction SilentlyContinue).Source
}
if (-not $pyw -or -not (Test-Path $pyw)) {
    Write-Error "pythonw.exe nao encontrado. Instale o Python e tente de novo."
    exit 1
}

$desktop = [Environment]::GetFolderPath("Desktop")
$lnk = Join-Path $desktop "TBH Copilot.lnk"

$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut($lnk)
$s.TargetPath = $pyw
$s.Arguments = '"' + (Join-Path $root "tbh_painel.pyw") + '"'
$s.WorkingDirectory = $root
$s.IconLocation = "$pyw,0"
$s.Description = "Painel de controle do TBH Copilot"
$s.Save()

Write-Host "Atalho criado: $lnk"
Write-Host "  -> $pyw `"$(Join-Path $root 'tbh_painel.pyw')`""
