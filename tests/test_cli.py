"""Tests für das Command-line Interface in cli.py."""

import json
import sys
from datetime import datetime
from pathlib import Path
from types import TracebackType

import pytest

from aufgussplan.cli import main
from aufgussplan.database import init_db, save_aufgussplan
from aufgussplan.scraper import KNOWN_LOCATIONS, Aufguss, Aufgussplan


class FakeScraper:
    """Ersatz für AufgussplanScraper ohne Netzwerkzugriff."""

    def __init__(
        self,
        plans: dict[str, Aufgussplan] | None = None,
        existing: set[str] | None = None,
    ) -> None:
        self.plans = plans or {}
        self.existing = existing or set()

    def __call__(self, timeout: float = 10.0) -> "FakeScraper":
        # Wird anstelle der Klasse aufgerufen: AufgussplanScraper(timeout=...)
        return self

    def __enter__(self) -> "FakeScraper":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    def scrape_standort(self, standort: str) -> Aufgussplan | None:
        return self.plans.get(standort)

    def check_standort_exists(self, standort: str) -> bool:
        return standort in self.existing


def run_cli(monkeypatch: pytest.MonkeyPatch, *argv: str) -> int:
    monkeypatch.setattr(sys, "argv", ["aufgussplan", *argv])
    return main()


def use_fake_scraper(monkeypatch: pytest.MonkeyPatch, fake: FakeScraper) -> None:
    monkeypatch.setattr("aufgussplan.cli.AufgussplanScraper", fake)


def make_plan(standort: str = "fellbach") -> Aufgussplan:
    return Aufgussplan(
        standort=standort,
        abgerufen_am="2026-08-23T10:00:00",
        aufguesse=[
            Aufguss(zeit="10:30", sauna="Kelosauna", aufguss_name="Birkenaufguss")
        ],
    )


