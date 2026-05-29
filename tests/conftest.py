"""Shared fixtures for tests."""

import sqlite3
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from aufgussplan.database import init_db
from aufgussplan.scraper import Aufguss, Aufgussplan


@pytest.fixture
def sample_aufguss() -> Aufguss:
    """Erstellt einen Beispiel-Aufguss."""
    return Aufguss(
        zeit="10:00",
        sauna="Kelosauna",
        temperatur="90°C",
        aufguss_name="Finnischer Klassiker",
        duft=["Eukalyptus", "Minze"],
        beschreibung="Ein klassischer Aufguss",
        eigenschaften=["intensiv"],
    )


@pytest.fixture
def sample_aufgussplan(sample_aufguss: Aufguss) -> Aufgussplan:
    """Erstellt einen Beispiel-Aufgussplan."""
    return Aufgussplan(
        standort="fellbach",
        abgerufen_am="2026-05-30T10:00:00",
        aufguesse=[
            sample_aufguss,
            Aufguss(
                zeit="11:00",
                sauna="Biosauna",
                temperatur="60°C",
                aufguss_name="Sanfter Wind",
                duft=["Lavendel"],
            ),
        ],
    )


@pytest.fixture
def temp_db() -> Generator[sqlite3.Connection, None, None]:
    """Erstellt eine temporäre Datenbank."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    conn = init_db(db_path)
    yield conn
    conn.close()
    db_path.unlink(missing_ok=True)


SAMPLE_HTML_CONTENT = """
<table>
    <tr class="banner">
        <td colspan="4">Werbung</td>
    </tr>
    <tr>
        <td class="zeit"><span class="time">10:00</span></td>
        <td class="sauna">Kelosauna 90°C</td>
        <td class="aufguss">
            <div class="aufguss">Finnischer Klassiker</div>
            <span class="info">Ein intensiver Aufguss</span>
        </td>
        <td class="duft">
            <span class="dufttext">Eukalyptus, Minze</span>
            <img src="/icons/intensiv.png" alt="intensiv"/>
        </td>
    </tr>
    <tr>
        <td class="zeit"><span class="time">11:30</span></td>
        <td class="sauna">Biosauna 55-60°C</td>
        <td class="aufguss">
            <div class="aufguss">Sanfter Wind</div>
        </td>
        <td class="duft">
            <span class="dufttext">Lavendel</span>
        </td>
    </tr>
    <tr>
        <td class="zeit"><span class="time">13:00</span></td>
        <td class="sauna">Dampfbad</td>
        <td class="aufguss">
            <div class="aufguss">Mentholfrische</div>
        </td>
        <td class="duft">
            <span class="dufttext">Menthol</span>
        </td>
    </tr>
</table>
"""

SAMPLE_HTML_EMPTY = """
<table>
    <tr class="banner">
        <td colspan="4">Keine Aufgüsse heute</td>
    </tr>
</table>
"""
