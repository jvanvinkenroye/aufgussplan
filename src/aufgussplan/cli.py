"""Command-line Interface für den Aufgussplan-Scraper."""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from .database import get_aufguesse_by_date, get_db_path, get_statistics, init_db, save_aufgussplan
from .scraper import KNOWN_LOCATIONS, AufgussplanScraper


def main() -> int:
    """Hauptfunktion für CLI."""
    parser = argparse.ArgumentParser(
        description="Scraper für aufgussplan.de - Extrahiert Sauna-Aufgusspläne",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  aufgussplan --list                    # Zeigt alle bekannten Standorte
  aufgussplan fellbach                  # Scraped Fellbach (JSON)
  aufgussplan --all                     # Scraped alle Standorte (JSON)
  aufgussplan fellbach -o plan.json     # Speichert als JSON-Datei

  # Datenbank-Modus
  aufgussplan --db --all                # Scraped alle und speichert in SQLite
  aufgussplan --db fellbach             # Scraped Fellbach in SQLite
  aufgussplan --db-stats                # Zeigt Datenbank-Statistiken
  aufgussplan --db-query 2026-01-25     # Zeigt Aufgüsse für Datum
  aufgussplan --db-path                 # Zeigt Datenbank-Pfad
        """,
    )

    parser.add_argument(
        "standorte",
        nargs="*",
        help="Standort-Slugs zum Scrapen (z.B. fellbach, karlsruhe)",
    )

    parser.add_argument(
        "--all",
        "-a",
        action="store_true",
        help="Alle bekannten Standorte scrapen",
    )

    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="Bekannte Standorte auflisten",
    )

    parser.add_argument(
        "--check",
        "-c",
        metavar="STANDORT",
        help="Prüfen ob ein Standort existiert",
    )

    parser.add_argument(
        "--output",
        "-o",
        metavar="DATEI",
        help="Ausgabe in JSON-Datei speichern",
    )

    parser.add_argument(
        "--pretty",
        "-p",
        action="store_true",
        help="JSON formatiert ausgeben",
    )

    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Keine Statusmeldungen ausgeben",
    )

    parser.add_argument(
        "--timeout",
        "-t",
        type=float,
        default=10.0,
        help="HTTP-Timeout in Sekunden (Standard: 10)",
    )

    # Datenbank-Optionen
    parser.add_argument(
        "--db",
        action="store_true",
        help="In SQLite-Datenbank speichern statt JSON",
    )

    parser.add_argument(
        "--db-file",
        metavar="DATEI",
        type=Path,
        help="Pfad zur SQLite-Datenbank (Standard: ~/.local/share/aufgussplan/aufgussplan.db)",
    )

    parser.add_argument(
        "--db-stats",
        action="store_true",
        help="Datenbank-Statistiken anzeigen",
    )

    parser.add_argument(
        "--db-query",
        metavar="DATUM",
        help="Aufgüsse für Datum abfragen (YYYY-MM-DD oder 'heute')",
    )

    parser.add_argument(
        "--db-path",
        action="store_true",
        help="Datenbank-Pfad anzeigen",
    )

    args = parser.parse_args()

    # Datenbank-Pfad
    db_path = args.db_file or get_db_path()

    # Zeige Datenbank-Pfad
    if args.db_path:
        print(db_path)
        return 0

    # Datenbank-Statistiken
    if args.db_stats:
        if not db_path.exists():
            print(f"Datenbank existiert nicht: {db_path}", file=sys.stderr)
            return 1

        conn = init_db(db_path)
        stats = get_statistics(conn)
        conn.close()

        print(f"Datenbank: {db_path}")
        print(f"Standorte: {stats['standorte']}")
        print(f"Abrufe: {stats['abrufe']}")
        print(f"Aufgüsse gesamt: {stats['aufguesse_gesamt']}")
        print(f"Zeitraum: {stats['erster_abruf']} bis {stats['letzter_abruf']}")
        print()
        print("Top 10 Saunas:")
        for s in stats["top_saunas"]:
            print(f"  {s['count']:4d}x {s['sauna']}")
        print()
        print("Top 10 Aufgüsse:")
        for a in stats["top_aufguesse"]:
            print(f"  {a['count']:4d}x {a['aufguss_name']}")

        return 0

    # Datenbank-Abfrage
    if args.db_query:
        if not db_path.exists():
            print(f"Datenbank existiert nicht: {db_path}", file=sys.stderr)
            return 1

        datum = args.db_query
        if datum.lower() == "heute":
            datum = datetime.now().strftime("%Y-%m-%d")

        conn = init_db(db_path)
        aufguesse = get_aufguesse_by_date(
            conn, datum,
            standort=args.standorte[0] if args.standorte else None
        )
        conn.close()

        if not aufguesse:
            print(f"Keine Aufgüsse für {datum} gefunden.", file=sys.stderr)
            return 1

        if args.pretty or not args.output:
            # Formatierte Ausgabe
            current_standort = ""
            for a in aufguesse:
                if a["standort"] != current_standort:
                    current_standort = a["standort"]
                    print(f"\n=== {current_standort.upper()} ===")
                print(f"  {a['zeit']} | {a['sauna'] or '-':20} | {a['aufguss_name'] or '-'}")
        else:
            # JSON Ausgabe
            print(json.dumps(aufguesse, ensure_ascii=False, indent=2 if args.pretty else None))

        return 0

    # Liste bekannte Standorte
    if args.list:
        print("Bekannte Standorte:")
        for standort in KNOWN_LOCATIONS:
            print(f"  - {standort}")
        return 0

    # Prüfe Standort
    if args.check:
        with AufgussplanScraper(timeout=args.timeout) as scraper:
            exists = scraper.check_standort_exists(args.check)
            if exists:
                print(f"Standort '{args.check}' existiert.")
                return 0
            else:
                print(f"Standort '{args.check}' existiert nicht.")
                return 1

    # Bestimme zu scrapende Standorte
    if args.all:
        standorte = KNOWN_LOCATIONS
    elif args.standorte:
        standorte = args.standorte
    else:
        parser.print_help()
        return 1

    # Datenbank-Verbindung wenn nötig
    conn = None
    if args.db:
        conn = init_db(db_path)
        if not args.quiet:
            print(f"Datenbank: {db_path}", file=sys.stderr)

    # Scrape
    results = []
    datum = datetime.now().strftime("%Y-%m-%d")

    with AufgussplanScraper(timeout=args.timeout) as scraper:
        for standort in standorte:
            if not args.quiet:
                print(f"Scraping {standort}...", file=sys.stderr)

            plan = scraper.scrape_standort(standort)
            if plan:
                if conn:
                    # In Datenbank speichern
                    save_aufgussplan(conn, plan, datum)
                    if not args.quiet:
                        print(
                            f"  -> {len(plan.aufguesse)} Aufgüsse gespeichert",
                            file=sys.stderr,
                        )
                else:
                    results.append(plan.to_dict())
                    if not args.quiet:
                        print(
                            f"  -> {len(plan.aufguesse)} Aufgüsse gefunden",
                            file=sys.stderr,
                        )
            else:
                if not args.quiet:
                    print("  -> Fehler oder Standort nicht gefunden", file=sys.stderr)

    # Datenbank schließen
    if conn:
        conn.close()
        if not args.quiet:
            print(f"\nDaten gespeichert für {datum}", file=sys.stderr)
        return 0

    # JSON-Ausgabe
    if not results:
        print("Keine Daten gefunden.", file=sys.stderr)
        return 1

    # JSON formatieren
    indent = 2 if args.pretty else None
    json_output = json.dumps(
        results if len(results) > 1 else results[0],
        ensure_ascii=False,
        indent=indent,
    )

    # Speichern oder ausgeben
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(json_output, encoding="utf-8")
        if not args.quiet:
            print(f"Gespeichert: {output_path}", file=sys.stderr)
    else:
        print(json_output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
