# Aufgussplan Scraper

Scraper für [aufgussplan.de](https://www.aufgussplan.de) - Sammelt täglich Sauna-Aufgusspläne und speichert sie in einer SQLite-Datenbank.

## Lokale Installation (uv)

```bash
# Repository klonen
cd aufgussplan

# Virtual Environment erstellen und installieren
uv venv --seed
source .venv/bin/activate
uv pip install -e .

# Nutzen
aufgussplan --help
aufgussplan --list
aufgussplan obernsees --pretty
aufgussplan --db --all
aufgussplan --db-stats
```

## Podman Container

### Image bauen

```bash
podman build -t aufgussplan:latest -f Containerfile .
```

### Manuell scrapen

```bash
# Volume erstellen
podman volume create aufgussplan-data

# Alle Standorte scrapen
podman run --rm \
    -v aufgussplan-data:/data:Z \
    aufgussplan:latest \
    --db-file /data/aufgussplan.db --db --all

# Statistiken anzeigen
podman run --rm \
    -v aufgussplan-data:/data:Z \
    aufgussplan:latest \
    --db-file /data/aufgussplan.db --db-stats

# Aufgüsse für heute
podman run --rm \
    -v aufgussplan-data:/data:Z \
    aufgussplan:latest \
    --db-file /data/aufgussplan.db --db-query heute
```

### SQLite-Datenbank inspizieren

```bash
# Datenbank-Pfad finden
podman volume inspect aufgussplan-data --format '{{.Mountpoint}}'

# Oder direkt mit sqlite3
podman run --rm -it \
    -v aufgussplan-data:/data:Z \
    docker.io/library/alpine \
    sh -c "apk add sqlite && sqlite3 /data/aufgussplan.db"
```

## Systemd User Service (Linux)

Automatisches tägliches Scrapen um 10:00 Uhr.

### Installation

```bash
# Unit-Files kopieren
mkdir -p ~/.config/systemd/user
cp systemd/aufgussplan.service ~/.config/systemd/user/
cp systemd/aufgussplan.timer ~/.config/systemd/user/

# Systemd neu laden
systemctl --user daemon-reload

# Timer aktivieren und starten
systemctl --user enable --now aufgussplan.timer

# Status prüfen
systemctl --user status aufgussplan.timer
systemctl --user list-timers
```

### Manuell auslösen

```bash
systemctl --user start aufgussplan.service
```

### Logs anzeigen

```bash
journalctl --user -u aufgussplan.service -f
```

### Deinstallation

```bash
systemctl --user disable --now aufgussplan.timer
rm ~/.config/systemd/user/aufgussplan.*
systemctl --user daemon-reload
```

## CLI-Optionen

```
aufgussplan [STANDORTE...] [OPTIONEN]

Optionen:
  -a, --all              Alle bekannten Standorte scrapen
  -l, --list             Bekannte Standorte auflisten
  -c, --check STANDORT   Prüfen ob Standort existiert
  -o, --output DATEI     Als JSON-Datei speichern
  -p, --pretty           JSON formatiert ausgeben
  -q, --quiet            Keine Statusmeldungen
  -t, --timeout SEKUNDEN HTTP-Timeout (Standard: 10)

Datenbank:
  --db                   In SQLite speichern statt JSON
  --db-file DATEI        Pfad zur Datenbank
  --db-stats             Statistiken anzeigen
  --db-query DATUM       Aufgüsse für Datum abfragen
  --db-path              Datenbank-Pfad anzeigen
```

## Bekannte Standorte

| Standort | Slug |
|----------|------|
| F3 Fellbach | `fellbach` |
| Vierordtbad Karlsruhe | `vierordtbad` |
| Europabad Karlsruhe | `karlsruhe` |
| Therme Obernsees | `obernsees` |
| Obertshausen | `obertshausen` |
| Aqualand | `aqualand` |
| Moselbad Koblenz | `koblenz` |
| Fürther Mare | `fuerth` |
| Schwitzkasten Budenheim | `budenheim` |
| Kelsterbach Erlebnisbad | `kelsterbach` |

## Datenbank-Schema

```sql
-- Standorte
CREATE TABLE standorte (
    id INTEGER PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,
    name TEXT
);

-- Abrufe (pro Tag/Standort)
CREATE TABLE abrufe (
    id INTEGER PRIMARY KEY,
    standort_id INTEGER,
    datum TEXT NOT NULL,
    anzahl_aufguesse INTEGER
);

-- Aufgüsse
CREATE TABLE aufguesse (
    id INTEGER PRIMARY KEY,
    abruf_id INTEGER,
    zeit TEXT,
    sauna TEXT,
    temperatur TEXT,
    aufguss_name TEXT,
    duft TEXT,
    beschreibung TEXT,
    eigenschaften TEXT
);
```

## Beispiel-Abfragen

```sql
-- Alle Aufgüsse von heute
SELECT s.slug, a.zeit, a.sauna, a.aufguss_name
FROM aufguesse a
JOIN abrufe ab ON a.abruf_id = ab.id
JOIN standorte s ON ab.standort_id = s.id
WHERE ab.datum = date('now')
ORDER BY s.slug, a.zeit;

-- Häufigste Aufgüsse
SELECT aufguss_name, COUNT(*) as anzahl
FROM aufguesse
GROUP BY aufguss_name
ORDER BY anzahl DESC
LIMIT 10;
```
