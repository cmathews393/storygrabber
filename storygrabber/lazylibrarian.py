import urllib.parse
from typing import Any, Dict

import requests


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
        self, command: str, params: Dict[str, str] = None, wait: bool = False
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
        query_string = "&".join(
            f"{k}={urllib.parse.quote_plus(str(v))}" for k, v in params.items()
        )
        url = f"{self.base_url}?{query_string}"

        try:
            response = self.session.get(url)
            response.raise_for_status()

            # Check if response is JSON
            content_type = response.headers.get("Content-Type", "")
            if "json" in content_type:
                return response.json()
            else:
                return {"success": True, "message": response.text}

        except requests.RequestException as e:
            return {"success": False, "error": str(e)}

    # Author management methods
    def add_author(self, name: str) -> Dict[str, Any]:
        """
        Add an author to the LazyLibrarian database by name.

        Args:
            name: The author's name

        Returns:
            API response
        """
        return self._make_request("addAuthor", {"name": name})

    def add_author_by_id(self, author_id: str) -> Dict[str, Any]:
        """
        Add an author to the LazyLibrarian database by AuthorID.

        Args:
            author_id: The author's ID (from Goodreads or other sources)

        Returns:
            API response
        """
        return self._make_request("addAuthorID", {"id": author_id})

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
    ) -> Dict[str, Any]:
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
        self, directory: str = None, wait: bool = False
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
        self, command: str, params: Dict[str, str] = None, wait: bool = False
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
