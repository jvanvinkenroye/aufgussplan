# Aufgussplan Scraper

Scraper für [aufgussplan.de](https://www.aufgussplan.de) - Sammelt täglich Sauna-Aufgusspläne und speichert sie in einer SQLite-Datenbank.

## Schnellstart (Docker)

```bash
# Container bauen und starten
docker compose up -d

# Logs anzeigen
docker compose logs -f
```

Der Container scraped automatisch **täglich um 10:00 Uhr** alle Standorte.

## Docker-Befehle

### Container verwalten

```bash
# Bauen
docker compose build

# Starten
docker compose up -d

# Stoppen
docker compose down

# Logs
docker compose logs -f

# Status
docker compose ps
```

### Daten abfragen

```bash
# Statistiken anzeigen
docker compose exec aufgussplan aufgussplan --db-file /data/aufgussplan.db --db-stats

# Aufgüsse für heute
docker compose exec aufgussplan aufgussplan --db-file /data/aufgussplan.db --db-query heute

# Aufgüsse für bestimmtes Datum
docker compose exec aufgussplan aufgussplan --db-file /data/aufgussplan.db --db-query 2026-01-25

# Nur bestimmter Standort
docker compose exec aufgussplan aufgussplan --db-file /data/aufgussplan.db --db-query heute obernsees
```

### Manuell scrapen

```bash
# Alle Standorte
docker compose exec aufgussplan aufgussplan --db-file /data/aufgussplan.db --db --all

# Einzelner Standort
docker compose exec aufgussplan aufgussplan --db-file /data/aufgussplan.db --db fellbach
```

### Datenbank

```bash
# SQLite CLI öffnen
docker compose exec aufgussplan sqlite3 /data/aufgussplan.db

# Datenbank exportieren
docker compose exec aufgussplan cat /data/aufgussplan.db > aufgussplan.db
```

## Make-Shortcuts (optional)

Falls `make` installiert ist:

```bash
make help     # Alle Befehle anzeigen
make build    # Docker-Image bauen
make up       # Container starten
make down     # Container stoppen
make logs     # Logs anzeigen
make stats    # Statistiken
make query    # Aufgüsse heute
make scrape   # Manuell scrapen
make db       # SQLite CLI
make export   # Datenbank exportieren
```

## Lokale Installation (ohne Docker)

```bash
# Repository klonen
cd aufgussplan

# Virtual Environment erstellen
uv venv --seed
source .venv/bin/activate

# Installieren
uv pip install -e .

# Nutzen
aufgussplan --help
aufgussplan --list
aufgussplan obernsees --pretty
aufgussplan --db --all
aufgussplan --db-stats
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

-- Aufgüsse pro Standort pro Tag
SELECT s.slug, ab.datum, ab.anzahl_aufguesse
FROM abrufe ab
JOIN standorte s ON ab.standort_id = s.id
ORDER BY ab.datum DESC, s.slug;
```

## Konfiguration

### Cron-Zeit ändern

In `docker/crontab` die Zeit anpassen:

```cron
# Format: Minute Stunde Tag Monat Wochentag
0 10 * * *   # 10:00 Uhr täglich (Standard)
0 8 * * *    # 08:00 Uhr täglich
0 */6 * * *  # Alle 6 Stunden
```

Nach Änderung neu bauen: `docker compose build && docker compose up -d`

### Timezone

In `docker-compose.yml`:

```yaml
environment:
  - TZ=Europe/Berlin
```
