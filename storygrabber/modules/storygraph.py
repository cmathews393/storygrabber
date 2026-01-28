"""Storygraph module."""

import os
import re

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from storygrabber.modules.util import write_cache


class Storygraph:
    """Module to interact with Storygraph."""

    results_count_name = (
        "search-results-count"  # this has changed before, make it easier to update.
    )
    results_count_regex = rf'<p class="{re.escape(results_count_name)}">(\d+) books</p>'
    book_html_blocks = "div.book-pane, div.book-pane-content, div.book-title-author-and-series, article.book-tile"
    sg_wtr_page_size = 10  # could change

    def __init__(self: "Storygraph", fs_session: str | None = None) -> None:
        """Init storygraph vars etc."""
        self.sg_base_url = "https://app.thestorygraph.com/to-read/"
        self.fs_session = fs_session
        self.fs_url = "http://192.168.1.222:8191/v1"
        self.client = httpx.Client(
            timeout=60,
        )  # This is the timeout for calling FlareSolverR

        self.session_created = False
        if fs_session is None:
            self.session_id = self._create_fs_session()
        else:
            self.session_id = fs_session

    def _create_fs_session(self: "Storygraph") -> str:
        """Create new flaresolverr session."""
        fs_timeout = os.getenv("FLARESOLVERR_TIMEOUT", "120000")
        fs_payload = {
            "cmd": "sessions.create",
            "maxTimeout": int(fs_timeout),
        }
        print(self.fs_url)
        response = self.client.post(self.fs_url, json=fs_payload)
        print(response.text)
        response.raise_for_status()
        self.session_created = True
        return response.json().get("session")

    def _destroy_fs_session(self: "Storygraph") -> None:
        """Destroy flaresolverr session."""
        if self.session_id is not None or self.session_created is True:
            fs_payload = {
                "cmd": "sessions.destroy",
                "session": self.session_id,
            }
            response = self.client.post(self.fs_url, json=fs_payload)

        response.raise_for_status()
        self.session_created = False
        self.session_id = None

    def _extract_books_from_soup(self, soup: BeautifulSoup, seen_books: set) -> list:
        """Extract book information from BeautifulSoup object."""
        found_books = []
        book_blocks = soup.select(self.book_html_blocks)
        for block in book_blocks:
            book_link = (
                block.select_one("a[href^='/books/']")
                or block.select_one("h3 a")
                or block.find("a")
            )
            if not book_link:
                continue

            book_url = book_link.get("href", "")
            if isinstance(book_url, str) and book_url.startswith("/"):
                book_url = f"https://app.thestorygraph.com{book_url}"

            book_title = book_link.get_text(strip=True) if book_link else ""

            author_link = block.select_one("a[href^='/authors/']") or block.select_one(
                "p.font-body a",
            )
            author = author_link.get_text(strip=True) if author_link else ""

            if not book_title:
                continue

            identifier = book_url or f"{book_title}|{author}"
            if identifier in seen_books:
                continue

            seen_books.add(identifier)
            found_books.append((book_url, book_title, author))
        return found_books

    def _get_book_count(self: "Storygraph", sg_response: str) -> int | None:
        """Helper function to handle regex."""
        if self.results_count_name in sg_response:
            book_count_pattern_match = re.search(
                self.results_count_regex,
                sg_response,
            )
            if book_count_pattern_match:
                return int(book_count_pattern_match.group(1))
        return None

    def _write_sg_cache(self: "Storygraph", username: str, books: list) -> None:
        """Write the Storygraph cache."""
        write_cache("storygraph", username, books)

    def get_books(self: "Storygraph", username: str) -> list[dict]:
        """Retrieve all WTR books with pagination."""
        fs_payload = {
            "cmd": "request.get",
            "session": self.session_id,
            "url": f"{self.sg_base_url}{username}",
        }
        books_req = self.client.post(self.fs_url, json=fs_payload)
        books_req.raise_for_status()
        sg_response = books_req.json().get("solution").get("response")
        soup = BeautifulSoup(sg_response, "html.parser")
        book_count = self._get_book_count(sg_response)
        if book_count:
            logger.error(book_count)
            seen_books = set()  # Titles appear multiple times in blocks, could trim logic down but haven't yet. Right now we just find dupes.
            if book_count > self.sg_wtr_page_size:
                iterations = book_count // self.sg_wtr_page_size
                if book_count % self.sg_wtr_page_size != 0:
                    iterations += 1
                books = self._extract_books_from_soup(soup, seen_books)
                for i in range(iterations):
                    current_page = f"{self.sg_base_url}{username}?page={i + 1}"
                    logger.debug(f"Fetching page {i}: {current_page}")
                    fs_payload = {
                        "cmd": "request.get",
                        "session": self.session_id,
                        "url": current_page,
                    }
                    books_req = self.client.post(self.fs_url, json=fs_payload)
                    books_req.raise_for_status()
                    sg_response = books_req.json().get("solution").get("response")
                    soup = BeautifulSoup(sg_response, "html.parser")
                    new_books = self._extract_books_from_soup(soup, seen_books)
                    if new_books:
                        books.extend(new_books)

            if book_count <= self.sg_wtr_page_size:
                books = self._extract_books_from_soup(sg_response, seen_books)
        self._destroy_fs_session()
        self._write_sg_cache(username, books)
        return books
