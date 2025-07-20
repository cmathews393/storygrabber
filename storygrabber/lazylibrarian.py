import urllib.parse
from typing import Any, Dict, Optional
from loguru import logger
import requests

logger.add(
    "lazylibrarian.log", level="DEBUG", rotation="10 MB", backtrace=True, diagnose=True
)


class LazyLibrarianClient:
    """
    A Python client for interacting with LazyLibrarian's API.
    Focuses primarily on book and author management but provides
    access to all API functionality.
    """

    def __init__(
        self, host: str, port: int, api_key: str, use_https: bool = False
    ) -> None:
        """
        Initialize the LazyLibrarian API client.

        Args:
            host: The hostname or IP address of the LazyLibrarian server
            port: The port number LazyLibrarian is running on
            api_key: Your LazyLibrarian API key
            use_https: Whether to use HTTPS instead of HTTP
        """
        protocol = "https" if use_https else "http"
        self.base_url = f"{protocol}://{host}:{port}/api"
        self.api_key = api_key
        self.session = requests.Session()

    def _make_request(
        self, command: str, params: dict[str, str] | None = None, wait: bool = False
    ) -> Dict[str, Any]:
        """
        Make a request to the LazyLibrarian API.

        Args:
            command: The API command to execute
            params: Additional parameters for the command
            wait: Whether to wait for long-running commands to complete

        Returns:
            The JSON response from the API or a dict with error information
        """
        if params is None:
            params = {}

        # Add common parameters
        params["cmd"] = command
        params["apikey"] = self.api_key

        if wait:
            params["wait"] = "1"

        # Build the URL with correctly encoded parameters
        # Use quote instead of quote_plus to avoid + signs, and handle special chars properly
        encoded_params = []
        for k, v in params.items():
            # Convert value to string and encode properly
            value_str = str(v)
            # Use quote with safe characters that LazyLibrarian expects
            encoded_value = urllib.parse.quote(value_str, safe="")
            encoded_params.append(f"{k}={encoded_value}")

        query_string = "&".join(encoded_params)
        url = f"{self.base_url}?{query_string}"

        try:
            response = self.session.get(url)
            response.raise_for_status()
            logger.debug(f"LazyLibrarian API request: {url}")
            logger.debug(f"LazyLibrarian API response status: {response.status_code}")
            logger.debug(f"LazyLibrarian API response: {response.text}")
            # Check if response is JSON
            content_type = response.headers.get("Content-Type", "")
            if "json" in content_type:
                return response.json()
            else:
                return {"success": True, "message": response.text}

        except requests.RequestException as e:
            return {"success": False, "error": str(e)}

    # Author management methods
    def add_author(self, name: str, auto_queue_books: bool = True) -> Dict[str, Any]:
        """
        Add an author to the LazyLibrarian database by name.
        Automatically resumes the author and marks their books as wanted.

        Args:
            name: The author's name
            auto_queue_books: Whether to automatically queue the author's books as wanted

        Returns:
            API response with additional information about resumed author and queued books
        """
        logger.info(f"Adding author: {name}")

        # Add the author
        result = self._make_request("addAuthor", {"name": name})

        if not result.get("success", True):
            logger.error(f"Failed to add author {name}: {result}")
            return result

        # Extract author ID from the response
        author_id = None
        if "authorid" in result:
            author_id = result["authorid"]
        elif "id" in result:
            author_id = result["id"]

        if not author_id:
            logger.warning(
                f"No author ID returned when adding {name}, cannot resume or queue books"
            )
            return result

        logger.info(f"Successfully added author {name} with ID {author_id}")

        # Resume the author
        logger.info(f"Resuming author {author_id}")
        resume_result = self.resume_author(author_id)
        if not resume_result.get("success", True):
            logger.warning(f"Failed to resume author {author_id}: {resume_result}")

        # Queue books if requested
        if auto_queue_books:
            logger.info(f"Marking books as wanted for author {author_id}")
            queue_result = self.mark_author_books_wanted(author_id)

            # Combine results
            result["resumed"] = resume_result
            result["books_queued"] = queue_result
        else:
            result["resumed"] = resume_result

        return result

    def test_connection(self) -> None:
        """
        Test the connection to the LazyLibrarian API.
        Raises an exception if the connection fails.
        """
        try:
            response = self._make_request("getVersion")
            if not response.get("success", False):
                raise ConnectionError(
                    f"Failed to connect: {response.get('error', 'Unknown error')}"
                )
            logger.info("Successfully connected to LazyLibrarian API")
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            raise

    def get_all_authors(self) -> Dict[str, Any]:
        """
        List all authors in the database.

        Returns:
            List of all authors
        """
        return self._make_request("getIndex")

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
        logger.info(f"Adding author by ID: {author_id}")

        # Add the author
        result = self._make_request("addAuthorID", {"id": author_id})

        if not result.get("success", True):
            logger.error(f"Failed to add author {author_id}: {result}")
            return result

        logger.info(f"Successfully added author with ID {author_id}")

        # Resume the author
        logger.info(f"Resuming author {author_id}")
        resume_result = self.resume_author(author_id)
        if not resume_result.get("success", True):
            logger.warning(f"Failed to resume author {author_id}: {resume_result}")

        # Queue books if requested
        if auto_queue_books:
            logger.info(f"Marking books as wanted for author {author_id}")
            queue_result = self.mark_author_books_wanted(author_id)

            # Combine results
            result["resumed"] = resume_result
            result["books_queued"] = queue_result
        else:
            result["resumed"] = resume_result

        return result

    def find_author(self, name: str) -> Dict[str, Any]:
        """
        Search for an author on Goodreads/GoogleBooks.

        Args:
            name: The author's name to search for

        Returns:
            Search results
        """
        return self._make_request("findAuthor", {"name": name})

    def get_author(self, author_id: str) -> Dict[str, Any]:
        """
        Get information about an author and their books.

        Args:
            author_id: The author's ID

        Returns:
            Author information and their books
        """
        return self._make_request("getAuthor", {"id": author_id})

    def remove_author(self, author_id: str) -> Dict[str, Any]:
        """
        Remove an author from the database.

        Args:
            author_id: The author's ID to remove

        Returns:
            API response
        """
        return self._make_request("removeAuthor", {"id": author_id})

    def refresh_author(self, name: str, refresh_cache: bool = False) -> Dict[str, Any]:
        """
        Reload an author and their books.

        Args:
            name: The author's name
            refresh_cache: Whether to refresh the cache

        Returns:
            API response
        """
        params = {"name": name}
        if refresh_cache:
            params["refresh"] = "1"
        return self._make_request("refreshAuthor", params)

    def resume_author(self, author_id: str) -> Dict[str, Any]:
        """
        Resume an author (mark as active).

        Args:
            author_id: The author's ID to resume

        Returns:
            API response
        """
        return self._make_request("resumeAuthor", {"id": author_id})

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
        logger.info(f"Getting books for author {author_id} to mark as wanted")

        # Get author information and their books
        author_info = self.get_author(author_id)
        if not author_info.get("success", True):
            logger.error(f"Failed to get author info: {author_info}")
            return author_info

        # Extract books from the response
        books = []
        if "books" in author_info:
            books = author_info["books"]
        elif isinstance(author_info, list):
            # Sometimes the response is directly a list of books
            books = author_info

        if not books:
            logger.warning(f"No books found for author {author_id}")
            return {
                "success": True,
                "message": "No books found for author",
                "books_queued": 0,
            }

        # Queue each book
        results = []
        books_queued = 0
        for book in books:
            if isinstance(book, dict):
                book_id = book.get("bookid") or book.get("id")
                book_title = book.get("title", "Unknown Title")
                if book_id:
                    logger.debug(f"Queuing book {book_id} ({book_title})")
                    result = self.queue_book(book_id, book_type)
                    results.append(result)
                    if result.get("success", True):
                        books_queued += 1
                else:
                    logger.warning(f"Book missing ID: {book}")
            else:
                logger.warning(f"Unexpected book format: {book}")

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
        return self._make_request("addBook", {"id": book_id})

    def find_book(self, name: str) -> Dict[str, Any]:
        """
        Search for a book on Goodreads/GoogleBooks.

        Args:
            name: The book's name to search for

        Returns:
            Search results
        """
        return self._make_request("findBook", {"name": name})

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
        return self._make_request(
            "searchBook", {"id": book_id, "type": book_type}, wait=wait
        )

    def queue_book(self, book_id: str, book_type: str = "eBook") -> Dict[str, Any]:
        """
        Mark a book as wanted.

        Args:
            book_id: The book's ID
            book_type: The type of book ('eBook' or 'AudioBook')

        Returns:
            API response
        """
        return self._make_request("queueBook", {"id": book_id, "type": book_type})

    def unqueue_book(self, book_id: str, book_type: str = "eBook") -> Dict[str, Any]:
        """
        Mark a book as skipped.

        Args:
            book_id: The book's ID
            book_type: The type of book ('eBook' or 'AudioBook')

        Returns:
            API response
        """
        return self._make_request("unqueueBook", {"id": book_id, "type": book_type})

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
        params = {}
        if directory:
            params["dir"] = directory
        return self._make_request("forceLibraryScan", params, wait=wait)

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
        return self._make_request("forceBookSearch", {"type": book_type}, wait=wait)

    def get_all_books(self) -> Dict[str, Any]:
        """
        List all books in the database.

        Returns:
            List of all books
        """
        return self._make_request("getAllBooks")

    def get_wanted(self) -> Dict[str, Any]:
        """
        List all wanted books.

        Returns:
            List of wanted books
        """
        return self._make_request("getWanted")

    # General API methods
    def help(self) -> Dict[str, Any]:
        """
        List all available API commands.

        Returns:
            List of commands and their descriptions
        """
        return self._make_request("help")

    def get_version(self) -> Dict[str, Any]:
        """
        Get LazyLibrarian version information.

        Returns:
            Version information
        """
        return self._make_request("getVersion")

    def search_item(self, item: str) -> Dict[str, Any]:
        """
        Search for an item (author, title, or ISBN).

        Args:
            item: The search query

        Returns:
            Search results
        """
        return self._make_request("searchItem", {"item": item})

    def show_stats(self) -> Dict[str, Any]:
        """
        Show database statistics.

        Returns:
            Database statistics
        """
        return self._make_request("showStats")

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
        return self._make_request(command, params, wait=wait)
