$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
& "$projectRoot\.venv\Scripts\python.exe" "$projectRoot\controller.py" --config "$projectRoot\config.json"
