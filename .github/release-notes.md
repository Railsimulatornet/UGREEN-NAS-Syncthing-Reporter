## Deutsch

### Was ist neu?

Dieses Update kümmert sich um die Sicherheit und die Pflege des Reporter-Images.

- Nicht benötigte Installationswerkzeuge wurden aus dem fertigen Image entfernt.
- Die automatische Sicherheitsprüfung vor der Veröffentlichung wurde verbessert.
- Die Images erhalten verständliche Versions- und Buildbezeichnungen statt neuer `sha-…`-Tags.

An den Berichten, der Zeitplanung und den Einstellungen ändert sich nichts.

### Aktualisierung

In der UGOS-Docker-App das bestehende Projekt über **Neu bereitstellen** aktualisieren und **Das neueste Image abrufen** aktivieren.

Die eigene `.env` und vorhandene Daten bitte **nicht überschreiben**. Der Image-Pfad bleibt unverändert; wer `latest` verwendet, muss die Compose-Datei nicht ändern.

Die feste Version ist auch als `ghcr.io/railsimulatornet/ugreen-nas-syncthing-reporter:2.2.2` verfügbar. Sie bleibt unverändert, während `latest` weiterhin geprüfte Wartungsbuilds erhält.

Das Paket enthält wie bisher die deutschen und englischen Einstellungen sowie das DE/EN-Handbuch.

---

## English

### What's new?

This update improves the security and maintenance of the reporter image.

- Unneeded installation tools have been removed from the finished image.
- The automatic security check before publication has been improved.
- Images now use readable version and build tags instead of new `sha-…` tags.

Reports, scheduling and settings remain unchanged.

### Updating

In the UGOS Docker app, redeploy the existing project and enable **Download the latest image**.

Please **do not overwrite** your existing `.env` or data. The image path is unchanged; installations using `latest` do not need a Compose change.

The fixed version is also available as `ghcr.io/railsimulatornet/ugreen-nas-syncthing-reporter:2.2.2`. It remains unchanged, while `latest` continues to receive verified maintenance builds.

The package still includes the German and English settings and the DE/EN handbook.
