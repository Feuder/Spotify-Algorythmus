$ErrorActionPreference = "Stop"

try {
    docker info *> $null
} catch {
    Write-Error "Docker Desktop ist nicht gestartet. Docker Desktop starten und dieses Skript erneut ausfuehren."
}

docker compose up --build -d
docker compose ps
Write-Host ""
Write-Host "Resonanz ist unter http://127.0.0.1:3000 erreichbar."

