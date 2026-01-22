from loguru import logger
import httpx
import os
import re
from bs4 import BeautifulSoup


class StoryGrabber:
    def __init__(
        self: "StoryGrabber", sg_user: str, session_id: str | None = None
    ) -> None:
        self.client = httpx.Client(timeout=60)
        self.base_url = os.getenv("FS_URL", "localhost:8191/v1")
        self.sg_username = sg_user
        self.sg_url = f"https://app.thestorygraph.com/to-read/{self.sg_username}"
        self.session_created = False

        logger.debug(f"Initializing StoryGrabber for user: {sg_user}")
        logger.debug(f"Using FlaresolverR URL: {self.base_url}")

        # Use provided session or create a new one
        if session_id:
            self.session_id = session_id
            logger.info(f"Using existing FlaresolverR session: {self.session_id}")
        else:
            body = {
                "cmd": "sessions.create",
                "maxTimeout": 120000,
            }

            logger.debug("Creating FlaresolverR session...")
            session_req = self.client.post(self.base_url, json=body)
            logger.debug(f"Session response status: {session_req.status_code}")

            if session_req.status_code != 200:
                logger.error(f"Failed to create session: {session_req.text}")

            self.session_id = session_req.json().get("session")
            self.session_created = True
            logger.info(f"Session created successfully with ID: {self.session_id}")

    def destroy_session(self) -> None:
        """Destroy FlaresolverR session if it was created by this instance"""
        if self.session_created and self.session_id:
            destroy_body = {
                "cmd": "sessions.destroy",
                "session": self.session_id,
            }
            destroy_req = self.client.post(self.base_url, json=destroy_body)
            if destroy_req.status_code == 200:
                logger.info("Session destroyed successfully")
            else:
                logger.error(f"Failed to destroy session: {destroy_req.text}")

    def get_books(self: "StoryGrabber") -> list[dict]:
        logger.info(f"Fetching books for user: {self.sg_username}")

        body = {
            "cmd": "request.get",
            "session": self.session_id,
            "url": self.sg_url,
        }

        logger.debug(f"Sending request to: {self.sg_url}")
        books_req = self.client.post(self.base_url, json=body)

        if books_req.status_code == 200:
            logger.debug("Initial request successful")
            response = books_req.json().get("solution").get("response")

            # Log response size and first part to help debug
            logger.debug(f"Response size: {len(response)} characters")
            logger.debug(f"First 500 chars of response: {response[:500]}")

            # Check if the search-results-count pattern exists
            if "search-results-count" in response:
                logger.debug("Found 'search-results-count' pattern in response")
                # Extract the number of books using regex - updated to match just the class name
                book_count_match = re.search(
                    r'<p class="search-results-count">(\d+) books</p>', response
                )
                if book_count_match:
                    book_count = int(book_count_match.group(1))
                    logger.info(f"Found {book_count} books to process")

                    iterations = book_count // 10
                    if book_count % 10 != 0:
                        iterations += 1
                    logger.debug(f"Will need to process {iterations} pages")

                    books = []
                    seen_books = set()
                    for i in range(iterations):
                        page_num = i + 1
                        logger.debug(f"Processing page {page_num} of {iterations}")

                        # Fetch each page via FlaresolverR so we get paginated results
                        page_url = f"{self.sg_url}?page={page_num}"
                        page_body = {
                            "cmd": "request.get",
                            "session": self.session_id,
                            "url": page_url,
                        }
                        page_req = self.client.post(self.base_url, json=page_body)
                        if page_req.status_code != 200:
                            logger.warning(
                                f"Failed to fetch page {page_num}: {page_req.status_code}"
                            )
                            continue

                        page_response = (
                            page_req.json().get("solution", {}).get("response", "")
                        )
                        soup = BeautifulSoup(page_response, "html.parser")

                        # Extract books using helper to keep logic DRY
                        new_books = self._extract_books_from_soup(soup, seen_books)
                        if new_books:
                            books.extend(new_books)

                    logger.success(f"Successfully extracted {len(books)} books")

                    # Don't destroy the session here anymore, we'll do it in main()
                    return books
                else:
                    logger.warning("Could not extract book count from page")
                    # Log some context around where we expected to find it
                    search_pattern = "search-results-count"
                    idx = response.find(search_pattern)
                    if idx != -1:
                        context_start = max(0, idx - 100)
                        context_end = min(len(response), idx + 200)
                        logger.debug(
                            f"Context around pattern: {response[context_start:context_end]}"
                        )
            else:
                logger.warning("No 'search-results-count' pattern found in response")

                # Fallback: try iterative pagination until no new books are discovered.
                books = []
                seen_books = set()
                page_num = 1
                max_pages = 50  # safety cap to prevent infinite loops

                while page_num <= max_pages:
                    logger.debug(f"Fetching page {page_num} (iterative fallback)")
                    page_url = f"{self.sg_url}?page={page_num}"
                    page_body = {
                        "cmd": "request.get",
                        "session": self.session_id,
                        "url": page_url,
                    }
                    page_req = self.client.post(self.base_url, json=page_body)
                    if page_req.status_code != 200:
                        logger.warning(
                            f"Failed to fetch page {page_num}: {page_req.status_code}"
                        )
                        break

                    page_response = (
                        page_req.json().get("solution", {}).get("response", "")
                    )
                    soup = BeautifulSoup(page_response, "html.parser")

                    # Extract books using the same helper; stop if no new books are found
                    new_books = self._extract_books_from_soup(soup, seen_books)
                    if not new_books:
                        logger.debug(
                            f"No new books found on page {page_num}; stopping iterative pagination"
                        )
                        break

                    books.extend(new_books)

                    page_num += 1

                if books:
                    logger.success(
                        f"Successfully extracted {len(books)} books via iterative pagination"
                    )
                    return books

                # Try to find any similar patterns to help debug if fallback didn't yield results
                if "search-results" in response:
                    logger.debug(
                        "Found 'search-results' in response (different class maybe?)"
                    )
                    # Extract a snippet around "search-results"
                    idx = response.find("search-results")
                    context_start = max(0, idx - 100)
                    context_end = min(len(response), idx + 300)
                    logger.debug(
                        f"Context around 'search-results': {response[context_start:context_end]}"
                    )
                else:
                    logger.debug("No 'search-results' found at all in response")
                    # Log some key indicators that might be present
                    if "to-read" in response:
                        logger.debug("Found 'to-read' in response")
                    if "books" in response.lower():
                        logger.debug("Found 'books' (case-insensitive) in response")
                    # Log a larger sample of the response
                    logger.debug(
                        f"Sample of response (chars 1000-2000): {response[1000:2000]}"
                    )
        else:
            logger.error(f"Request failed with status code {books_req.status_code}")
            logger.error(f"Response body: {books_req.text}")
            books_req.raise_for_status()

        # If we can't extract the count or there's an error
        logger.warning("Returning empty book list due to errors")
        return []

    def _extract_books_from_soup(self, soup, seen_books: set) -> list:
        """Extract (url, title, author) tuples from a BeautifulSoup page fragment.
        Ensures entries are deduplicated using the provided seen_books set (mutated)."""
        found = []

        book_blocks = soup.select(
            "div.book-pane, div.book-pane-content, div.book-title-author-and-series, article.book-tile"
        )

        if not book_blocks:
            for tag in soup.find_all(["div", "article", "section"]):
                h3 = tag.find("h3")
                if h3 and (
                    tag.find("p", {"class": "font-body"})
                    or tag.select_one("a[href^='/authors/']")
                ):
                    book_blocks.append(tag)

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
                "p.font-body a"
            )
            author = author_link.get_text(strip=True) if author_link else ""

            if not book_title:
                continue

            identifier = book_url or f"{book_title}|{author}"
            if identifier in seen_books:
                continue

            seen_books.add(identifier)
            found.append((book_url, book_title, author))

        return found
