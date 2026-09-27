# Changelog

## v2.2.2 - 2026-09-27

### Deutsch

- Nicht benötigte Installationswerkzeuge aus dem Reporter-Image entfernt.
- Automatische Sicherheitsprüfung vor der Veröffentlichung verbessert.
- Verständliche Versions- und Buildbezeichnungen für neue Images ergänzt.
- ZIP-Paket und DE/EN-Handbuch werden bei neuen Versionen automatisch veröffentlicht.
- Berichte, Zeitplanung und Einstellungen bleiben unverändert.

### English

- Removed unneeded installation tools from the reporter image.
- Improved the automatic security check before publication.
- Added readable version and build tags for new images.
- New versions automatically publish the ZIP package and DE/EN handbook.
- Reports, scheduling and settings remain unchanged.

## v2.2 - 2026-05-21

### Deutsch

#### Neu

- Vorgebautes Docker-Image über GitHub Container Registry ergänzt.
- Wöchentlicher GitHub Actions Rebuild für das Reporter-Image ergänzt.
- Trivy Image-Scan in GitHub Actions ergänzt.
- Dependabot-Konfiguration für GitHub Actions, Dockerfile und Python-Abhängigkeiten ergänzt.
- `docker-compose.local-build.yaml` für lokale Builds ergänzt.
- `scripts/update_reporter.sh` für Updates über Registry-Images ergänzt.
- `scripts/rebuild_reporter_local.sh` für lokale Rebuilds ergänzt.
- `scripts/security_scan_reporter.sh` für lokale Trivy-Scans des Reporter-Images ergänzt.
- `.dockerignore` für einen sauberen Docker-Build-Kontext ergänzt.
- `.env.example` für GHCR-Image-Nutzung aktualisiert.

#### Geändert

- Standard-`docker-compose.yaml` nutzt nun `ghcr.io/railsimulatornet/ugreen-nas-syncthing-reporter:latest` statt eines lokalen Builds.
- Dockerfile-Basisimage auf `python:3.12-slim-bookworm` geändert.
- Debian-Pakete werden beim Image-Build aktualisiert.
- Unnötiges `curl`-Paket aus dem Reporter-Image entfernt.
- Python-Abhängigkeit `requests` auf `>=2.32.4,<3` gesetzt.
- Reporter-Metadaten auf V2.2 / 2026-05-21 aktualisiert.

#### Hinweise

- Bestehende Nutzer können aktualisieren, indem sie die Compose-Datei ersetzen und anschließend `docker compose pull && docker compose up -d` ausführen.
- Lokale Builds bleiben über `docker-compose.local-build.yaml` möglich.

### English

#### Added

- Added prebuilt Docker image workflow for GitHub Container Registry.
- Added weekly scheduled GitHub Actions rebuild for the reporter image.
- Added Trivy image scan in GitHub Actions.
- Added Dependabot configuration for GitHub Actions, Dockerfile and Python dependencies.
- Added `docker-compose.local-build.yaml` for local builds.
- Added `scripts/update_reporter.sh` for registry-based updates.
- Added `scripts/rebuild_reporter_local.sh` for local rebuilds.
- Added `scripts/security_scan_reporter.sh` for local Trivy scans of the reporter image.
- Added `.dockerignore` for a clean Docker build context.
- Updated `.env.example` for GHCR image usage.

#### Changed

- Default `docker-compose.yaml` now uses `ghcr.io/railsimulatornet/ugreen-nas-syncthing-reporter:latest` instead of a local build.
- Dockerfile base image changed to `python:3.12-slim-bookworm`.
- Debian packages are upgraded during image build.
- Removed unnecessary `curl` package from the reporter image.
- Python dependency `requests` is pinned to `>=2.32.4,<3`.
- Reporter metadata updated to V2.2 / 2026-05-21.

#### Notes

- Existing users can update by replacing the Compose file and running `docker compose pull && docker compose up -d`.
- Local builds remain available through `docker-compose.local-build.yaml`.
