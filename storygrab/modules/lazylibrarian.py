import json
import urllib.parse
from typing import Any, Dict, Optional

import httpx
from loguru import logger

logger.add(
    "lazylibrarian.log", level="DEBUG", rotation="10 MB", backtrace=True, diagnose=True
)


class LazyLibrarianClient:
    """
    Simple Python client for LazyLibrarian's API.
    """

    def __init__(
        self, host: str, port: int, api_key: str, use_https: bool = False
    ) -> None:
        protocol = "https" if use_https else "http"
        self.base_url = f"{protocol}://{host}:{port}/api"
        self.api_key = api_key
        self.session = httpx.Client()

    def _make_request(
        self, command: str, params: Optional[dict[str, str]] = None, wait: bool = False
    ) -> Any:
        if params is None:
            params = {}
        params["cmd"] = command
        params["apikey"] = self.api_key
        if wait:
            params["wait"] = "1"

        # Use urllib.parse.urlencode for proper encoding
        url = f"{self.base_url}?{urllib.parse.urlencode(params, quote_via=urllib.parse.quote)}"

        logger.debug(
            f"Making API request to LazyLibrarian - Command: {command}, Params: {params}"
        )
        logger.debug(
            f"Request URL (without API key): {url.replace(self.api_key, '[REDACTED]')}"
        )
        logger.debug(f"Request URL: {url}")

        try:
            response = self.session.get(url)
            logger.debug(f"HTTP response status: {response.status_code}")
            response.raise_for_status()

            # Handle response - either "OK" or JSON data
            response_text = response.text.strip()
            logger.debug(f"Raw response text (first 200 chars): {response_text[:200]}")

            if response_text == "OK":
                logger.debug("Response is 'OK' - returning success dictionary")
                return {"success": True, "message": "OK"}
            else:
                # Parse as JSON using json.loads()
                try:
                    parsed_response = json.loads(response_text)
                    logger.debug(
                        f"Successfully parsed JSON response, type: {type(parsed_response)}"
                    )
                    return parsed_response
                except json.JSONDecodeError as json_error:
                    # If it's not valid JSON, return as message
                    logger.warning(f"Failed to parse response as JSON: {json_error}")
                    logger.debug(f"Non-JSON response text: {response_text}")
                    return {"success": True, "message": response_text}
        except httpx.RequestError as e:
            logger.error(f"Request error for command '{command}': {e}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error for command '{command}': {e}")
            return {"success": False, "error": str(e)}

    def _normalize_response(self, response: Any) -> Dict[str, Any]:
        """
        Normalize API responses to ensure they're always dictionaries.

        Args:
            response: The raw API response

        Returns:
            A normalized dictionary response
        """
        logger.debug(f"Normalizing response of type: {type(response)}")

        if isinstance(response, dict):
            logger.debug("Response is already a dictionary")
            return response
        elif isinstance(response, list):
            logger.debug(
                f"Response is a list with {len(response)} items - normalizing to dict"
            )
            return {"success": True, "data": response}
        else:
            logger.warning(
                f"Unexpected response format: {type(response)}, value: {response}"
            )
            return {
                "success": False,
                "error": f"Unexpected response format: {type(response)}",
            }

    def list_no_books(self):
        logger.info("Getting authors with no books")
        return self._make_request("listNoBooks")

    # Author management
    def add_author(self, name: str, auto_queue_books: bool = True) -> Any:
        logger.info(f"Adding author: {name} (auto_queue_books: {auto_queue_books})")

        result = self._make_request("addAuthor", {"name": name})
        logger.debug(f"addAuthor response: {result}")

        author_id = None
        success = True

        # Handle response as list: [author_name, author_id, success]
        if isinstance(result, list):
            logger.debug(f"Response is list with {len(result)} items")
            if len(result) > 1:
                author_id = result[1]
                logger.debug(f"Extracted author_id from list: {author_id}")
            if len(result) > 2:
                success = bool(result[2])
                logger.debug(f"Extracted success from list: {success}")
        elif isinstance(result, dict):
            logger.debug("Response is dictionary")
            author_id = result.get("authorid") or result.get("id")
            success = result.get("success", True)
            logger.debug(
                f"Extracted from dict - author_id: {author_id}, success: {success}"
            )
        else:
            logger.warning(f"Unexpected result type: {type(result)}")

        if author_id and success:
            logger.info(f"Successfully added author {name} with ID {author_id}")
            logger.debug(f"Resuming author {author_id}")
            self.resume_author(author_id)
            if auto_queue_books:
                logger.debug(f"Auto-queuing books for author {author_id}")
                self.mark_author_books_wanted(author_id)
        elif author_id and not success:
            logger.info(
                f"Author {name} already exists with ID {author_id} - will still resume and queue books"
            )
            logger.debug(f"Resuming author {author_id}")
            self.resume_author(author_id)
            if auto_queue_books:
                logger.debug(f"Auto-queuing books for author {author_id}")
                self.mark_author_books_wanted(author_id)
        else:
            logger.warning(
                f"Failed to add author {name} - author_id: {author_id}, success: {success}"
            )

        return result

    def test_connection(self) -> None:
        """
        Test the connection to the LazyLibrarian API.
        Raises an exception if the connection fails.
        """
        logger.info("Testing connection to LazyLibrarian API")
        try:
            response = self._make_request("getVersion")
            logger.debug(f"getVersion response: {response}")
            response = self._normalize_response(response)

            if not response.get("success", False):
                logger.error(
                    f"Connection test failed: {response.get('error', 'Unknown error')}"
                )
                raise ConnectionError(
                    f"Failed to connect: {response.get('error', 'Unknown error')}"
                )
            logger.info("Successfully connected to LazyLibrarian API")
        except Exception as e:
            logger.error(f"Connection test failed with exception: {e}")
            raise

    def get_all_authors(self) -> Dict[str, Any]:
        """
        List all authors in the database.

        Returns:
            List of all authors
        """
        logger.debug("Getting all authors from database")
        result = self._make_request("getIndex")
        logger.debug(
            f"get_all_authors response count: {len(result) if isinstance(result, list) else 'N/A'}"
        )
        return self._normalize_response(result)

    def add_author_by_id(
        self, author_id: str, auto_queue_books: bool = True
    ) -> Dict[str, Any]:
        """
        Add an author to the LazyLibrarian database by AuthorID.
        Automatically resumes the author and marks their books as wanted.

        Args:
            author_id: The author's ID (from Goodreads or other sources)
            auto_queue_books: Whether to automatically queue the author's books as wanted

        Returns:
            API response with additional information about resumed author and queued books
        """
        logger.info(
            f"Adding author by ID: {author_id} (auto_queue_books: {auto_queue_books})"
        )

        # Add the author
        result = self._make_request("addAuthorID", {"id": author_id})
        logger.debug(f"addAuthorID raw response: {result}")
        result = self._normalize_response(result)
        logger.debug(f"addAuthorID normalized response: {result}")

        if not result.get("success", True):
            logger.error(f"Failed to add author {author_id}: {result}")
            return result

        logger.info(f"Successfully added author with ID {author_id}")

        # Resume the author
        logger.debug(f"Resuming author {author_id}")
        resume_result = self.resume_author(author_id)
        logger.debug(f"resume_author raw response: {resume_result}")
        resume_result = self._normalize_response(resume_result)
        logger.debug(f"resume_author normalized response: {resume_result}")

        if not resume_result.get("success", True):
            logger.warning(f"Failed to resume author {author_id}: {resume_result}")

        # Queue books if requested
        if auto_queue_books:
            logger.info(f"Marking books as wanted for author {author_id}")
            queue_result = self.mark_author_books_wanted(author_id)
            logger.debug(f"mark_author_books_wanted response: {queue_result}")

            # Combine results
            result["resumed"] = resume_result
            result["books_queued"] = queue_result
        else:
            logger.debug("Skipping auto-queue books as requested")
            result["resumed"] = resume_result

        logger.info(f"Completed adding author {author_id}")
        return result

    def find_author(self, name: str) -> Dict[str, Any]:
        """
        Search for an author on Goodreads/GoogleBooks.

        Args:
            name: The author's name to search for

        Returns:
            Search results
        """
        logger.info(f"Searching for author: {name}")
        result = self._make_request("findAuthor", {"name": name})
        logger.debug(f"find_author response: {result}")
        return result

    def get_author(self, author_id: str) -> Dict[str, Any]:
        """
        Get information about an author and their books.

        Args:
            author_id: The author's ID

        Returns:
            Author information and their books
        """
        logger.debug(f"Getting author information for ID: {author_id}")
        result = self._make_request("getAuthor", {"id": author_id})
        logger.debug(f"get_author response: {result}")
        return result

    def remove_author(self, author_id: str) -> Dict[str, Any]:
        """
        Remove an author from the database.

        Args:
            author_id: The author's ID to remove

        Returns:
            API response
        """
        logger.info(f"Removing author: {author_id}")
        result = self._make_request("removeAuthor", {"id": author_id})
        logger.debug(f"remove_author response: {result}")
        return result

    def refresh_author(self, name: str, refresh_cache: bool = False) -> Dict[str, Any]:
        """
        Reload an author and their books.

        Args:
            name: The author's name
            refresh_cache: Whether to refresh the cache

        Returns:
            API response
        """
        logger.info(f"Refreshing author: {name} (refresh_cache: {refresh_cache})")
        params = {"name": name}
        if refresh_cache:
            params["refresh"] = "1"
        result = self._make_request("refreshAuthor", params)
        logger.debug(f"refresh_author response: {result}")
        return result

    def resume_author(self, author_id: str) -> Dict[str, Any]:
        """
        Resume an author (mark as active).

        Args:
            author_id: The author's ID to resume

        Returns:
            API response
        """
        logger.debug(f"Resuming author: {author_id}")
        result = self._make_request("resumeAuthor", {"id": author_id})
        logger.debug(f"resume_author response: {result}")
        return result

    def mark_author_books_wanted(
        self, author_id: str, book_type: str = "eBook"
    ) -> Dict[str, Any]:
        """
        Mark all of an author's books as wanted.

        Args:
            author_id: The author's ID
            book_type: The type of book ('eBook' or 'AudioBook')

        Returns:
            Combined results from queuing all books
        """
        logger.info(
            f"Getting books for author {author_id} to mark as wanted (book_type: {book_type})"
        )

        # Get author information and their books
        author_info = self.get_author(author_id)
        logger.debug(f"Raw author_info response: {author_info}")
        author_info = self._normalize_response(author_info)
        logger.debug(f"Normalized author_info response: {author_info}")

        # Special handling for author info - if response was a list, it's likely the books
        if "data" in author_info and isinstance(author_info["data"], list):
            logger.debug("Found list data in normalized response - treating as books")
            books = author_info["data"]
            author_info["books"] = books

        if not author_info.get("success", True):
            logger.error(f"Failed to get author info: {author_info}")
            return author_info

        # Extract books from the response
        books = []
        if "books" in author_info:
            books = author_info["books"]
            logger.debug(f"Found {len(books)} books in 'books' key")
        elif isinstance(author_info, list):
            # Sometimes the response is directly a list of books
            books = author_info
            logger.debug(f"Author info is directly a list with {len(books)} items")

        if not books:
            logger.warning(f"No books found for author {author_id}")
            return {
                "success": True,
                "message": "No books found for author",
                "books_queued": 0,
            }

        logger.info(f"Found {len(books)} books for author {author_id}")

        # Queue each book
        results = []
        books_queued = 0
        for i, book in enumerate(books):
            logger.debug(f"Processing book {i+1}/{len(books)}: {book}")
            if isinstance(book, dict):
                book_id = book.get("bookid") or book.get("id")
                book_title = book.get("title", "Unknown Title")
                if book_id:
                    logger.debug(f"Queuing book {book_id} ({book_title})")
                    result = self.queue_book(book_id, book_type)
                    logger.debug(f"Queue book result: {result}")
                    results.append(result)
                    result = self._normalize_response(result)
                    if result.get("success", True):
                        books_queued += 1
                        logger.debug(f"Successfully queued book {book_id}")
                    else:
                        logger.warning(f"Failed to queue book {book_id}: {result}")
                else:
                    logger.warning(f"Book missing ID: {book}")
            else:
                logger.warning(f"Unexpected book format (type: {type(book)}): {book}")

        logger.info(f"Successfully queued {books_queued} books for author {author_id}")
        return {
            "success": True,
            "message": f"Queued {books_queued} books",
            "books_queued": books_queued,
            "total_books": len(books),
            "results": results,
        }

    # Book management methods
    def add_book(self, book_id: str) -> Dict[str, Any]:
        """
        Add a book to the LazyLibrarian database by ID.

        Args:
            book_id: The book's ID

        Returns:
            API response
        """
        logger.info(f"Adding book by ID: {book_id}")

        # Check if the book already exists in the library to avoid duplicate adds
        try:
            all_books = self.get_all_books()
            books_list = (
                all_books.get("data") if isinstance(all_books, dict) else all_books
            )
            if isinstance(books_list, list):
                for b in books_list:
                    # Try multiple possible id fields
                    for key in ("BookID", "bookid", "id"):
                        if b.get(key) and str(b.get(key)) == str(book_id):
                            logger.info(
                                f"Book {book_id} already exists in LazyLibrarian; skipping add"
                            )
                            return {
                                "success": True,
                                "message": "Book already exists",
                                "existing": b,
                            }
        except Exception as e:
            logger.debug(f"Failed to check existing books before add: {e}")

        result = self._make_request("addBook", {"id": book_id})
        logger.debug(f"add_book response: {result}")
        return result

    def find_book(self, name: str) -> Dict[str, Any]:
        """
        Search for a book on Goodreads/GoogleBooks.

        Args:
            name: The book's name to search for

        Returns:
            Search results
        """
        logger.info(f"Searching for book: {name}")
        result = self._make_request("findBook", {"name": name})
        logger.debug(f"find_book response: {result}")
        return result

    def search_book(
        self, book_id: str, book_type: str = "eBook", wait: bool = False
    ) -> Dict[str, str | int | dict | list]:
        """
        Search for a specific book.

        Args:
            book_id: The book's ID
            book_type: The type of book ('eBook' or 'AudioBook')
            wait: Whether to wait for search to complete

        Returns:
            Search results
        """
        logger.info(
            f"Searching for specific book: {book_id} (type: {book_type}, wait: {wait})"
        )
        result = self._make_request(
            "searchBook", {"id": book_id, "type": book_type}, wait=wait
        )
        logger.debug(f"search_book response: {result}")
        return result

    def queue_book(self, book_id: str, book_type: str = "eBook") -> Dict[str, Any]:
        """
        Mark a book as wanted.

        Args:
            book_id: The book's ID
            book_type: The type of book ('eBook' or 'AudioBook')

        Returns:
            API response
        """
        logger.debug(f"Queuing book: {book_id} (type: {book_type})")

        # Check wanted list: if the book is already wanted and status is 'Open', skip queue
        try:
            wanted = self.get_wanted()
            wanted_list = wanted.get("data") if isinstance(wanted, dict) else wanted
            if isinstance(wanted_list, list):
                for w in wanted_list:
                    for key in ("BookID", "bookid", "id"):
                        if w.get(key) and str(w.get(key)) == str(book_id):
                            status = w.get("Status") or w.get("status") or ""
                            if isinstance(status, str):
                                status_norm = status.strip().lower()
                                # treat 'open', 'want', 'wanted' as already wanted
                                if any(
                                    k in status_norm for k in ("open", "want", "wanted")
                                ):
                                    logger.info(
                                        f"Book {book_id} already in wanted with status '{status}' - skipping queue"
                                    )
                                    return {
                                        "success": True,
                                        "message": "Already wanted (Open)",
                                        "wanted": w,
                                    }
                            # If it's present but not Open, fall through and attempt to queue
                            logger.debug(
                                f"Book {book_id} present in wanted with status: {status}"
                            )
                            break
        except Exception as e:
            logger.debug(f"Failed to inspect wanted list before queue: {e}")

        result = self._make_request("queueBook", {"id": book_id, "type": book_type})
        logger.debug(f"queue_book response: {result}")
        return result

    def unqueue_book(self, book_id: str, book_type: str = "eBook") -> Dict[str, Any]:
        """
        Mark a book as skipped.

        Args:
            book_id: The book's ID
            book_type: The type of book ('eBook' or 'AudioBook')

        Returns:
            API response
        """
        logger.debug(f"Unqueuing book: {book_id} (type: {book_type})")
        result = self._make_request("unqueueBook", {"id": book_id, "type": book_type})
        logger.debug(f"unqueue_book response: {result}")
        return result

    # Library management methods
    def force_library_scan(
        self, directory: Optional[str] = None, wait: bool = False
    ) -> Dict[str, Any]:
        """
        Rescan the book library.

        Args:
            directory: Optional specific directory to scan
            wait: Whether to wait for scan to complete

        Returns:
            API response
        """
        logger.info(f"Forcing library scan (directory: {directory}, wait: {wait})")
        params = {}
        if directory:
            params["dir"] = directory
        result = self._make_request("forceLibraryScan", params, wait=wait)
        logger.debug(f"force_library_scan response: {result}")
        return result

    def force_book_search(
        self, book_type: str = "eBook", wait: bool = False
    ) -> Dict[str, Any]:
        """
        Search for all wanted books.

        Args:
            book_type: The type of book ('eBook' or 'AudioBook')
            wait: Whether to wait for search to complete

        Returns:
            API response
        """
        logger.info(f"Forcing book search (type: {book_type}, wait: {wait})")
        result = self._make_request("forceBookSearch", {"type": book_type}, wait=wait)
        logger.debug(f"force_book_search response: {result}")
        return result

    def get_all_books(self) -> Dict[str, Any]:
        """
        List all books in the database.

        Returns:
            List of all books
        """
        logger.debug("Getting all books from database")
        result = self._make_request("getAllBooks")
        logger.debug(
            f"get_all_books response count: {len(result) if isinstance(result, list) else 'N/A'}"
        )
        return self._normalize_response(result)

    def get_wanted(self) -> Dict[str, Any]:
        """
        List all wanted books.

        Returns:
            List of wanted books
        """
        logger.debug("Getting all wanted books")
        result = self._make_request("getWanted")
        logger.debug(
            f"get_wanted response count: {len(result) if isinstance(result, list) else 'N/A'}"
        )
        return self._normalize_response(result)

    # General API methods
    def help(self) -> Dict[str, Any]:
        """
        List all available API commands.

        Returns:
            List of commands and their descriptions
        """
        logger.debug("Getting API help")
        result = self._make_request("help")
        logger.debug("help response received")
        return result

    def get_version(self) -> Dict[str, Any]:
        """
        Get LazyLibrarian version information.

        Returns:
            Version information
        """
        logger.debug("Getting LazyLibrarian version")
        result = self._make_request("getVersion")
        logger.debug(f"get_version response: {result}")
        return result

    def search_item(self, item: str) -> Dict[str, Any]:
        """
        Search for an item (author, title, or ISBN).

        Args:
            item: The search query

        Returns:
            Search results
        """
        logger.info(f"Searching for item: {item}")
        result = self._make_request("searchItem", {"item": item})
        logger.debug(f"search_item response: {result}")
        return result

    def show_stats(self) -> Dict[str, Any]:
        """
        Show database statistics.

        Returns:
            Database statistics
        """
        logger.debug("Getting database statistics")
        result = self._make_request("showStats")
        logger.debug(f"show_stats response: {result}")
        return result

    # Execute any API command
    def execute_command(
        self, command: str, params: Optional[Dict[str, str]] = None, wait: bool = False
    ) -> Dict[str, Any]:
        """
        Execute any LazyLibrarian API command.

        Args:
            command: The API command to execute
            params: Additional parameters for the command
            wait: Whether to wait for long-running commands to complete

        Returns:
            API response
        """
        logger.info(f"Executing custom command: {command} with params: {params}")
        result = self._make_request(command, params, wait=wait)
        logger.debug(f"execute_command response: {result}")
        return result
