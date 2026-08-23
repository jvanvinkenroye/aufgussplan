"""Tests für die HTTP-Schicht in scraper.py mit httpx.MockTransport."""

from collections.abc import Callable, Iterator

import httpx
import pytest

from aufgussplan.scraper import KNOWN_LOCATIONS, AufgussplanScraper

Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture
def make_scraper() -> Iterator[Callable[[Handler], AufgussplanScraper]]:
    """Erzeugt Scraper, deren Client gegen einen MockTransport läuft."""
    created: list[AufgussplanScraper] = []

    def _make(handler: Handler) -> AufgussplanScraper:
        s = AufgussplanScraper()
        s.client.close()
        s.client = httpx.Client(
            transport=httpx.MockTransport(handler), follow_redirects=False
        )
        created.append(s)
        return s

    yield _make
    for s in created:
        s.client.close()


def _respond(status: int, text: str = "") -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text=text)

    return handler


def _fail(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("Verbindung fehlgeschlagen", request=request)


class TestGetContent:
    def test_200_liefert_html(
        self, make_scraper: Callable[[Handler], AufgussplanScraper]
    ) -> None:
        s = make_scraper(_respond(200, "<html>plan</html>"))
        assert s.get_content("fellbach") == "<html>plan</html>"

    def test_302_bedeutet_standort_existiert_nicht(
        self, make_scraper: Callable[[Handler], AufgussplanScraper]
    ) -> None:
        # Die Seite leitet bei unbekannten Standorten um; der Client folgt
        # Redirects bewusst nicht (follow_redirects=False).
        s = make_scraper(_respond(302))
        assert s.get_content("gibtesnicht") is None

    def test_server_fehler_liefert_none(
        self, make_scraper: Callable[[Handler], AufgussplanScraper]
    ) -> None:
        s = make_scraper(_respond(500))
        assert s.get_content("fellbach") is None

    def test_netzwerkfehler_liefert_none(
        self, make_scraper: Callable[[Handler], AufgussplanScraper]
    ) -> None:
        s = make_scraper(_fail)
        assert s.get_content("fellbach") is None

    def test_ruft_content_url_auf(
        self, make_scraper: Callable[[Handler], AufgussplanScraper]
    ) -> None:
        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(str(request.url))
            return httpx.Response(200, text="ok")

        make_scraper(handler).get_content("fellbach")
        assert seen == ["https://www.aufgussplan.de/content/fellbach"]


class TestGetStandortPage:
    def test_200_liefert_html(
        self, make_scraper: Callable[[Handler], AufgussplanScraper]
    ) -> None:
        s = make_scraper(_respond(200, "<html>standort</html>"))
        assert s.get_standort_page("fellbach") == "<html>standort</html>"

    def test_fehler_liefert_none(
        self, make_scraper: Callable[[Handler], AufgussplanScraper]
    ) -> None:
        assert make_scraper(_respond(404)).get_standort_page("fellbach") is None
        assert make_scraper(_fail).get_standort_page("fellbach") is None


class TestCheckStandortExists:
    def test_200_existiert(
        self, make_scraper: Callable[[Handler], AufgussplanScraper]
    ) -> None:
        assert make_scraper(_respond(200, "ok")).check_standort_exists("fellbach")

    def test_302_existiert_nicht(
        self, make_scraper: Callable[[Handler], AufgussplanScraper]
    ) -> None:
        assert not make_scraper(_respond(302)).check_standort_exists("nope")

    def test_netzwerkfehler_existiert_nicht(
        self, make_scraper: Callable[[Handler], AufgussplanScraper]
    ) -> None:
        assert not make_scraper(_fail).check_standort_exists("fellbach")


CONTENT_HTML = """
<table>
  <tr>
    <td class="zeit">10:30</td>
    <td class="sauna">Kelosauna 90 &#176;C</td>
    <td class="aufguss">Birkenaufguss</td>
    <td class="duft"></td>
  </tr>
</table>
"""

STANDORT_HTML = """
<div class="legende">
  <div class="legende-item"><img src="/i/t.png" alt="Handtuch"/> Pflicht</div>
</div>
"""


class TestScrapeStandort:
    def test_kombiniert_content_und_legende(
        self, make_scraper: Callable[[Handler], AufgussplanScraper]
    ) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.startswith("/content/"):
                return httpx.Response(200, text=CONTENT_HTML)
            return httpx.Response(200, text=STANDORT_HTML)

        plan = make_scraper(handler).scrape_standort("fellbach")
        assert plan is not None
        assert plan.standort == "fellbach"
        assert [a.zeit for a in plan.aufguesse] == ["10:30"]
        assert plan.legende == {"Handtuch": "Pflicht"}

    def test_content_fehler_liefert_none(
        self, make_scraper: Callable[[Handler], AufgussplanScraper]
    ) -> None:
        assert make_scraper(_respond(302)).scrape_standort("nope") is None

    def test_legende_fehler_liefert_plan_ohne_legende(
        self, make_scraper: Callable[[Handler], AufgussplanScraper]
    ) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.startswith("/content/"):
                return httpx.Response(200, text=CONTENT_HTML)
            return httpx.Response(500)

        plan = make_scraper(handler).scrape_standort("fellbach")
        assert plan is not None
        assert plan.legende == {}


class TestScrapeAll:
    def test_ueberspringt_fehlgeschlagene_standorte(
        self, make_scraper: Callable[[Handler], AufgussplanScraper]
    ) -> None:
        ok = {"fellbach", "obernsees"}

        def handler(request: httpx.Request) -> httpx.Response:
            slug = request.url.path.rsplit("/", 1)[-1]
            if request.url.path.startswith("/content/") and slug in ok:
                return httpx.Response(200, text=CONTENT_HTML)
            if request.url.path.startswith("/standort/"):
                return httpx.Response(404)
            return httpx.Response(302)

        plaene = make_scraper(handler).scrape_all()
        assert [p.standort for p in plaene] == ["fellbach", "obernsees"]

    def test_known_locations_nicht_leer(self) -> None:
        assert len(KNOWN_LOCATIONS) == len(set(KNOWN_LOCATIONS))
        assert "fellbach" in KNOWN_LOCATIONS


def test_context_manager_schliesst_client() -> None:
    with AufgussplanScraper() as s:
        assert not s.client.is_closed
    assert s.client.is_closed
