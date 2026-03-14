"""Scraper für aufgussplan.de - Extrahiert Aufgusspläne als strukturierte Daten."""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup, Tag

# Bekannte aktive Standorte
KNOWN_LOCATIONS = [
    "fellbach",
    "vierordtbad",
    "karlsruhe",
    "obernsees",
    "obertshausen",
    "aqualand",
    "koblenz",
    "fuerth",
    "budenheim",
    "kelsterbach",
]

BASE_URL = "https://www.aufgussplan.de"


@dataclass
class Aufguss:
    """Einzelner Aufguss-Eintrag."""

    zeit: str
    sauna: str
    temperatur: str | None = None
    aufguss_name: str = ""
    duft: list[str] = field(default_factory=list)
    mitarbeiter: str | None = None
    beschreibung: str | None = None
    eigenschaften: list[str] = field(default_factory=list)
    bild_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Konvertiert zu Dictionary für JSON-Export."""
        return {
            "zeit": self.zeit,
            "sauna": self.sauna,
            "temperatur": self.temperatur,
            "aufguss_name": self.aufguss_name,
            "duft": self.duft,
            "mitarbeiter": self.mitarbeiter,
            "beschreibung": self.beschreibung,
            "eigenschaften": self.eigenschaften,
            "bild_url": self.bild_url,
        }


@dataclass
class Aufgussplan:
    """Aufgussplan für einen Standort."""

    standort: str
    abgerufen_am: str
    aufguesse: list[Aufguss] = field(default_factory=list)
    legende: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Konvertiert zu Dictionary für JSON-Export."""
        return {
            "standort": self.standort,
            "abgerufen_am": self.abgerufen_am,
            "anzahl_aufguesse": len(self.aufguesse),
            "legende": self.legende,
            "aufguesse": [a.to_dict() for a in self.aufguesse],
        }