class TestEinfacheBefehle:
    def test_list_zeigt_alle_standorte(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert run_cli(monkeypatch, "--list") == 0
        out = capsys.readouterr().out
        for standort in KNOWN_LOCATIONS:
            assert standort in out

    def test_db_path_zeigt_pfad(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        tmp_path: Path,
    ) -> None:
        db = tmp_path / "meine.db"
        assert run_cli(monkeypatch, "--db-path", "--db-file", str(db)) == 0
        assert capsys.readouterr().out.strip() == str(db)

    def test_ohne_argumente_zeigt_hilfe_und_fehlercode(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert run_cli(monkeypatch) == 1
        assert "usage" in capsys.readouterr().out


class TestCheck:
    def test_existierender_standort(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        use_fake_scraper(monkeypatch, FakeScraper(existing={"fellbach"}))
        assert run_cli(monkeypatch, "--check", "fellbach") == 0
        assert "existiert" in capsys.readouterr().out

    def test_unbekannter_standort(self, monkeypatch: pytest.MonkeyPatch) -> None:
        use_fake_scraper(monkeypatch, FakeScraper(existing=set()))
        assert run_cli(monkeypatch, "--check", "gibtesnicht") == 1


class TestScrapeJson:
    def test_einzelner_standort_gibt_objekt_aus(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        use_fake_scraper(monkeypatch, FakeScraper(plans={"fellbach": make_plan()}))
        assert run_cli(monkeypatch, "fellbach", "--quiet") == 0
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, dict)
        assert data["standort"] == "fellbach"
        assert data["anzahl_aufguesse"] == 1

    def test_mehrere_standorte_geben_liste_aus(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        fake = FakeScraper(
            plans={"fellbach": make_plan(), "obernsees": make_plan("obernsees")}
        )
        use_fake_scraper(monkeypatch, fake)
        assert run_cli(monkeypatch, "fellbach", "obernsees", "--quiet") == 0
        data = json.loads(capsys.readouterr().out)
        assert [p["standort"] for p in data] == ["fellbach", "obernsees"]

    def test_output_schreibt_datei(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        use_fake_scraper(monkeypatch, FakeScraper(plans={"fellbach": make_plan()}))
        out_file = tmp_path / "plan.json"
        code = run_cli(
            monkeypatch, "fellbach", "--quiet", "--output", str(out_file)
        )
        assert code == 0
        data = json.loads(out_file.read_text(encoding="utf-8"))
        assert data["standort"] == "fellbach"

    def test_fehlschlag_liefert_fehlercode(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        use_fake_scraper(monkeypatch, FakeScraper(plans={}))
        assert run_cli(monkeypatch, "gibtesnicht", "--quiet") == 1
        assert "Keine Daten" in capsys.readouterr().err


class TestScrapeDb:
    def test_speichert_in_datenbank(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        use_fake_scraper(monkeypatch, FakeScraper(plans={"fellbach": make_plan()}))
        db = tmp_path / "test.db"
        code = run_cli(
            monkeypatch, "fellbach", "--db", "--db-file", str(db), "--quiet"
        )
        assert code == 0

        conn = init_db(db)
        try:
            rows = conn.execute("SELECT zeit, sauna FROM aufguesse").fetchall()
            assert [(r["zeit"], r["sauna"]) for r in rows] == [("10:30", "Kelosauna")]
        finally:
            conn.close()


def _befuellte_db(db: Path, datum: str) -> None:
    conn = init_db(db)
    try:
        save_aufgussplan(conn, make_plan(), datum=datum)
    finally:
        conn.close()


class TestDbQuery:
    def test_fehlende_datenbank(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        tmp_path: Path,
    ) -> None:
        db = tmp_path / "fehlt.db"
        assert run_cli(monkeypatch, "--db-query", "heute", "--db-file", str(db)) == 1
        assert "existiert nicht" in capsys.readouterr().err

    def test_datum_mit_treffern(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        tmp_path: Path,
    ) -> None:
        db = tmp_path / "test.db"
        _befuellte_db(db, "2026-08-20")
        code = run_cli(monkeypatch, "--db-query", "2026-08-20", "--db-file", str(db))
        assert code == 0
        out = capsys.readouterr().out
        assert "FELLBACH" in out
        assert "10:30" in out
        assert "Birkenaufguss" in out

    def test_heute_wird_aufgeloest(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        tmp_path: Path,
    ) -> None:
        db = tmp_path / "test.db"
        _befuellte_db(db, datetime.now().strftime("%Y-%m-%d"))
        assert run_cli(monkeypatch, "--db-query", "heute", "--db-file", str(db)) == 0
        assert "10:30" in capsys.readouterr().out

    def test_standort_filter(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        tmp_path: Path,
    ) -> None:
        db = tmp_path / "test.db"
        _befuellte_db(db, "2026-08-20")
        code = run_cli(
            monkeypatch,
            "--db-query",
            "2026-08-20",
            "obernsees",
            "--db-file",
            str(db),
        )
        assert code == 1  # kein Treffer für diesen Standort
        assert "Keine Aufgüsse" in capsys.readouterr().err

    def test_datum_ohne_treffer(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        tmp_path: Path,
    ) -> None:
        db = tmp_path / "test.db"
        _befuellte_db(db, "2026-08-20")
        assert (
            run_cli(monkeypatch, "--db-query", "1999-01-01", "--db-file", str(db))
            == 1
        )


class TestDbStats:
    def test_fehlende_datenbank(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        tmp_path: Path,
    ) -> None:
        db = tmp_path / "fehlt.db"
        assert run_cli(monkeypatch, "--db-stats", "--db-file", str(db)) == 1
        assert "existiert nicht" in capsys.readouterr().err

    def test_zeigt_statistiken(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        tmp_path: Path,
    ) -> None:
        db = tmp_path / "test.db"
        _befuellte_db(db, "2026-08-20")
        assert run_cli(monkeypatch, "--db-stats", "--db-file", str(db)) == 0
        out = capsys.readouterr().out
        assert "Standorte: 1" in out
        assert "Aufgüsse gesamt: 1" in out
        assert "Kelosauna" in out
