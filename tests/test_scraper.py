"""Tests für den Aufgussplan Scraper."""

from pytest_httpx import HTTPXMock

from aufgussplan.scraper import (
    KNOWN_LOCATIONS,
    Aufguss,
    Aufgussplan,
    AufgussplanScraper,
)

from .conftest import SAMPLE_HTML_CONTENT, SAMPLE_HTML_EMPTY


class TestAufguss:
    """Tests für die Aufguss-Dataclass."""

    def test_to_dict_minimal(self) -> None:
        """Minimaler Aufguss kann zu Dict konvertiert werden."""
        aufguss = Aufguss(zeit="10:00", sauna="Kelosauna")
        result = aufguss.to_dict()

        assert result["zeit"] == "10:00"
        assert result["sauna"] == "Kelosauna"
        assert result["temperatur"] is None
        assert result["aufguss_name"] == ""
        assert result["duft"] == []

    def test_to_dict_full(self, sample_aufguss: Aufguss) -> None:
        """Vollständiger Aufguss kann zu Dict konvertiert werden."""
        result = sample_aufguss.to_dict()

        assert result["zeit"] == "10:00"
        assert result["sauna"] == "Kelosauna"
        assert result["temperatur"] == "90°C"
        assert result["aufguss_name"] == "Finnischer Klassiker"
        assert result["duft"] == ["Eukalyptus", "Minze"]
        assert result["beschreibung"] == "Ein klassischer Aufguss"


class TestAufgussplan:
    """Tests für die Aufgussplan-Dataclass."""

    def test_to_dict_empty(self) -> None:
        """Leerer Aufgussplan kann zu Dict konvertiert werden."""
        plan = Aufgussplan(standort="fellbach", abgerufen_am="2026-05-30T10:00:00")
        result = plan.to_dict()

        assert result["standort"] == "fellbach"
        assert result["abgerufen_am"] == "2026-05-30T10:00:00"
        assert result["anzahl_aufguesse"] == 0
        assert result["aufguesse"] == []

    def test_to_dict_with_aufguesse(self, sample_aufgussplan: Aufgussplan) -> None:
        """Aufgussplan mit Aufgüssen kann zu Dict konvertiert werden."""
        result = sample_aufgussplan.to_dict()

        assert result["standort"] == "fellbach"
        assert result["anzahl_aufguesse"] == 2
        assert len(result["aufguesse"]) == 2
        assert result["aufguesse"][0]["zeit"] == "10:00"
        assert result["aufguesse"][1]["zeit"] == "11:00"


