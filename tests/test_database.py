"""Tests für die SQLite-Schicht in database.py."""

import sqlite3
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest

from aufgussplan.database import (
    get_aufguesse_by_date,
    get_db_path,
    get_or_create_standort,
    get_statistics,
    init_db,
    save_aufgussplan,
)
from aufgussplan.scraper import Aufguss, Aufgussplan


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    connection = init_db(tmp_path / "test.db")
    yield connection
    connection.close()


def _count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"])


class TestInitDb:
    def test_erstellt_datei_und_tabellen(self, tmp_path: Path) -> None:
        db_file = tmp_path / "neu" / "test.db"
        conn = init_db(db_file)
        try:
            assert db_file.exists()  # inkl. Verzeichnis-Anlage
            tables = {
                row["name"]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            assert {"standorte", "abrufe", "aufguesse"} <= tables
        finally:
            conn.close()

    def test_idempotent(self, tmp_path: Path) -> None:
        db_file = tmp_path / "test.db"
        init_db(db_file).close()
        conn = init_db(db_file)  # zweiter Aufruf darf nicht fehlschlagen
        conn.close()

    def test_get_db_path_liegt_im_home(self) -> None:
        path = get_db_path()
        assert path.name == "aufgussplan.db"
        assert path.is_relative_to(Path.home())


class TestGetOrCreateStandort:
    def test_legt_standort_mit_titel_an(self, conn: sqlite3.Connection) -> None:
        standort_id = get_or_create_standort(conn, "bad-homburg")
        row = conn.execute(
            "SELECT slug, name FROM standorte WHERE id = ?", (standort_id,)
        ).fetchone()
        assert row["slug"] == "bad-homburg"
        assert row["name"] == "Bad Homburg"

    def test_gleicher_slug_liefert_gleiche_id(
        self, conn: sqlite3.Connection
    ) -> None:
        first = get_or_create_standort(conn, "fellbach")
        second = get_or_create_standort(conn, "fellbach")
        assert first == second
        assert _count(conn, "standorte") == 1


class TestSaveAufgussplan:
    def test_speichert_plan_vollstaendig(
        self, conn: sqlite3.Connection, sample_plan: Aufgussplan
    ) -> None:
        abruf_id = save_aufgussplan(conn, sample_plan, datum="2026-08-20")

        abruf = conn.execute(
            "SELECT * FROM abrufe WHERE id = ?", (abruf_id,)
        ).fetchone()
        assert abruf["datum"] == "2026-08-20"
        assert abruf["anzahl_aufguesse"] == 2
        assert abruf["abgerufen_am"] == "2026-08-23T10:00:00"

        rows = conn.execute(
            "SELECT * FROM aufguesse WHERE abruf_id = ? ORDER BY zeit", (abruf_id,)
        ).fetchall()
        assert len(rows) == 2
        assert rows[0]["zeit"] == "10:30"
        assert rows[0]["duft"] == "Birke,Menthol"  # Listen werden komma-gejoint
        assert rows[0]["eigenschaften"] == "/icons/abc.png"
        assert rows[1]["duft"] is None  # leere Liste wird zu NULL

    def test_gleicher_tag_ersetzt_aufguesse(
        self, conn: sqlite3.Connection, sample_plan: Aufgussplan
    ) -> None:
        first_id = save_aufgussplan(conn, sample_plan, datum="2026-08-20")

        neuer_plan = Aufgussplan(
            standort="fellbach",
            abgerufen_am="2026-08-23T18:00:00",
            aufguesse=[Aufguss(zeit="16:00", sauna="Erdsauna")],
        )
        second_id = save_aufgussplan(conn, neuer_plan, datum="2026-08-20")

        # Upsert: derselbe Abruf wird aktualisiert, Aufgüsse ersetzt
        assert second_id == first_id
        assert _count(conn, "abrufe") == 1
        assert _count(conn, "aufguesse") == 1
        abruf = conn.execute(
            "SELECT * FROM abrufe WHERE id = ?", (first_id,)
        ).fetchone()
        assert abruf["anzahl_aufguesse"] == 1
        assert abruf["abgerufen_am"] == "2026-08-23T18:00:00"

    def test_verschiedene_tage_erzeugen_neue_abrufe(
        self, conn: sqlite3.Connection, sample_plan: Aufgussplan
    ) -> None:
        save_aufgussplan(conn, sample_plan, datum="2026-08-20")
        save_aufgussplan(conn, sample_plan, datum="2026-08-21")
        assert _count(conn, "abrufe") == 2
        assert _count(conn, "aufguesse") == 4
        assert _count(conn, "standorte") == 1

    def test_default_datum_ist_heute(
        self, conn: sqlite3.Connection, sample_plan: Aufgussplan
    ) -> None:
        abruf_id = save_aufgussplan(conn, sample_plan)
        row = conn.execute(
            "SELECT datum FROM abrufe WHERE id = ?", (abruf_id,)
        ).fetchone()
        assert row["datum"] == datetime.now().strftime("%Y-%m-%d")


class TestGetAufguesseByDate:
    @pytest.fixture
    def befuellt(self, conn: sqlite3.Connection) -> sqlite3.Connection:
        for standort, zeiten in [("obernsees", ["14:00"]), ("fellbach", ["10:30"])]:
            plan = Aufgussplan(
                standort=standort,
                abgerufen_am="2026-08-23T10:00:00",
                aufguesse=[Aufguss(zeit=z, sauna="Kelosauna") for z in zeiten],
            )
            save_aufgussplan(conn, plan, datum="2026-08-20")
        return conn

    def test_liefert_alle_standorte_sortiert(
        self, befuellt: sqlite3.Connection
    ) -> None:
        rows = get_aufguesse_by_date(befuellt, "2026-08-20")
        assert [(r["standort"], r["zeit"]) for r in rows] == [
            ("fellbach", "10:30"),
            ("obernsees", "14:00"),
        ]

    def test_filter_nach_standort(self, befuellt: sqlite3.Connection) -> None:
        rows = get_aufguesse_by_date(befuellt, "2026-08-20", standort="obernsees")
        assert len(rows) == 1
        assert rows[0]["standort"] == "obernsees"

    def test_unbekanntes_datum_liefert_leere_liste(
        self, befuellt: sqlite3.Connection
    ) -> None:
        assert get_aufguesse_by_date(befuellt, "1999-01-01") == []


class TestGetStatistics:
    def test_leere_datenbank(self, conn: sqlite3.Connection) -> None:
        stats = get_statistics(conn)
        assert stats["standorte"] == 0
        assert stats["abrufe"] == 0
        assert stats["aufguesse_gesamt"] == 0
        assert stats["erster_abruf"] is None
        assert stats["letzter_abruf"] is None
        assert stats["top_saunas"] == []
        assert stats["top_aufguesse"] == []

    def test_befuellte_datenbank(
        self, conn: sqlite3.Connection, sample_plan: Aufgussplan
    ) -> None:
        save_aufgussplan(conn, sample_plan, datum="2026-08-20")
        save_aufgussplan(conn, sample_plan, datum="2026-08-21")

        stats = get_statistics(conn)
        assert stats["standorte"] == 1
        assert stats["abrufe"] == 2
        assert stats["aufguesse_gesamt"] == 4
        assert stats["erster_abruf"] == "2026-08-20"
        assert stats["letzter_abruf"] == "2026-08-21"
        assert {s["sauna"] for s in stats["top_saunas"]} == {"Kelosauna", "Dampfbad"}
        assert stats["top_aufguesse"][0]["count"] == 2
