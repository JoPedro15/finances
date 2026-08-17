"""
Infrastructure client for scraping ETF details from JustETF.
"""

from __future__ import annotations

import re

import requests
from bs4 import BeautifulSoup, Tag
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from src.core.exceptions import JustETFScrapeError
from src.core.models import (
    CountryExposure,
    ETFDetails,
    Holding,
    SectorExposure,
)


class JustETFClient:
    """Scraper client for retrieving ETF holdings and exposure details from JustETF."""

    BASE_URL: str = "https://www.justetf.com/en/etf-profile.html"
    DEFAULT_HEADERS: dict[str, str] = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    def __init__(self, timeout: float = 10.0, max_retries: int = 3) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(self.DEFAULT_HEADERS)

        retries = Retry(
            total=max_retries,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def get_etf_details(self, isin: str) -> ETFDetails:
        """
        Fetches and parses ETF profile page for the given ISIN.

        Raises:
            JustETFScrapeError: If request fails or HTML cannot be parsed.
        """
        url = f"{self.BASE_URL}?isin={isin}"
        try:
            response = self.session.get(url, timeout=self.timeout)
            if response.status_code != 200:
                raise JustETFScrapeError(
                    f"HTTP error {response.status_code} while fetching ISIN {isin}"
                )
        except requests.RequestException as e:
            raise JustETFScrapeError(
                f"Network error fetching JustETF page for {isin}: {e}"
            ) from e

        try:
            soup = BeautifulSoup(response.text, "html.parser")
            holdings = self._parse_holdings(soup)
            sectors = self._parse_sectors(soup)
            countries = self._parse_countries(soup)
            ter_pct = self._parse_ter(soup)

            return ETFDetails(
                holdings=holdings,
                sector_breakdown=sectors,
                country_breakdown=countries,
                ter_pct=ter_pct,
            )
        except Exception as e:
            if isinstance(e, JustETFScrapeError):
                raise
            raise JustETFScrapeError(
                f"Failed to parse JustETF response for ISIN {isin}: {e}"
            ) from e

    def _parse_holdings(self, soup: BeautifulSoup) -> list[Holding]:
        holdings: list[Holding] = []

        table = soup.find("table", {"id": "top-holdings"})
        if not isinstance(table, Tag):
            container = soup.find(
                lambda tag: tag.name in ["div", "section", "table"]
                and tag.get("id")
                and "holding" in str(tag.get("id")).lower()
            )
            if isinstance(container, Tag):
                table = (
                    container if container.name == "table" else container.find("table")
                )

        if not isinstance(table, Tag):
            for tbl in soup.find_all("table"):
                header_text = tbl.get_text().lower()
                if (
                    "holding" in header_text
                    or "weight" in header_text
                    or "name" in header_text
                ) and "inception" not in header_text:
                    table = tbl
                    break

        if not isinstance(table, Tag):
            return holdings

        for row in table.find_all("tr"):
            cols = row.find_all(["td", "th"])
            if len(cols) < 2:
                continue

            name = cols[0].get_text(strip=True)
            if not name or name.lower() in [
                "name",
                "holding",
                "top holdings",
                "weight",
            ]:
                continue

            weight_text = cols[-1].get_text(strip=True)
            match = re.search(r"(\d+[.,]?\d*)\s*%", weight_text)
            if match:
                try:
                    weight_pct = float(match.group(1).replace(",", "."))
                    holdings.append(
                        Holding(
                            name=name,
                            isin="",
                            ticker=None,
                            weight_pct=weight_pct,
                        )
                    )
                except ValueError:
                    continue

        return holdings

    def _parse_sectors(self, soup: BeautifulSoup) -> list[SectorExposure]:
        sectors: list[SectorExposure] = []
        container = soup.find("div", {"id": "sectors"})
        if not isinstance(container, Tag):
            container = soup.find(
                lambda tag: tag.name in ["div", "section", "table"]
                and tag.get("id")
                and "sector" in str(tag.get("id")).lower()
            )

        target = container if isinstance(container, Tag) else soup
        rows = target.find_all("tr") if isinstance(target, Tag) else []

        for row in rows:
            cols = row.find_all(["td", "th"])
            if len(cols) >= 2:
                sector_name = cols[0].get_text(strip=True)
                if not sector_name or sector_name.lower() in [
                    "sector",
                    "name",
                    "weight",
                ]:
                    continue

                weight_text = cols[1].get_text(strip=True)
                match = re.search(r"(\d+[.,]?\d*)\s*%", weight_text)
                if match:
                    try:
                        weight_pct = float(match.group(1).replace(",", "."))
                        sectors.append(
                            SectorExposure(
                                sector_name=sector_name,
                                weight_pct=weight_pct,
                            )
                        )
                    except ValueError:
                        continue

        return sectors

    def _parse_countries(self, soup: BeautifulSoup) -> list[CountryExposure]:
        countries: list[CountryExposure] = []
        container = soup.find("div", {"id": "countries"})
        if not isinstance(container, Tag):
            container = soup.find(
                lambda tag: tag.name in ["div", "section", "table"]
                and tag.get("id")
                and "countr" in str(tag.get("id")).lower()
            )

        target = container if isinstance(container, Tag) else soup
        rows = target.find_all("tr") if isinstance(target, Tag) else []

        for row in rows:
            cols = row.find_all(["td", "th"])
            if len(cols) >= 2:
                country_name = cols[0].get_text(strip=True)
                if not country_name or country_name.lower() in [
                    "country",
                    "name",
                    "weight",
                ]:
                    continue

                weight_text = cols[1].get_text(strip=True)
                match = re.search(r"(\d+[.,]?\d*)\s*%", weight_text)
                if match:
                    try:
                        weight_pct = float(match.group(1).replace(",", "."))
                        countries.append(
                            CountryExposure(
                                country_name=country_name,
                                weight_pct=weight_pct,
                            )
                        )
                    except ValueError:
                        continue

        return countries

    def _parse_ter(self, soup: BeautifulSoup) -> float | None:
        for label in soup.find_all(
            string=re.compile(r"TER|Total\s*Expense\s*Ratio", re.IGNORECASE)
        ):
            parent = label.parent
            if parent:
                search_scope = parent.parent if parent.parent else parent
                text_content = search_scope.get_text()
                match = re.search(r"(\d+[.,]?\d*)\s*%", text_content)
                if match:
                    try:
                        return float(match.group(1).replace(",", "."))
                    except ValueError:
                        pass
        return None
