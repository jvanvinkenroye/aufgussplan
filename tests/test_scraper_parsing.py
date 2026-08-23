"""Tests für das HTML-Parsing in scraper.py (ohne Netzwerk)."""

from collections.abc import Callable

import pytest
from bs4 import BeautifulSoup, Tag

from aufgussplan.scraper import Aufguss, Aufgussplan, AufgussplanScraper


def _row(html: str) -> Tag:
    """Baut ein TR-Element aus einem HTML-Schnipsel."""
    soup = BeautifulSoup(f"<table>{html}</table>", "lxml")
    row = soup.find("tr")
    assert isinstance(row, Tag)
    return row


class TestParseContentTableBased:
    """Struktur 1: tabellenbasierte Pläne."""

    @pytest.fixture
    def plan(
        self, scraper: AufgussplanScraper, fixture_html: Callable[[str], str]
    ) -> Aufgussplan:
        return scraper.parse_content(fixture_html("table_based.html"), "fellbach")

    def test_extrahiert_alle_gueltigen_zeilen(self, plan: Aufgussplan) -> None:
        # Banner- und Header-Zeile werden übersprungen, 4 Datenzeilen bleiben
        assert [a.zeit for a in plan.aufguesse] == ["10:30", "14:00", "18:15", "9:30"]

    def test_standort_und_metadaten(self, plan: Aufgussplan) -> None:
        assert plan.standort == "fellbach"
        assert plan.abgerufen_am  # ISO-Zeitstempel gesetzt
        assert plan.legende == {}

    def test_vollstaendige_zeile(self, plan: Aufgussplan) -> None:
        a = plan.aufguesse[0]
        assert a.zeit == "10:30"
        assert a.sauna == "Kelosauna"
        assert a.temperatur == "90°C"
        assert a.aufguss_name == "Birkenaufguss"
        assert a.beschreibung == "Klassischer Aufguss mit Birkensud"
        assert a.duft == ["Birke", "Menthol"]
        assert a.eigenschaften == ["/icons/abc-123.png"]

    def test_zeile_ohne_optionale_felder(self, plan: Aufgussplan) -> None:
        a = plan.aufguesse[1]
        assert a.sauna == "Dampfbad"
        assert a.temperatur is None
        assert a.aufguss_name == "Salz-Peeling"
        assert a.duft == []
        assert a.beschreibung is None

    def test_temperaturbereich(self, plan: Aufgussplan) -> None:
        a = plan.aufguesse[2]
        assert a.temperatur == "80-90°C"
        assert a.sauna == "Panoramasauna"
        assert a.eigenschaften == ["/icons/uuid-1.png", "/icons/uuid-2.png"]

    def test_einstellige_stunde(self, plan: Aufgussplan) -> None:
        assert plan.aufguesse[3].zeit == "9:30"


class TestParseTableRow:
    def test_banner_zeile_wird_uebersprungen(
        self, scraper: AufgussplanScraper
    ) -> None:
        row = _row('<tr class="banner"><td>Werbung</td><td>mehr</td></tr>')
        assert scraper._parse_table_row(row) is None

    def test_header_zeile_wird_uebersprungen(
        self, scraper: AufgussplanScraper
    ) -> None:
        row = _row("<tr><th>Zeit</th><th>Sauna</th></tr>")
        assert scraper._parse_table_row(row) is None

    def test_zeile_mit_einer_zelle_wird_uebersprungen(
        self, scraper: AufgussplanScraper
    ) -> None:
        row = _row("<tr><td>10:30</td></tr>")
        assert scraper._parse_table_row(row) is None

    def test_ungueltige_zeit_wird_verworfen(
        self, scraper: AufgussplanScraper
    ) -> None:
        row = _row('<tr><td class="zeit">bald</td><td class="sauna">X</td></tr>')
        assert scraper._parse_table_row(row) is None

    @pytest.mark.xfail(
        reason=(
            "Bekannte Lücke: der Fallback für Zeilen ohne td.zeit prüft zwar "
            "die erste Zelle auf eine Uhrzeit, weist sie aber nie zu — die "
            "Zeile wird immer verworfen (scraper.py, _parse_table_row)"
        ),
        strict=True,
    )
    def test_fallback_nutzt_erste_zelle_als_zeit(
        self, scraper: AufgussplanScraper
    ) -> None:
        row = _row("<tr><td>10:30</td><td>Kelosauna</td></tr>")
        aufguss = scraper._parse_table_row(row)
        assert aufguss is not None
        assert aufguss.zeit == "10:30"


