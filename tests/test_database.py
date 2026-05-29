"""Tests für die Datenbank-Funktionen."""

import sqlite3
import tempfile
from pathlib import Path

from aufgussplan.database import (
    get_aufguesse_by_date,
    get_or_create_standort,
    get_statistics,
    init_db,
    save_aufgussplan,
)
from aufgussplan.scraper import Aufguss, Aufgussplan


class TestInitDb:
    """Tests für init_db."""

    def test_creates_tables(self, temp_db: sqlite3.Connection) -> None:
        """init_db erstellt alle erforderlichen Tabellen."""
        cursor = temp_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row["name"] for row in cursor.fetchall()]

        assert "standorte" in tables
        assert "abrufe" in tables
        assert "aufguesse" in tables

    def test_creates_indexes(self, temp_db: sqlite3.Connection) -> None:
        """init_db erstellt Indizes."""
        cursor = temp_db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' ORDER BY name"
        )
        indexes = [row["name"] for row in cursor.fetchall()]

        assert "idx_abrufe_datum" in indexes
        assert "idx_abrufe_standort" in indexes
        assert "idx_aufguesse_abruf" in indexes

    def test_creates_directory(self) -> None:
        """init_db erstellt das Verzeichnis falls nötig."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "subdir" / "test.db"
            conn = init_db(db_path)
            conn.close()

            assert db_path.exists()
            assert db_path.parent.exists()


class TestGetOrCreateStandort:
    """Tests für get_or_create_standort."""

    def test_creates_new_standort(self, temp_db: sqlite3.Connection) -> None:
        """Erstellt neuen Standort wenn nicht vorhanden."""
        standort_id = get_or_create_standort(temp_db, "fellbach")

        assert standort_id > 0

        cursor = temp_db.execute("SELECT * FROM standorte WHERE id = ?", (standort_id,))
        row = cursor.fetchone()
        assert row["slug"] == "fellbach"

    def test_returns_existing_standort(self, temp_db: sqlite3.Connection) -> None:
        """Gibt existierenden Standort zurück."""
        id1 = get_or_create_standort(temp_db, "fellbach")
        id2 = get_or_create_standort(temp_db, "fellbach")

        assert id1 == id2

    def test_different_standorte_different_ids(
        self, temp_db: sqlite3.Connection
    ) -> None:
        """Verschiedene Standorte bekommen verschiedene IDs."""
        id1 = get_or_create_standort(temp_db, "fellbach")
        id2 = get_or_create_standort(temp_db, "karlsruhe")

        assert id1 != id2


class TestSaveAufgussplan:
    """Tests für save_aufgussplan."""

    def test_saves_plan(
        self, temp_db: sqlite3.Connection, sample_aufgussplan: Aufgussplan
    ) -> None:
        """Speichert Aufgussplan in Datenbank."""
        abruf_id = save_aufgussplan(temp_db, sample_aufgussplan, "2026-05-30")

        assert abruf_id > 0

        cursor = temp_db.execute("SELECT * FROM abrufe WHERE id = ?", (abruf_id,))
        row = cursor.fetchone()
        assert row["datum"] == "2026-05-30"
        assert row["anzahl_aufguesse"] == 2

    def test_saves_aufguesse(
        self, temp_db: sqlite3.Connection, sample_aufgussplan: Aufgussplan
    ) -> None:
        """Speichert Aufgüsse korrekt."""
        abruf_id = save_aufgussplan(temp_db, sample_aufgussplan, "2026-05-30")

        cursor = temp_db.execute(
            "SELECT * FROM aufguesse WHERE abruf_id = ? ORDER BY zeit", (abruf_id,)
        )
        rows = cursor.fetchall()

        assert len(rows) == 2
        assert rows[0]["zeit"] == "10:00"
        assert rows[0]["sauna"] == "Kelosauna"
        assert rows[0]["aufguss_name"] == "Finnischer Klassiker"
        assert rows[1]["zeit"] == "11:00"

    def test_updates_existing_plan(
        self, temp_db: sqlite3.Connection, sample_aufgussplan: Aufgussplan
    ) -> None:
        """Aktualisiert existierenden Plan für gleichen Tag."""
        abruf_id1 = save_aufgussplan(temp_db, sample_aufgussplan, "2026-05-30")

        updated_plan = Aufgussplan(
            standort="fellbach",
            abgerufen_am="2026-05-30T12:00:00",
            aufguesse=[
                Aufguss(zeit="14:00", sauna="Dampfbad", aufguss_name="Mentholfrische")
            ],
        )
        abruf_id2 = save_aufgussplan(temp_db, updated_plan, "2026-05-30")

        assert abruf_id1 == abruf_id2

        cursor = temp_db.execute(
            "SELECT * FROM aufguesse WHERE abruf_id = ?", (abruf_id1,)
        )
        rows = cursor.fetchall()
        assert len(rows) == 1
        assert rows[0]["zeit"] == "14:00"

    def test_different_dates_different_abrufe(
        self, temp_db: sqlite3.Connection, sample_aufgussplan: Aufgussplan
    ) -> None:
        """Verschiedene Tage erstellen verschiedene Abrufe."""
        abruf_id1 = save_aufgussplan(temp_db, sample_aufgussplan, "2026-05-30")
        abruf_id2 = save_aufgussplan(temp_db, sample_aufgussplan, "2026-05-31")

        assert abruf_id1 != abruf_id2


class TestGetAufguesseByDate:
    """Tests für get_aufguesse_by_date."""

    def test_returns_aufguesse_for_date(
        self, temp_db: sqlite3.Connection, sample_aufgussplan: Aufgussplan
    ) -> None:
        """Gibt Aufgüsse für angegebenes Datum zurück."""
        save_aufgussplan(temp_db, sample_aufgussplan, "2026-05-30")

        results = get_aufguesse_by_date(temp_db, "2026-05-30")

        assert len(results) == 2
        assert results[0]["standort"] == "fellbach"
        assert results[0]["zeit"] == "10:00"

    def test_filters_by_standort(
        self, temp_db: sqlite3.Connection, sample_aufgussplan: Aufgussplan
    ) -> None:
        """Filtert nach Standort."""
        save_aufgussplan(temp_db, sample_aufgussplan, "2026-05-30")

        other_plan = Aufgussplan(
            standort="karlsruhe",
            abgerufen_am="2026-05-30T10:00:00",
            aufguesse=[Aufguss(zeit="15:00", sauna="Kelosauna")],
        )
        save_aufgussplan(temp_db, other_plan, "2026-05-30")

        results = get_aufguesse_by_date(temp_db, "2026-05-30", standort="fellbach")

        assert len(results) == 2
        assert all(r["standort"] == "fellbach" for r in results)

    def test_returns_empty_for_no_data(self, temp_db: sqlite3.Connection) -> None:
        """Gibt leere Liste wenn keine Daten."""
        results = get_aufguesse_by_date(temp_db, "2026-05-30")

        assert results == []


class TestGetStatistics:
    """Tests für get_statistics."""

    def test_returns_statistics(
        self, temp_db: sqlite3.Connection, sample_aufgussplan: Aufgussplan
    ) -> None:
        """Gibt Statistiken zurück."""
        save_aufgussplan(temp_db, sample_aufgussplan, "2026-05-30")

        stats = get_statistics(temp_db)

        assert stats["standorte"] == 1
        assert stats["abrufe"] == 1
        assert stats["aufguesse_gesamt"] == 2
        assert stats["erster_abruf"] == "2026-05-30"
        assert stats["letzter_abruf"] == "2026-05-30"

    def test_returns_top_saunas(
        self, temp_db: sqlite3.Connection, sample_aufgussplan: Aufgussplan
    ) -> None:
        """Gibt Top-Saunas zurück."""
        save_aufgussplan(temp_db, sample_aufgussplan, "2026-05-30")

        stats = get_statistics(temp_db)

        assert len(stats["top_saunas"]) > 0
        assert any(s["sauna"] == "Kelosauna" for s in stats["top_saunas"])

    def test_empty_db(self, temp_db: sqlite3.Connection) -> None:
        """Statistiken für leere Datenbank."""
        stats = get_statistics(temp_db)

        assert stats["standorte"] == 0
        assert stats["abrufe"] == 0
        assert stats["aufguesse_gesamt"] == 0
        assert stats["erster_abruf"] is None
        assert stats["letzter_abruf"] is None
