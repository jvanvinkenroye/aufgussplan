"""SQLite-Datenbank für Aufgussplan-Daten."""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from .scraper import Aufguss, Aufgussplan


def get_db_path() -> Path:
    """Gibt den Standard-Datenbankpfad zurück."""
    return Path.home() / ".local" / "share" / "aufgussplan" / "aufgussplan.db"


def init_db(db_path: Path | None = None) -> sqlite3.Connection:
    """Initialisiert die Datenbank und erstellt Tabellen.

    Args:
        db_path: Pfad zur Datenbank (optional)

    Returns:
        SQLite-Connection
    """
    if db_path is None:
        db_path = get_db_path()

    # Erstelle Verzeichnis falls nötig
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    conn.executescript("""
        -- Standorte
        CREATE TABLE IF NOT EXISTS standorte (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT UNIQUE NOT NULL,
            name TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        -- Abrufe (pro Tag/Standort)
        CREATE TABLE IF NOT EXISTS abrufe (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            standort_id INTEGER NOT NULL,
            abgerufen_am TEXT NOT NULL,
            datum TEXT NOT NULL,
            anzahl_aufguesse INTEGER DEFAULT 0,
            FOREIGN KEY (standort_id) REFERENCES standorte(id),
            UNIQUE(standort_id, datum)
        );

        -- Aufgüsse
        CREATE TABLE IF NOT EXISTS aufguesse (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            abruf_id INTEGER NOT NULL,
            zeit TEXT NOT NULL,
            sauna TEXT,
            temperatur TEXT,
            aufguss_name TEXT,
            duft TEXT,
            mitarbeiter TEXT,
            beschreibung TEXT,
            eigenschaften TEXT,
            FOREIGN KEY (abruf_id) REFERENCES abrufe(id)
        );

        -- Indizes
        CREATE INDEX IF NOT EXISTS idx_abrufe_datum ON abrufe(datum);
        CREATE INDEX IF NOT EXISTS idx_abrufe_standort ON abrufe(standort_id);
        CREATE INDEX IF NOT EXISTS idx_aufguesse_abruf ON aufguesse(abruf_id);
        CREATE INDEX IF NOT EXISTS idx_aufguesse_zeit ON aufguesse(zeit);
    """)

    conn.commit()
    return conn


def get_or_create_standort(conn: sqlite3.Connection, slug: str) -> int:
    """Holt oder erstellt einen Standort.

    Args:
        conn: Datenbank-Verbindung
        slug: Standort-Slug

    Returns:
        Standort-ID
    """
    cursor = conn.execute(
        "SELECT id FROM standorte WHERE slug = ?",
        (slug,)
    )
    row = cursor.fetchone()

    if row:
        return row["id"]

    cursor = conn.execute(
        "INSERT INTO standorte (slug, name) VALUES (?, ?)",
        (slug, slug.replace("-", " ").title())
    )
    conn.commit()
    return cursor.lastrowid  # type: ignore


