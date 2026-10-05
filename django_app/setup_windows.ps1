# Project-local setup; never removes attendance or face data.
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskPython = Join-Path $PSScriptRoot 'venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    & py -3.12 -m venv (Join-Path $PSScriptRoot 'venv')
    if ($LASTEXITCODE -ne 0) { throw 'Cannot create Python 3.12 virtual environment.' }
}
$cpuRuntime = & $taskPython -c "from importlib.metadata import distributions; print(any(d.metadata['Name'].lower() == 'onnxruntime' for d in distributions()))"
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect the project environment.' }
if ($cpuRuntime -eq 'True') {
    throw 'CPU onnxruntime is already installed. Stop server, then remove only that distribution in this venv before running setup. Do not install CPU and GPU runtimes together.'
}
& $taskPython -m pip install --no-deps -r (Join-Path $PSScriptRoot 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& $taskPython manage.py check
if ($LASTEXITCODE -ne 0) { throw 'Django system checks failed.' }
Write-Host 'Setup complete. Next: .\venv\Scripts\python.exe manage.py migrate'
Write-Host 'Then: .\venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000 --noreload'
