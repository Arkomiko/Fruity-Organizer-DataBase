# Собирает портативный dist\FODB.exe. Нужен Python 3.13 с Tcl/Tk 8.6.
# Порядок: окружение, зависимости, значки, тесты, сборка.
$root = $PSScriptRoot
$venv = Join-Path $root ".venv-build"
$python = Join-Path $venv "Scripts\python.exe"

if (-not (Test-Path $python)) {
    py -3.13 -m venv $venv
}
& $python -m pip install --quiet --disable-pip-version-check -r (Join-Path $root "requirements-build.txt")
& $python (Join-Path $root "tools\gen_assets.py")
& $python -m unittest discover -s (Join-Path $root "tests")
if ($LASTEXITCODE -ne 0) { throw "Tests failed" }
& $python -m PyInstaller --noconfirm --clean --log-level WARN --distpath (Join-Path $root "dist") --workpath (Join-Path $root "build") (Join-Path $root "FODB.spec")
if ($LASTEXITCODE -ne 0) { throw "Build failed" }
# Промежуточные файлы сборки больше не нужны: результат лежит в dist.
Remove-Item (Join-Path $root "build") -Recurse -Force -ErrorAction SilentlyContinue
Get-Item (Join-Path $root "dist\FODB.exe") | Select-Object Name, @{ Name = "SizeMB"; Expression = { [math]::Round($_.Length / 1MB, 2) } }
