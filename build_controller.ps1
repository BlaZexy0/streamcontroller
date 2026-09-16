param(
    [ValidateSet("onedir", "onefile", "all")]
    [string]$Mode = "all"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PyInstaller = Join-Path $ProjectRoot ".venv\Scripts\pyinstaller.exe"

if (-not (Test-Path -LiteralPath $PyInstaller)) {
    throw "PyInstaller fehlt. Zuerst requirements-build.txt installieren."
}

if ($Mode -in @("onedir", "all")) {
    & $PyInstaller --clean --noconfirm (Join-Path $ProjectRoot "soomfon_controller.spec")
    if ($LASTEXITCODE -ne 0) { throw "onedir-Build fehlgeschlagen" }
}

if ($Mode -in @("onefile", "all")) {
    & $PyInstaller --clean --noconfirm (Join-Path $ProjectRoot "soomfon_controller_onefile.spec")
    if ($LASTEXITCODE -ne 0) { throw "onefile-Build fehlgeschlagen" }
}