class AufgussplanScraper:
    """Scraper für aufgussplan.de."""

    def __init__(self, timeout: float = 10.0) -> None:
        """Initialisiert den Scraper.

        Args:
            timeout: HTTP-Timeout in Sekunden
        """
        self.client = httpx.Client(
            timeout=timeout,
            headers={
                "User-Agent": "AufgussplanScraper/0.1 (Python)",
                "Accept": "text/html,application/xhtml+xml",
            },
            follow_redirects=False,
        )

    def __enter__(self) -> "AufgussplanScraper":
        return self

    def __exit__(self, *args: Any) -> None:
        self.client.close()

    def get_content(self, standort: str) -> str | None:
        """Ruft den HTML-Content für einen Standort ab.

        Args:
            standort: Standort-Slug (z.B. 'fellbach')

        Returns:
            HTML-Content oder None bei Fehler
        """
        url = f"{BASE_URL}/content/{standort}"
        try:
            response = self.client.get(url)
            if response.status_code == 200:
                return response.text
            elif response.status_code == 302:
                # Redirect = Standort existiert nicht
                return None
            else:
                return None
        except httpx.HTTPError:
            return None

    def get_standort_page(self, standort: str) -> str | None:
        """Ruft die vollständige Standort-Seite ab (für Legende).

        Args:
            standort: Standort-Slug

        Returns:
            HTML-Content oder None bei Fehler
        """
        url = f"{BASE_URL}/standort/{standort}"
        try:
            response = self.client.get(url)
            if response.status_code == 200:
                return response.text
            return None
        except httpx.HTTPError:
            return None

    def parse_legende(self, html: str) -> dict[str, str]:
        """Extrahiert die Legende (Symbole und Bedeutungen).

        Args:
            html: HTML-Content der Standort-Seite

        Returns:
            Dictionary mit Symbol-Name -> Beschreibung
        """
        soup = BeautifulSoup(html, "lxml")
        legende: dict[str, str] = {}

        # Suche nach Legende-Elementen (meist in .legende oder ähnlich)
        legende_container = soup.find("div", class_="legende")
        if legende_container and isinstance(legende_container, Tag):
            items = legende_container.find_all("div", class_="legende-item")
            for item in items:
                if isinstance(item, Tag):
                    img = item.find("img")
                    text = item.get_text(strip=True)
                    if img and isinstance(img, Tag) and img.get("alt"):
                        legende[str(img["alt"])] = text
                    elif text:
                        legende[text] = text

        return legende

    def parse_content(self, html: str, standort: str) -> Aufgussplan:
        """Parst den Aufgussplan-Content.

        Args:
            html: HTML-Content von /content/{standort}
            standort: Standort-Name

        Returns:
            Aufgussplan-Objekt mit allen extrahierten Daten
        """
        soup = BeautifulSoup(html, "lxml")
        plan = Aufgussplan(
            standort=standort,
            abgerufen_am=datetime.now().isoformat(),
        )

        # Versuche verschiedene HTML-Strukturen zu parsen
        # Struktur 1: Tabellen-basiert
        tables = soup.find_all("table")
        for table in tables:
            if isinstance(table, Tag):
                rows = table.find_all("tr")
                for row in rows:
                    if isinstance(row, Tag):
                        aufguss = self._parse_table_row(row)
                        if aufguss:
                            plan.aufguesse.append(aufguss)

        # Struktur 2: Div-basiert (cards/items)
        if not plan.aufguesse:
            items = soup.find_all("div", class_=re.compile(r"aufguss|item|entry"))
            for item in items:
                if isinstance(item, Tag):
                    aufguss = self._parse_div_item(item)
                    if aufguss:
                        plan.aufguesse.append(aufguss)

        # Struktur 3: Allgemeine Extraktion
        if not plan.aufguesse:
            plan.aufguesse = self._parse_generic(soup)

        return plan

    def _parse_table_row(self, row: Tag) -> Aufguss | None:
        """Parst eine Tabellenzeile.

        Args:
            row: TR-Element

        Returns:
            Aufguss-Objekt oder None
        """
        # Überspringe Banner-Zeilen und Header
        row_class = row.get("class")
        if isinstance(row_class, list) and "banner" in row_class:
            return None

        # Suche nach spezifischen Zellen
        zeit_cell = row.find("td", class_="zeit")
        sauna_cell = row.find("td", class_="sauna")
        aufguss_cell = row.find("td", class_="aufguss")
        duft_cell = row.find("td", class_="duft")

        # Fallback: alle Zellen
        if not zeit_cell:
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                return None
            # Versuche Zeit aus erster Zelle
            first_text = cells[0].get_text(strip=True) if cells else ""
            if not re.match(r"\d{1,2}:\d{2}", first_text):
                return None

        # Extrahiere Zeit
        zeit = ""
        if zeit_cell and isinstance(zeit_cell, Tag):
            zeit_span = zeit_cell.find("span", class_="time")
            if zeit_span:
                zeit = zeit_span.get_text(strip=True)
            else:
                zeit = zeit_cell.get_text(strip=True)

        if not zeit or not re.match(r"\d{1,2}:\d{2}", zeit):
            return None

        aufguss = Aufguss(zeit=zeit, sauna="")

        # Extrahiere Sauna
        if sauna_cell and isinstance(sauna_cell, Tag):
            sauna_text = sauna_cell.get_text(strip=True)
            # Extrahiere Temperatur
            temp_match = re.search(r"(\d+(?:-\d+)?)\s*°C", sauna_text)
            if temp_match:
                aufguss.temperatur = f"{temp_match.group(1)}°C"
                aufguss.sauna = re.sub(r"\d+(?:-\d+)?\s*°C", "", sauna_text).strip()
            else:
                aufguss.sauna = sauna_text

        # Extrahiere Aufguss-Name
        if aufguss_cell and isinstance(aufguss_cell, Tag):
            aufguss_div = aufguss_cell.find("div", class_="aufguss")
            if aufguss_div:
                aufguss.aufguss_name = aufguss_div.get_text(strip=True)
            else:
                aufguss.aufguss_name = aufguss_cell.get_text(strip=True)

            # Extrahiere Info/Beschreibung
            info_span = aufguss_cell.find("span", class_="info")
            if info_span:
                aufguss.beschreibung = info_span.get_text(strip=True)

        # Extrahiere Duft und Eigenschaften
        if duft_cell and isinstance(duft_cell, Tag):
            duft_text = duft_cell.find("span", class_="dufttext")
            if duft_text:
                duft_str = duft_text.get_text(strip=True)
                if duft_str:
                    aufguss.duft = [d.strip() for d in duft_str.split(",")]

            # Eigenschaften aus Icons
            imgs = duft_cell.find_all("img")
            for img in imgs:
                if isinstance(img, Tag):
                    src = img.get("src", "")
                    if src:
                        # Extrahiere UUID aus Pfad
                        aufguss.eigenschaften.append(str(src))

        return aufguss if aufguss.zeit else None

    def _parse_div_item(self, item: Tag) -> Aufguss | None:
        """Parst ein Div-Element.

        Args:
            item: Div-Element

        Returns:
            Aufguss-Objekt oder None
        """
        text = item.get_text(" ", strip=True)

        # Suche nach Zeit
        zeit_match = re.search(r"(\d{1,2}:\d{2})", text)
        if not zeit_match:
            return None

        aufguss = Aufguss(zeit=zeit_match.group(1), sauna="")

        # Temperatur
        temp_match = re.search(r"(\d+)\s*°C", text)
        if temp_match:
            aufguss.temperatur = f"{temp_match.group(1)}°C"

        # Bilder
        imgs = item.find_all("img")
        for img in imgs:
            if isinstance(img, Tag):
                alt = img.get("alt", "")
                src = img.get("src", "")
                if alt:
                    aufguss.eigenschaften.append(str(alt))
                if src and not aufguss.bild_url:
                    aufguss.bild_url = str(src)

        return aufguss

    def _parse_generic(self, soup: BeautifulSoup) -> list[Aufguss]:
        """Generische Extraktion wenn andere Methoden fehlschlagen.

        Args:
            soup: BeautifulSoup-Objekt

        Returns:
            Liste von Aufguss-Objekten
        """
        aufguesse: list[Aufguss] = []
        text = soup.get_text(" ", strip=True)

        # Finde alle Zeitangaben und extrahiere Kontext
        zeit_pattern = re.compile(r"(\d{1,2}:\d{2})")
        matches = list(zeit_pattern.finditer(text))

        for i, match in enumerate(matches):
            zeit = match.group(1)

            # Extrahiere Text bis zur nächsten Zeit
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            context = text[start:end][:200]  # Max 200 Zeichen

            aufguss = Aufguss(zeit=zeit, sauna="")

            # Temperatur
            temp_match = re.search(r"(\d+)\s*°C", context)
            if temp_match:
                aufguss.temperatur = f"{temp_match.group(1)}°C"

            # Sauna-Name (häufige Muster)
            sauna_match = re.search(
                r"([\w\-]+sauna|[\w\-]+bad|Kelosauna|Dampfbad|Biosauna)",
                context,
                re.IGNORECASE,
            )
            if sauna_match:
                aufguss.sauna = sauna_match.group(1)

            aufguesse.append(aufguss)

        return aufguesse

    def scrape_standort(self, standort: str) -> Aufgussplan | None:
        """Scraped einen kompletten Standort.

        Args:
            standort: Standort-Slug

        Returns:
            Aufgussplan-Objekt oder None bei Fehler
        """
        # Hole Content
        content_html = self.get_content(standort)
        if not content_html:
            return None

        # Parse Content
        plan = self.parse_content(content_html, standort)

        # Hole Legende von Standort-Seite
        standort_html = self.get_standort_page(standort)
        if standort_html:
            plan.legende = self.parse_legende(standort_html)

        return plan

    def scrape_all(self) -> list[Aufgussplan]:
        """Scraped alle bekannten Standorte.

        Returns:
            Liste von Aufgussplan-Objekten
        """
        results: list[Aufgussplan] = []
        for standort in KNOWN_LOCATIONS:
            plan = self.scrape_standort(standort)
            if plan:
                results.append(plan)
        return results

    def check_standort_exists(self, standort: str) -> bool:
        """Prüft ob ein Standort existiert.

        Args:
            standort: Standort-Slug

        Returns:
            True wenn Standort existiert
        """
        url = f"{BASE_URL}/content/{standort}"
        try:
            response = self.client.get(url)
            return response.status_code == 200
        except httpx.HTTPError:
            return False
