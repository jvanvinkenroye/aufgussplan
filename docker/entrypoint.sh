#!/bin/bash
set -e

DB_FILE="${AUFGUSSPLAN_DB:-/data/aufgussplan.db}"

# Initialisiere Datenbank falls nicht vorhanden
if [ ! -f "$DB_FILE" ]; then
    echo "Initialisiere Datenbank: $DB_FILE"
    aufgussplan --db-file "$DB_FILE" --db --all --quiet || true
    echo "Datenbank initialisiert."
fi

# Führe initialen Scrape durch falls gewünscht
if [ "$SCRAPE_ON_START" = "true" ]; then
    echo "Führe initialen Scrape durch..."
    aufgussplan --db-file "$DB_FILE" --db --all
fi

# Zeige Statistiken
echo ""
echo "=== Aufgussplan Scraper ==="
aufgussplan --db-file "$DB_FILE" --db-stats 2>/dev/null || echo "Noch keine Daten vorhanden."
echo ""
echo "Cron-Job aktiv: Täglich um ${SCRAPE_HOUR:-10}:${SCRAPE_MINUTE:-00} Uhr"
echo "Datenbank: $DB_FILE"
echo "==========================="
echo ""

# Starte übergebenen Befehl (cron)
exec "$@"