class TestParseContentDivBased:
    """Struktur 2: div-basierte Pläne (Cards/Items)."""

    @pytest.fixture
    def plan(
        self, scraper: AufgussplanScraper, fixture_html: Callable[[str], str]
    ) -> Aufgussplan:
        return scraper.parse_content(fixture_html("div_based.html"), "obernsees")

    def test_nur_items_mit_uhrzeit(self, plan: Aufgussplan) -> None:
        assert [a.zeit for a in plan.aufguesse] == ["09:00", "11:30"]

    def test_temperatur_und_bilder(self, plan: Aufgussplan) -> None:
        a = plan.aufguesse[0]
        assert a.temperatur == "60°C"
        assert a.eigenschaften == ["Aufgusszeremonie"]
        assert a.bild_url == "/img/morgengruss.jpg"

    def test_item_ohne_bild(self, plan: Aufgussplan) -> None:
        a = plan.aufguesse[1]
        assert a.temperatur == "100°C"
        assert a.bild_url is None


class TestParseContentGeneric:
    """Struktur 3: generische Textextraktion als letzter Fallback."""

    @pytest.fixture
    def plan(
        self, scraper: AufgussplanScraper, fixture_html: Callable[[str], str]
    ) -> Aufgussplan:
        return scraper.parse_content(fixture_html("generic_text.html"), "aqualand")

    def test_findet_alle_zeiten(self, plan: Aufgussplan) -> None:
        assert [a.zeit for a in plan.aufguesse] == ["10:00", "12:00", "15:30"]

    def test_erkennt_sauna_und_temperatur_im_kontext(
        self, plan: Aufgussplan
    ) -> None:
        assert plan.aufguesse[0].sauna == "Kräutersauna"
        assert plan.aufguesse[0].temperatur == "85°C"
        assert plan.aufguesse[1].sauna == "Dampfbad"
        assert plan.aufguesse[2].sauna == ""

    def test_leere_seite_ergibt_leeren_plan(
        self, scraper: AufgussplanScraper, fixture_html: Callable[[str], str]
    ) -> None:
        plan = scraper.parse_content(fixture_html("empty.html"), "leer")
        assert plan.aufguesse == []


class TestParseLegende:
    def test_extrahiert_legende(
        self, scraper: AufgussplanScraper, fixture_html: Callable[[str], str]
    ) -> None:
        legende = scraper.parse_legende(fixture_html("legende.html"))
        assert legende == {
            "Handtuch": "Handtuch erforderlich",
            "Nur für Erwachsene": "Nur für Erwachsene",
        }

    def test_seite_ohne_legende(
        self, scraper: AufgussplanScraper, fixture_html: Callable[[str], str]
    ) -> None:
        assert scraper.parse_legende(fixture_html("empty.html")) == {}


class TestToDict:
    def test_aufguss_to_dict(self) -> None:
        a = Aufguss(zeit="10:30", sauna="Kelosauna", duft=["Birke"])
        d = a.to_dict()
        assert d["zeit"] == "10:30"
        assert d["sauna"] == "Kelosauna"
        assert d["duft"] == ["Birke"]
        assert d["temperatur"] is None
        assert d["mitarbeiter"] is None

    def test_plan_to_dict_zaehlt_aufguesse(self, sample_plan: Aufgussplan) -> None:
        d = sample_plan.to_dict()
        assert d["standort"] == "fellbach"
        assert d["anzahl_aufguesse"] == 2
        assert len(d["aufguesse"]) == 2
        assert d["legende"] == {"Handtuch": "Handtuch erforderlich"}
