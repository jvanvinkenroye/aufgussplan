"""Gemeinsame Fixtures für die Testsuite."""

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from aufgussplan.scraper import Aufguss, Aufgussplan, AufgussplanScraper

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_html() -> Callable[[str], str]:
    """Lädt eine HTML-Fixture-Datei als String."""

    def _load(name: str) -> str:
        return (FIXTURES_DIR / name).read_text(encoding="utf-8")

    return _load


@pytest.fixture
def scraper() -> Iterator[AufgussplanScraper]:
    """Scraper-Instanz (ohne Netzwerkzugriff in Parsing-Tests)."""
    with AufgussplanScraper() as s:
        yield s


@pytest.fixture
def sample_plan() -> Aufgussplan:
    """Beispiel-Aufgussplan mit zwei Einträgen."""
    return Aufgussplan(
        standort="fellbach",
        abgerufen_am="2026-08-23T10:00:00",
        aufguesse=[
            Aufguss(
                zeit="10:30",
                sauna="Kelosauna",
                temperatur="90°C",
                aufguss_name="Birkenaufguss",
                duft=["Birke", "Menthol"],
                beschreibung="Klassischer Aufguss",
                eigenschaften=["/icons/abc.png"],
            ),
            Aufguss(zeit="14:00", sauna="Dampfbad", aufguss_name="Salz-Peeling"),
        ],
        legende={"Handtuch": "Handtuch erforderlich"},
    )
