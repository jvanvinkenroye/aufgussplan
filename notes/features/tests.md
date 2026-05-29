# Feature: Tests

## Ziel
Umfassende Testabdeckung für den Aufgussplan Scraper.

## Module zu testen

### 1. scraper.py
- `Aufguss` dataclass - `to_dict()` Methode
- `Aufgussplan` dataclass - `to_dict()` Methode
- `AufgussplanScraper`:
  - `get_content()` - HTTP-Anfragen, Fehlerbehandlung
  - `parse_content()` - HTML-Parsing
  - `_parse_table_row()` - Tabellenzeilen-Parsing
  - `scrape_standort()` - Kombination aus get + parse
  - `scrape_all()` - Alle Standorte
  - `check_standort_exists()` - Existenzprüfung

### 2. database.py
- `init_db()` - Datenbank-Initialisierung
- `save_aufgussplan()` - Speichern von Aufgussplänen
- `get_aufguesse_by_date()` - Abfragen nach Datum
- `get_statistics()` - Statistiken

### 3. cli.py
- Argument-Parsing
- Output-Formate (JSON, pretty)
- Datenbank-Integration

## Testansatz
- pytest mit Fixtures
- httpx-mock für HTTP-Mocking
- Temporäre SQLite-Datenbanken für DB-Tests
- Beispiel-HTML für Parser-Tests