class TestAufgussplanScraper:
    """Tests für den AufgussplanScraper."""

    def test_known_locations_not_empty(self) -> None:
        """Bekannte Standorte sind definiert."""
        assert len(KNOWN_LOCATIONS) > 0
        assert "fellbach" in KNOWN_LOCATIONS

    def test_context_manager(self) -> None:
        """Scraper kann als Context-Manager verwendet werden."""
        with AufgussplanScraper() as scraper:
            assert scraper is not None

    def test_get_content_success(self, httpx_mock: HTTPXMock) -> None:
        """get_content gibt HTML bei Erfolg zurück."""
        httpx_mock.add_response(
            url="https://www.aufgussplan.de/content/fellbach",
            text=SAMPLE_HTML_CONTENT,
        )

        with AufgussplanScraper() as scraper:
            result = scraper.get_content("fellbach")

        assert result is not None
        assert "<table>" in result

    def test_get_content_redirect_returns_none(self, httpx_mock: HTTPXMock) -> None:
        """get_content gibt None bei Redirect (Standort existiert nicht)."""
        httpx_mock.add_response(
            url="https://www.aufgussplan.de/content/nonexistent",
            status_code=302,
        )

        with AufgussplanScraper() as scraper:
            result = scraper.get_content("nonexistent")

        assert result is None

    def test_get_content_error_returns_none(self, httpx_mock: HTTPXMock) -> None:
        """get_content gibt None bei HTTP-Fehler zurück."""
        httpx_mock.add_response(
            url="https://www.aufgussplan.de/content/fellbach",
            status_code=500,
        )

        with AufgussplanScraper() as scraper:
            result = scraper.get_content("fellbach")

        assert result is None

    def test_parse_content_extracts_aufguesse(self) -> None:
        """parse_content extrahiert Aufgüsse aus HTML."""
        with AufgussplanScraper() as scraper:
            plan = scraper.parse_content(SAMPLE_HTML_CONTENT, "fellbach")

        assert plan.standort == "fellbach"
        assert len(plan.aufguesse) == 3

        first = plan.aufguesse[0]
        assert first.zeit == "10:00"
        assert first.sauna == "Kelosauna"
        assert first.temperatur == "90°C"
        assert first.aufguss_name == "Finnischer Klassiker"
        assert "Eukalyptus" in first.duft
        assert "Minze" in first.duft

    def test_parse_content_handles_temperature_range(self) -> None:
        """parse_content extrahiert Temperatur-Bereiche korrekt."""
        with AufgussplanScraper() as scraper:
            plan = scraper.parse_content(SAMPLE_HTML_CONTENT, "fellbach")

        biosauna = plan.aufguesse[1]
        assert biosauna.temperatur == "55-60°C"
        assert "Biosauna" in biosauna.sauna

    def test_parse_content_skips_banner_rows(self) -> None:
        """parse_content überspringt Banner-Zeilen."""
        with AufgussplanScraper() as scraper:
            plan = scraper.parse_content(SAMPLE_HTML_CONTENT, "fellbach")

        for aufguss in plan.aufguesse:
            assert "Werbung" not in aufguss.sauna
            assert "Werbung" not in aufguss.aufguss_name

    def test_parse_content_empty_table(self) -> None:
        """parse_content gibt leeren Plan bei leerer Tabelle."""
        with AufgussplanScraper() as scraper:
            plan = scraper.parse_content(SAMPLE_HTML_EMPTY, "fellbach")

        assert plan.standort == "fellbach"
        assert len(plan.aufguesse) == 0

    def test_scrape_standort_success(self, httpx_mock: HTTPXMock) -> None:
        """scrape_standort kombiniert get_content und parse_content."""
        httpx_mock.add_response(
            url="https://www.aufgussplan.de/content/fellbach",
            text=SAMPLE_HTML_CONTENT,
        )
        httpx_mock.add_response(
            url="https://www.aufgussplan.de/standort/fellbach",
            text="<html><body>Standort-Seite</body></html>",
        )

        with AufgussplanScraper() as scraper:
            plan = scraper.scrape_standort("fellbach")

        assert plan is not None
        assert plan.standort == "fellbach"
        assert len(plan.aufguesse) == 3

    def test_scrape_standort_not_found(self, httpx_mock: HTTPXMock) -> None:
        """scrape_standort gibt None wenn Standort nicht existiert."""
        httpx_mock.add_response(
            url="https://www.aufgussplan.de/content/nonexistent",
            status_code=302,
        )

        with AufgussplanScraper() as scraper:
            plan = scraper.scrape_standort("nonexistent")

        assert plan is None

    def test_check_standort_exists_true(self, httpx_mock: HTTPXMock) -> None:
        """check_standort_exists gibt True bei existierendem Standort."""
        httpx_mock.add_response(
            url="https://www.aufgussplan.de/content/fellbach",
            status_code=200,
        )

        with AufgussplanScraper() as scraper:
            result = scraper.check_standort_exists("fellbach")

        assert result is True

    def test_check_standort_exists_false(self, httpx_mock: HTTPXMock) -> None:
        """check_standort_exists gibt False bei nicht-existierendem Standort."""
        httpx_mock.add_response(
            url="https://www.aufgussplan.de/content/nonexistent",
            status_code=302,
        )

        with AufgussplanScraper() as scraper:
            result = scraper.check_standort_exists("nonexistent")

        assert result is False

    def test_scrape_all(self, httpx_mock: HTTPXMock) -> None:
        """scrape_all scraped alle bekannten Standorte."""
        for standort in KNOWN_LOCATIONS:
            httpx_mock.add_response(
                url=f"https://www.aufgussplan.de/content/{standort}",
                text=SAMPLE_HTML_CONTENT,
            )
            httpx_mock.add_response(
                url=f"https://www.aufgussplan.de/standort/{standort}",
                text="<html></html>",
            )

        with AufgussplanScraper() as scraper:
            results = scraper.scrape_all()

        assert len(results) == len(KNOWN_LOCATIONS)
        for plan in results:
            assert plan.standort in KNOWN_LOCATIONS
