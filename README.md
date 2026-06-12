# Resonanz

Resonanz ist der lokal betriebene persönliche KI-Musikassistent aus der
Projektspezifikation. Er synchronisiert Spotify-Hördaten, findet neue Musik,
ergänzt nullable Musikmerkmale, erstellt nachvollziehbare Playlists und bietet
ein deutsches responsives Dashboard.

## Schnellstart

1. Docker Desktop starten.
2. Nur die Datei [`.env`](./.env) im Projektstamm öffnen und die gewünschten
   Zugangsdaten eintragen. Andere Konfigurationsdateien sind nicht nötig.
3. In PowerShell ausführen:

   ```powershell
   .\scripts\start.ps1
   ```

4. [http://127.0.0.1:3000](http://127.0.0.1:3000) öffnen.
5. Für Spotify
   [http://127.0.0.1:8000/api/auth/spotify/login](http://127.0.0.1:8000/api/auth/spotify/login)
   öffnen und die Verbindung erlauben.

Ohne externe Schlüssel startet Resonanz im Demo-Modus. Playlist-Generator,
Dashboard, Profile, Merkmalskorrekturen und Algorithmus sind dadurch sofort
testbar.

## Zentrale `.env`

Die Root-[`.env`](./.env) ist absichtlich die einzige Laufzeitkonfiguration.
Docker Compose lädt sie für PostgreSQL, Backend und Worker. Das Frontend erhält
keine Secrets und kommuniziert ausschließlich über `/api`.

Pflicht für Spotify:

- `SPOTIFY_CLIENT_ID`
- `SPOTIFY_CLIENT_SECRET`
- Redirect URI im Spotify Dashboard:
  `http://127.0.0.1:8000/api/auth/spotify/callback`

Optional:

- `LASTFM_API_KEY` für Discovery
- `GETSONGBPM_API_KEY` für BPM und Tonart
- `MUSICBRAINZ_CONTACT_EMAIL` für MusicBrainz und AcousticBrainz
- `OPENAI_API_KEY` für Structured Outputs bei manuellen Texteingaben

BPM- und Tonartdaten werden von
<a href="https://getsongbpm.com/">GetSongBPM</a> bereitgestellt. GetSongBPM
ist kostenlos, verlangt aber diesen sichtbaren Backlink. Resonanz zeigt ihn
zusätzlich im Systemstatus an.

Ohne `OPENAI_API_KEY` verwendet Resonanz eine lokale deutsche Textanalyse.
Spotify-Verlauf, Tokens und Hördaten werden niemals an OpenAI übertragen.

## Bedienung Schritt für Schritt

1. **Übersicht:** Freitext, Kontext, Dauer und Discovery-Anteil wählen.
2. **Playlist erstellen:** Der lokale Algorithmus bewertet Präferenz,
   Aktualität, Kontext, Skip-Verhalten, Discovery-Ähnlichkeit und
   Merkmalskonfidenz.
3. **Reihenfolge:** BPM-Abstand, Camelot-Kompatibilität, Genrewechsel,
   Energie und Künstlerwiederholungen bestimmen die Reihenfolge.
4. **Spotify:** Ergebnis als private Playlist veröffentlichen. Wiederholte
   Veröffentlichungen am selben Kalendertag aktualisieren dieselbe Playlist.
5. **Verlauf:** Automatische Profilzuordnungen prüfen und manuell korrigieren.
6. **Musikdaten:** Fehlende BPM-/Key-Werte sichtbar prüfen und korrigieren.
7. **Einstellungen:** Tägliche Zeit, Dauer, Discovery-Anteil und Aktivierung
   ändern. Der Worker übernimmt die Dashboard-Werte ohne zweite Konfiguration.

## Dienste

| Dienst | Aufgabe |
| --- | --- |
| `postgres` | PostgreSQL-Datenbank |
| `backend` | FastAPI, OAuth, API und Migrationen |
| `worker` | Spotify-Synchronisierung und tägliche Automatisierung |
| `frontend` | React/TypeScript-Dashboard hinter Nginx |

Alle Ports sind ausschließlich an `127.0.0.1` gebunden.

## Wichtige Endpunkte

- `POST /api/playlists/generate`
- `POST /api/intents/parse`
- `POST /api/sync/spotify`
- `POST /api/sync/discovery`
- `POST /api/sync/features`
- `POST /api/system/source-probe?limit=100`
- `POST /api/playlist-runs/{id}/publish`
- `POST /api/playlist-runs/{id}/enqueue`
- `PATCH /api/sessions/{id}/profile`
- `PATCH /api/tracks/{id}/features`

Die 100-Track-Machbarkeitsprobe kann alternativ im Backend-Container oder
lokal mit `python -m app.probe_sources` ausgeführt werden. Pro Track gewinnt
automatisch die Quelle mit der höchsten Match-Konfidenz.

## Prüfen und Stoppen

```powershell
.\scripts\check.ps1
.\scripts\stop.ps1
```

Der vollständige simulierte Ablauf innerhalb der Docker-Umgebung lässt sich
separat prüfen:

```powershell
docker compose exec -T backend python -m app.e2e_smoke
```

API-Dokumentation: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## Datenschutz und Grenzen

- Refresh- und Access-Tokens werden verschlüsselt im Backend gespeichert.
- API-Schlüssel und Tokens erscheinen weder im Frontend noch in Logs.
- Fehlende Musikmerkmale bleiben erlaubt und werden niedriger gewichtet.
- Der Queue-Assistent ist standardmäßig deaktiviert; Spotify garantiert seine
  Reihenfolge nicht.
- iPhone-Fokus-Endpunkt, HTTPS, Mehrbenutzer-Authentifizierung, Backups und
  externes Monitoring sind bewusst spätere Server-Erweiterungen.
