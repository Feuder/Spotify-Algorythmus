$ErrorActionPreference = "Stop"

Push-Location backend
try {
    if (-not (Test-Path ".venv")) {
        py -3.12 -m venv .venv
        .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
    }
    .\.venv\Scripts\ruff.exe check app tests
    .\.venv\Scripts\pytest.exe
} finally {
    Pop-Location
}

Push-Location frontend
try {
    npm install
    npm run lint
    npm run build
} finally {
    Pop-Location
}

docker compose config --quiet
Write-Host "Alle lokalen Prüfungen bestanden."
