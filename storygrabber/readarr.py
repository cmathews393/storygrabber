from typing import Any, Dict, List, Optional, Tuple

import httpx


class ReadarrClient:
    """
    A Python client for interacting with Readarr's API.
    Allows for book and author management through Readarr.

    API documentation: https://readarr.com/docs/api/
    """

    def __init__(
        self,
        host: str,
        port: int,
        api_key: str,
        use_https: bool = False,
        base_path: str = "",
    ) -> None:
        """
        Initialize the Readarr API client.

        Args:
            host: The hostname or IP address of the Readarr server
            port: The port number Readarr is running on
            api_key: Your Readarr API key
            use_https: Whether to use HTTPS instead of HTTP
            base_path: Base URL path if Readarr is not at root (e.g., "/readarr")
        """
        protocol = "https" if use_https else "http"
        self.base_url = f"{protocol}://{host}:{port}{base_path}/api/v1"
        self.api_key = api_key
        self.session = httpx.Client()
        self.session.headers.update(
            {"X-Api-Key": api_key, "Content-Type": "application/json"}
        )

    def _make_request(
        self, method: str, endpoint: str, params: Dict = None, data: Dict = None
    ) -> Dict[str, Any]:
        """
        Make a request to the Readarr API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (without leading slash)
            params: URL parameters
            data: Request body for POST/PUT requests

        Returns:
            The JSON response or error information
        """
        url = f"{self.base_url}/{endpoint}"

        try:
            if method.upper() == "GET":
                response = self.session.get(url, params=params)
            elif method.upper() == "POST":
                response = self.session.post(url, params=params, json=data)
            elif method.upper() == "PUT":
                response = self.session.put(url, params=params, json=data)
            elif method.upper() == "DELETE":
                response = self.session.delete(url, params=params)
            else:
                return {"success": False, "error": "Invalid HTTP method"}

            response.raise_for_status()

            if response.content:
                return response.json()
            return {"success": True}

        except httpx.RequestError as e:
            return {"success": False, "error": str(e)}

    # System Information
    def get_system_status(self) -> Dict[str, Any]:
        """Get system status information."""
        return self._make_request("GET", "system/status")

    def get_health(self) -> List[Dict[str, Any]]:
        """Get health check information."""
        return self._make_request("GET", "health")

    # Author Management
    def get_authors(self, include_books: bool = True) -> List[Dict[str, Any]]:
        """
        Get all authors in Readarr.

        Args:
            include_books: Whether to include the author's books in the response

        Returns:
            List of authors
        """
        params = {}
        if include_books:
            params["includeBooks"] = "true"
        return self._make_request("GET", "author", params=params)

    def get_author(self, author_id: int, include_books: bool = True) -> Dict[str, Any]:
        """
        Get details for a specific author.

        Args:
            author_id: The author's ID in Readarr
            include_books: Whether to include the author's books in the response

        Returns:
            Author details
        """
        params = {}
        if include_books:
            params["includeBooks"] = "true"
        return self._make_request("GET", f"author/{author_id}", params=params)

    def search_author(self, term: str) -> List[Dict[str, Any]]:
        """
        Search for authors.

        Args:
            term: Search term

        Returns:
            List of matching authors
        """
        return self._make_request("GET", "search", params={"term": term})

    def add_author(self, author_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add an author to Readarr.

        Args:
            author_data: Author data object

        Returns:
            The added author details
        """
        return self._make_request("POST", "author", data=author_data)

    def update_author(self, author_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an author's details.

        Args:
            author_data: Author data object with ID

        Returns:
            The updated author details
        """
        return self._make_request("PUT", "author", data=author_data)

    def delete_author(
        self, author_id: int, delete_files: bool = False
    ) -> Dict[str, Any]:
        """
        Delete an author from Readarr.

        Args:
            author_id: The author's ID in Readarr
            delete_files: Whether to delete author files from disk

        Returns:
            Response status
        """
        return self._make_request(
            "DELETE",
            f"author/{author_id}",
            params={"deleteFiles": "true" if delete_files else "false"},
        )

    # Book Management
    def get_books(self) -> List[Dict[str, Any]]:
        """
        Get all books in Readarr.

        Returns:
            List of books
        """
        return self._make_request("GET", "book")

    def get_book(self, book_id: int) -> Dict[str, Any]:
        """
        Get details for a specific book.

        Args:
            book_id: The book's ID in Readarr

        Returns:
            Book details
        """
        return self._make_request("GET", f"book/{book_id}")

    def search_book(self, term: str) -> List[Dict[str, Any]]:
        """
        Search for books.

        Args:
            term: Search term (title, author name, ISBN, etc.)

        Returns:
            List of matching books
        """
        return self._make_request("GET", "search/book", params={"term": term})

    def add_book(self, book_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add a book to Readarr.

        Args:
            book_data: Book data object

        Returns:
            The added book details
        """
        return self._make_request("POST", "book", data=book_data)

    def update_book(self, book_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a book's details.

        Args:
            book_data: Book data object with ID

        Returns:
            The updated book details
        """
        return self._make_request("PUT", "book", data=book_data)

    def delete_book(self, book_id: int, delete_files: bool = False) -> Dict[str, Any]:
        """
        Delete a book from Readarr.

        Args:
            book_id: The book's ID in Readarr
            delete_files: Whether to delete book files from disk

        Returns:
            Response status
        """
        return self._make_request(
            "DELETE",
            f"book/{book_id}",
            params={"deleteFiles": "true" if delete_files else "false"},
        )

    # Search and Download
    def search_book_releases(self, book_id: int) -> Dict[str, Any]:
        """
        Search for releases of a book.

        Args:
            book_id: The book's ID in Readarr

        Returns:
            Search results
        """
        return self._make_request(
            "POST", "command", data={"name": "BookSearch", "bookIds": [book_id]}
        )

    def search_author_releases(self, author_id: int) -> Dict[str, Any]:
        """
        Search for releases of all books by an author.

        Args:
            author_id: The author's ID in Readarr

        Returns:
            Search results
        """
        return self._make_request(
            "POST", "command", data={"name": "AuthorSearch", "authorId": author_id}
        )

    # Quality Profiles
    def get_quality_profiles(self) -> List[Dict[str, Any]]:
        """
        Get all quality profiles.

        Returns:
            List of quality profiles
        """
        return self._make_request("GET", "qualityprofile")

    # Metadata Profiles
    def get_metadata_profiles(self) -> List[Dict[str, Any]]:
        """
        Get all metadata profiles.

        Returns:
            List of metadata profiles
        """
        return self._make_request("GET", "metadataprofile")

    # Root Folders
    def get_root_folders(self) -> List[Dict[str, Any]]:
        """
        Get all root folders.

        Returns:
            List of root folders
        """
        return self._make_request("GET", "rootfolder")

    # Helper Methods
    def lookup_author_by_name(
        self, name: str
    ) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Helper method to look up an author by name.

        Args:
            name: Author's name

        Returns:
            Tuple of (best_match, all_matches)
        """
        results = self.search_author(name)
        if not results or not isinstance(results, list) or not results:
            return None, []
        return results[0], results

    def add_author_by_name(
        self,
        name: str,
        quality_profile_id: int,
        metadata_profile_id: int,
        root_folder_path: str,
        monitored: bool = True,
    ) -> Dict[str, Any]:
        """
        Helper method to add an author by name.

        Args:
            name: Author's name
            quality_profile_id: Quality profile ID
            metadata_profile_id: Metadata profile ID
            root_folder_path: Root folder path
            monitored: Whether to monitor the author

        Returns:
            The added author details or error information
        """
        best_match, _ = self.lookup_author_by_name(name)
        if not best_match:
            return {"success": False, "error": f"No author found with name: {name}"}

        # Prepare the author data for adding
        author_data = {
            "authorName": name,
            "foreignAuthorId": best_match.get("foreignAuthorId"),
            "qualityProfileId": quality_profile_id,
            "metadataProfileId": metadata_profile_id,
            "rootFolderPath": root_folder_path,
            "monitored": monitored,
            "addOptions": {"searchForMissingBooks": True},
        }

        return self.add_author(author_data)

    def add_book_by_name(
        self,
        title: str,
        author_id: int,
        monitored: bool = True,
        search_on_add: bool = True,
    ) -> Dict[str, Any]:
        """
        Helper method to add a book by name.

        Args:
            title: Book title
            author_id: Author ID in Readarr
            monitored: Whether to monitor the book
            search_on_add: Whether to search for the book after adding

        Returns:
            The added book details or error information
        """
        search_results = self.search_book(title)
        if (
            not search_results
            or not isinstance(search_results, list)
            or not search_results
        ):
            return {"success": False, "error": f"No book found with title: {title}"}

        # Find matches by author ID
        matches = [
            book
            for book in search_results
            if book.get("author", {}).get("id") == author_id
        ]

        if not matches:
            return {
                "success": False,
                "error": f"No book found with title '{title}' for the specified author",
            }

        # Use the best match
        book_data = matches[0]
        book_data["monitored"] = monitored
        book_data["addOptions"] = {"searchForNewBook": search_on_add}

        return self.add_book(book_data)