def save_aufgussplan(
    conn: sqlite3.Connection,
    plan: Aufgussplan,
    datum: str | None = None
) -> int:
    """Speichert einen Aufgussplan in der Datenbank.

    Args:
        conn: Datenbank-Verbindung
        plan: Aufgussplan-Objekt
        datum: Datum (YYYY-MM-DD), default: heute

    Returns:
        Abruf-ID
    """
    if datum is None:
        datum = datetime.now().strftime("%Y-%m-%d")

    standort_id = get_or_create_standort(conn, plan.standort)

    # Prüfe ob bereits ein Abruf für heute existiert
    cursor = conn.execute(
        "SELECT id FROM abrufe WHERE standort_id = ? AND datum = ?",
        (standort_id, datum)
    )
    existing = cursor.fetchone()

    if existing:
        # Lösche alte Aufgüsse
        conn.execute("DELETE FROM aufguesse WHERE abruf_id = ?", (existing["id"],))
        abruf_id = existing["id"]
        # Update Abruf
        conn.execute(
            """UPDATE abrufe
               SET abgerufen_am = ?, anzahl_aufguesse = ?
               WHERE id = ?""",
            (plan.abgerufen_am, len(plan.aufguesse), abruf_id)
        )
    else:
        # Neuer Abruf
        cursor = conn.execute(
            """INSERT INTO abrufe (standort_id, abgerufen_am, datum, anzahl_aufguesse)
               VALUES (?, ?, ?, ?)""",
            (standort_id, plan.abgerufen_am, datum, len(plan.aufguesse))
        )
        abruf_id = cursor.lastrowid  # type: ignore

    # Speichere Aufgüsse
    for aufguss in plan.aufguesse:
        conn.execute(
            """INSERT INTO aufguesse
               (abruf_id, zeit, sauna, temperatur, aufguss_name, duft,
                mitarbeiter, beschreibung, eigenschaften)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                abruf_id,
                aufguss.zeit,
                aufguss.sauna,
                aufguss.temperatur,
                aufguss.aufguss_name,
                ",".join(aufguss.duft) if aufguss.duft else None,
                aufguss.mitarbeiter,
                aufguss.beschreibung,
                ",".join(aufguss.eigenschaften) if aufguss.eigenschaften else None,
            )
        )

    conn.commit()
    return abruf_id


def get_aufguesse_by_date(
    conn: sqlite3.Connection,
    datum: str,
    standort: str | None = None
) -> list[dict[str, Any]]:
    """Holt Aufgüsse für ein bestimmtes Datum.

    Args:
        conn: Datenbank-Verbindung
        datum: Datum (YYYY-MM-DD)
        standort: Optional: nur für diesen Standort

    Returns:
        Liste von Aufguss-Dictionaries
    """
    query = """
        SELECT
            s.slug as standort,
            a.zeit,
            a.sauna,
            a.temperatur,
            a.aufguss_name,
            a.duft,
            a.beschreibung
        FROM aufguesse a
        JOIN abrufe ab ON a.abruf_id = ab.id
        JOIN standorte s ON ab.standort_id = s.id
        WHERE ab.datum = ?
    """
    params: list[Any] = [datum]

    if standort:
        query += " AND s.slug = ?"
        params.append(standort)

    query += " ORDER BY s.slug, a.zeit"

    cursor = conn.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]


def get_statistics(conn: sqlite3.Connection) -> dict[str, Any]:
    """Holt Statistiken aus der Datenbank.

    Returns:
        Dictionary mit Statistiken
    """
    stats: dict[str, Any] = {}

    # Anzahl Standorte
    cursor = conn.execute("SELECT COUNT(*) as count FROM standorte")
    stats["standorte"] = cursor.fetchone()["count"]

    # Anzahl Abrufe
    cursor = conn.execute("SELECT COUNT(*) as count FROM abrufe")
    stats["abrufe"] = cursor.fetchone()["count"]

    # Anzahl Aufgüsse gesamt
    cursor = conn.execute("SELECT COUNT(*) as count FROM aufguesse")
    stats["aufguesse_gesamt"] = cursor.fetchone()["count"]

    # Erster und letzter Abruf
    cursor = conn.execute("SELECT MIN(datum) as min, MAX(datum) as max FROM abrufe")
    row = cursor.fetchone()
    stats["erster_abruf"] = row["min"]
    stats["letzter_abruf"] = row["max"]

    # Top Saunas
    cursor = conn.execute("""
        SELECT sauna, COUNT(*) as count
        FROM aufguesse
        WHERE sauna IS NOT NULL AND sauna != ''
        GROUP BY sauna
        ORDER BY count DESC
        LIMIT 10
    """)
    stats["top_saunas"] = [dict(row) for row in cursor.fetchall()]

    # Top Aufgüsse
    cursor = conn.execute("""
        SELECT aufguss_name, COUNT(*) as count
        FROM aufguesse
        WHERE aufguss_name IS NOT NULL AND aufguss_name != ''
        GROUP BY aufguss_name
        ORDER BY count DESC
        LIMIT 10
    """)
    stats["top_aufguesse"] = [dict(row) for row in cursor.fetchall()]

    return stats
