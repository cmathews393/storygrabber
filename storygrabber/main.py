import argparse
import json
import os
import re

import dotenv
import httpx
from bs4 import BeautifulSoup
from loguru import logger

from storygrabber.lazylibrarian import LazyLibrarianClient
from storygrabber.readarr import ReadarrClient

dotenv.load_dotenv()

# Configure Loguru logger
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logger.remove()  # Remove default handler
logger.add(
    "./app/logs/storygrabber.log",
    rotation="10 MB",
    level=log_level,
    format="{time} | {level} | {message}",
)
logger.add(
    lambda msg: print(msg),
    level=log_level,
    format="{level} | {message}",
)


class StoryGrabber:
    def __init__(self: "StoryGrabber", sg_user: str, session_id: str = None) -> None:
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

            if "search-results-count my-4" in response:
                # Extract the number of books using regex
                book_count_match = re.search(
                    r'<p class="search-results-count my-4">(\d+) books</p>', response
                )
                if book_count_match:
                    book_count = int(book_count_match.group(1))
                    logger.info(f"Found {book_count} books to process")

                    iterations = book_count // 10
                    if book_count % 10 != 0:
                        iterations += 1
                    logger.debug(f"Will need to process {iterations} pages")

                    books = []
                    for i in range(iterations):
                        page_num = i + 1
                        logger.debug(f"Processing page {page_num} of {iterations}")

                        body = {
                            "cmd": "request.get",
                            "session": self.session_id,
                            "url": f"{self.sg_url}?page={page_num}",
                        }
                        books_req = self.client.post(self.base_url, json=body)
                        books_req.raise_for_status()

                        # Extract books from the current page using BeautifulSoup
                        soup = BeautifulSoup(
                            books_req.json().get("solution").get("response"),
                            "html.parser",
                        )
                        book_divs = soup.find_all(
                            "div", class_="book-title-author-and-series"
                        )

                        logger.debug(f"Found {len(book_divs)} books on page {page_num}")

                        # Use a set to track unique book identifiers (title + author)
                        seen_books = set()

                        for book_div in book_divs:
                            # Extract book URL and title
                            title_link = book_div.find("h3").find("a")
                            book_url = title_link["href"] if title_link else ""
                            book_title = title_link.text.strip() if title_link else ""

                            # Extract author
                            author_link = book_div.find("p", class_="font-body").find(
                                "a"
                            )
                            author = author_link.text.strip() if author_link else ""

                            # Create a unique identifier for this book
                            book_identifier = f"{book_title}|{author}"

                            # Skip if we've already seen this book
                            if book_identifier in seen_books:
                                logger.debug(
                                    f"Skipping duplicate book: '{book_title}' by {author}"
                                )
                                continue

                            seen_books.add(book_identifier)
                            logger.debug(f"Extracted book: '{book_title}' by {author}")
                            books.append((book_url, book_title, author))

                    logger.success(f"Successfully extracted {len(books)} books")

                    # Don't destroy the session here anymore, we'll do it in main()
                    return books
                else:
                    logger.warning("Could not extract book count from page")
            else:
                logger.warning("No book count found on page")
        else:
            logger.error(f"Request failed with status code {books_req.status_code}")
            books_req.raise_for_status()

        # If we can't extract the count or there's an error
        logger.warning("Returning empty book list due to errors")
        return []


def dump_books_to_file(books: dict, filename: str) -> None:
    """
    Dump the books dictionary to a JSON file.
    Args:
        books: dict of user -> list of (url, title, author) tuples
        filename: path to output JSON file
    """
    # Convert tuples to dicts for JSON serialization
    serializable = {}
    for user, booklist in books.items():
        serializable[user] = [
            {"url": b[0], "title": b[1], "author": b[2]} for b in booklist
        ]
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2)
    logger.info(
        f"Dumped {sum(len(v) for v in serializable.values())} books to {filename}"
    )


def import_books_from_file(filename: str, manager: str = "Lazy") -> None:
    """
    Import books from a JSON file and add them to the selected manager.
    Args:
        filename: path to JSON file (as produced by dump_books_to_file)
        manager: "Lazy" or "Readarr"
    """
    with open(filename, "r", encoding="utf-8") as f:
        books_by_user = json.load(f)

    # Setup managers
    ll_host = os.getenv("LL_HOST", "localhost")
    ll_port = int(os.getenv("LL_PORT", "5299"))
    ll_api_key = os.getenv("LL_API_KEY", "")
    ll_use_https = os.getenv("LL_HTTPS", "False").lower() == "true"
    readarr_host = os.getenv("READARR_HOST", "localhost")
    readarr_port = int(os.getenv("READARR_PORT", "8787"))
    readarr_api_key = os.getenv("READARR_API_KEY", "")
    readarr_use_https = os.getenv("READARR_HTTPS", "False").lower() == "true"
    readarr_base_path = os.getenv("READARR_BASE_PATH", "")
    readarr_quality_profile_id = int(os.getenv("READARR_QUALITY_PROFILE_ID", "1"))
    readarr_metadata_profile_id = int(os.getenv("READARR_METADATA_PROFILE_ID", "1"))
    readarr_root_folder = os.getenv("READARR_ROOT_FOLDER", "/books")

    for user, books in books_by_user.items():
        logger.info(f"Importing {len(books)} books for user {user}")
        for book in books:
            book_title = book["title"]
            book_author = book["author"]
            book_url = book["url"]
            logger.info(f"Importing '{book_title}' by {book_author}")

            if manager == "Lazy":
                try:
                    ll_client = LazyLibrarianClient(
                        host=ll_host,
                        port=ll_port,
                        api_key=ll_api_key,
                        use_https=ll_use_https,
                    )
                    # Don't auto-queue all books - we only want the specific book
                    ll_client.add_author(book_author, auto_queue_books=False)
                    book_search = ll_client.find_book(book_title)
                    logger.debug(
                        f"Book search result for '{book_title}': {book_search}"
                    )

                    # find_book returns a list of book results, not a dict with success/id
                    if isinstance(book_search, list) and len(book_search) > 0:
                        # Use the first (best) match
                        best_match = book_search[0]
                        book_id = best_match.get("bookid") or best_match.get("id")

                        if book_id:
                            logger.debug(f"Using book ID {book_id} for '{book_title}'")
                            ll_client.add_book(book_id)
                            ll_client.queue_book(book_id)
                            ll_client.queue_book(book_id, book_type="AudioBook")
                            ll_client.search_book(book_id)
                            ll_client.search_book(book_id, book_type="AudioBook")
                        else:
                            logger.warning(
                                f"No book ID found in search result for '{book_title}'"
                            )
                    else:
                        logger.warning(
                            f"No search results found for book '{book_title}'"
                        )

                    logger.success(f"Imported '{book_title}' to LazyLibrarian")
                except Exception as e:
                    logger.error(f"Error importing book to LazyLibrarian: {e}")

            elif manager == "Readarr":
                try:
                    readarr_client = ReadarrClient(
                        host=readarr_host,
                        port=readarr_port,
                        api_key=readarr_api_key,
                        use_https=readarr_use_https,
                        base_path=readarr_base_path,
                    )
                    best_author_match, _ = readarr_client.lookup_author_by_name(
                        book_author
                    )
                    author_in_readarr = False
                    author_id = None
                    existing_authors = readarr_client.get_authors()
                    if isinstance(existing_authors, list):
                        for author in existing_authors:
                            if (
                                author.get("authorName", "").lower()
                                == book_author.lower()
                            ):
                                author_in_readarr = True
                                author_id = author.get("id")
                                break
                    if not author_in_readarr and best_author_match:
                        author_result = readarr_client.add_author_by_name(
                            name=book_author,
                            quality_profile_id=readarr_quality_profile_id,
                            metadata_profile_id=readarr_metadata_profile_id,
                            root_folder_path=readarr_root_folder,
                            monitored=True,
                        )
                        if author_result.get("id"):
                            author_id = author_result.get("id")
                    if author_id:
                        book_result = readarr_client.add_book_by_name(
                            title=book_title,
                            author_id=author_id,
                            monitored=True,
                            search_on_add=True,
                        )
                        if book_result.get("id"):
                            logger.success(f"Imported '{book_title}' to Readarr")
                        else:
                            logger.error(
                                f"Failed to import '{book_title}' to Readarr: {book_result.get('error', 'Unknown error')}"
                            )
                    else:
                        logger.error(f"Failed to get or add author '{book_author}'")
                except Exception as e:
                    logger.error(f"Error importing book to Readarr: {e}")

            else:
                logger.warning(f"Unknown manager: {manager}")


def unqueue_all_wanted_books(manager: str = "Lazy") -> dict:
    """
    Unqueue all wanted books from the selected manager.

    Args:
        manager: "Lazy" or "Readarr" (currently only Lazy is supported)

    Returns:
        Dictionary with results of the unqueue operation
    """
    if manager != "Lazy":
        logger.error(
            f"Manager '{manager}' not supported for unqueuing. Only 'Lazy' is supported."
        )
        return {"success": False, "error": "Unsupported manager"}

    # LazyLibrarian setup
    ll_host = os.getenv("LL_HOST", "localhost")
    ll_port = int(os.getenv("LL_PORT", "5299"))
    ll_api_key = os.getenv("LL_API_KEY", "")
    ll_use_https = os.getenv("LL_HTTPS", "False").lower() == "true"

    try:
        ll_client = LazyLibrarianClient(
            host=ll_host,
            port=ll_port,
            api_key=ll_api_key,
            use_https=ll_use_https,
        )

        logger.info("Fetching all wanted books from LazyLibrarian...")

        # Get all wanted books
        wanted_result = ll_client._make_request("getWanted")
        logger.debug(f"getWanted response type: {type(wanted_result)}")
        logger.debug(
            f"getWanted response (first 200 chars): {str(wanted_result)[:200]}"
        )

        wanted_books = []
        total_unqueued = 0
        failed_unqueues = 0

        # Parse the wanted books response - LazyLibrarian returns the array directly
        if isinstance(wanted_result, list):
            wanted_books = wanted_result
            logger.info(f"Found {len(wanted_books)} wanted books")
        elif isinstance(wanted_result, dict):
            # Fallback for other response formats
            if "message" in wanted_result:
                try:
                    import json

                    if isinstance(wanted_result["message"], str):
                        wanted_data = json.loads(wanted_result["message"])
                    else:
                        wanted_data = wanted_result["message"]

                    if isinstance(wanted_data, list):
                        wanted_books = wanted_data
                        logger.info(f"Found {len(wanted_books)} wanted books")
                    else:
                        logger.warning(
                            f"Unexpected wanted books data format: {type(wanted_data)}"
                        )

                except (json.JSONDecodeError, KeyError) as e:
                    logger.error(f"Failed to parse wanted books response: {e}")
                    return {"success": False, "error": f"Failed to parse response: {e}"}
            else:
                logger.warning(f"Unexpected dict response format: {wanted_result}")
                return {"success": False, "error": "Unexpected response format"}
        else:
            logger.warning(f"Unexpected wanted response format: {type(wanted_result)}")
            return {"success": False, "error": "Unexpected response format"}

        if not wanted_books:
            logger.info("No wanted books found to unqueue")
            return {
                "success": True,
                "total_unqueued": 0,
                "failed_unqueues": 0,
                "books": [],
            }

        results = []

        # Unqueue each wanted book
        for book in wanted_books:
            if not isinstance(book, dict):
                logger.warning(f"Skipping invalid book entry: {book}")
                continue

            # Use the correct field name from the response
            book_id = book.get("BookID")  # LazyLibrarian uses "BookID" (capital)
            book_title = book.get(
                "BookName", "Unknown Title"
            )  # LazyLibrarian uses "BookName"
            author_id = book.get("AuthorID", "")

            if not book_id:
                logger.warning(
                    f"No book ID found for '{book_title}' (AuthorID: {author_id})"
                )
                failed_unqueues += 1
                results.append(
                    {
                        "title": book_title,
                        "author_id": author_id,
                        "success": False,
                        "error": "No book ID found",
                    }
                )
                continue

            logger.debug(f"Unqueuing book '{book_title}' (ID: {book_id})")

            try:
                # Unqueue the book (remove from wanted)
                unqueue_result = ll_client._make_request("unqueueBook", {"id": book_id})
                logger.debug(f"Unqueue result for {book_id}: {unqueue_result}")

                # Check if unqueue was successful
                success = True
                if isinstance(unqueue_result, dict):
                    success = unqueue_result.get("success", True)
                elif isinstance(unqueue_result, list):
                    # Some APIs return [result, message, success]
                    if len(unqueue_result) >= 3:
                        success = bool(unqueue_result[2])

                if success:
                    logger.info(f"Successfully unqueued '{book_title}'")
                    total_unqueued += 1
                    results.append(
                        {
                            "title": book_title,
                            "author_id": author_id,
                            "book_id": book_id,
                            "success": True,
                        }
                    )
                else:
                    logger.warning(f"Failed to unqueue '{book_title}'")
                    failed_unqueues += 1
                    results.append(
                        {
                            "title": book_title,
                            "author_id": author_id,
                            "book_id": book_id,
                            "success": False,
                            "error": "Unqueue operation failed",
                        }
                    )

            except Exception as e:
                logger.error(f"Error unqueuing book '{book_title}': {e}")
                failed_unqueues += 1
                results.append(
                    {
                        "title": book_title,
                        "author_id": author_id,
                        "book_id": book_id,
                        "success": False,
                        "error": str(e),
                    }
                )

        logger.info(
            f"Unqueue operation completed: {total_unqueued} successful, {failed_unqueues} failed"
        )

        return {
            "success": True,
            "total_unqueued": total_unqueued,
            "failed_unqueues": failed_unqueues,
            "total_processed": len(wanted_books),
            "books": results,
        }

    except Exception as e:
        logger.error(f"Error during unqueue operation: {e}")
        return {"success": False, "error": str(e)}


def main():
    logger.info("StoryGrabber starting up")
    results = {}
    manager = os.getenv("SG_MANAGER", "Lazy")
    logger.info(f"Using book manager: {manager}")

    users = os.getenv("SG_USERS", "").strip().replace(" ", "").split(",")
    logger.info(f"Processing users: {', '.join(users)}")

    # LazyLibrarian setup
    ll_host = os.getenv("LL_HOST", "localhost")
    ll_port = int(os.getenv("LL_PORT", "5299"))
    ll_api_key = os.getenv("LL_API_KEY", "")
    ll_use_https = os.getenv("LL_HTTPS", "False").lower() == "true"
    logger.debug(
        f"LazyLibrarian config: host={ll_host}, port={ll_port}, https={ll_use_https}"
    )

    # Readarr setup
    readarr_host = os.getenv("READARR_HOST", "localhost")
    readarr_port = int(os.getenv("READARR_PORT", "8787"))
    readarr_api_key = os.getenv("READARR_API_KEY", "")
    readarr_use_https = os.getenv("READARR_HTTPS", "False").lower() == "true"
    readarr_base_path = os.getenv("READARR_BASE_PATH", "")
    logger.debug(
        f"Readarr config: host={readarr_host}, port={readarr_port}, https={readarr_use_https}"
    )

    # Quality and metadata profile IDs for Readarr
    readarr_quality_profile_id = int(os.getenv("READARR_QUALITY_PROFILE_ID", "1"))
    readarr_metadata_profile_id = int(os.getenv("READARR_METADATA_PROFILE_ID", "1"))
    readarr_root_folder = os.getenv("READARR_ROOT_FOLDER", "/books")
    logger.debug(
        f"Readarr profiles: quality={readarr_quality_profile_id}, metadata={readarr_metadata_profile_id}"
    )

    # Create a single FlaresolverR session to be used by all users
    client = httpx.Client(timeout=60)
    base_url = os.getenv("FS_URL", "localhost:8191/v1")

    body = {
        "cmd": "sessions.create",
        "maxTimeout": 120000,
    }

    logger.debug("Creating shared FlaresolverR session...")
    session_req = client.post(base_url, json=body)

    if session_req.status_code != 200:
        logger.error(f"Failed to create session: {session_req.text}")
        return results

    session_id = session_req.json().get("session")
    logger.info(f"Shared session created successfully with ID: {session_id}")

    try:
        for user in users:
            if user:
                logger.info(f"Processing user: {user}")
                sg = StoryGrabber(user, session_id=session_id)
                books = sg.get_books()

                if books:
                    logger.info(f"Found {len(books)} books for user {user}")
                    results[user] = []

                    for book in books:
                        book_title = book[1]
                        book_author = book[2]
                        book_url = book[0]

                        logger.info(f"Processing book: '{book_title}' by {book_author}")

                        # Add to appropriate book manager
                        if manager == "Lazy":
                            try:
                                logger.debug(f"Adding '{book_title}' to LazyLibrarian")
                                ll_client = LazyLibrarianClient(
                                    host=ll_host,
                                    port=ll_port,
                                    api_key=ll_api_key,
                                    use_https=ll_use_https,
                                )

                                # First check if author exists, if not add them
                                logger.debug(
                                    f"Checking if author '{book_author}' exists in LazyLibrarian"
                                )
                                author_search = ll_client.find_author(book_author)
                                logger.debug(author_search)

                                logger.debug(
                                    f"Adding author '{book_author}' to LazyLibrarian"
                                )
                                # Don't auto-queue all books - we only want the specific book
                                ll_client.add_author(
                                    book_author, auto_queue_books=False
                                )

                                # Now search for the book
                                logger.debug(
                                    f"Searching for book '{book_title}' in LazyLibrarian"
                                )
                                book_search = ll_client.find_book(book_title)
                                logger.debug(f"Book search result: {book_search}")

                                # find_book returns a list, not a dict with success/id
                                if (
                                    isinstance(book_search, list)
                                    and len(book_search) > 0
                                ):
                                    # Use the first (best) match
                                    best_match = book_search[0]
                                    book_id = best_match.get(
                                        "bookid"
                                    ) or best_match.get("id")

                                    if book_id:
                                        logger.debug(
                                            f"Using book ID {book_id} for '{book_title}'"
                                        )
                                        # If found, queue the book
                                        logger.debug(
                                            f"Queuing book '{book_title}' in LazyLibrarian"
                                        )
                                        add_result = ll_client.add_book(book_id)
                                        logger.debug(add_result)
                                        ll_client.queue_book(book_id)
                                        ll_client.queue_book(
                                            book_id, book_type="AudioBook"
                                        )
                                        ll_client.search_book(book_id)
                                        ll_client.search_book(
                                            book_id, book_type="AudioBook"
                                        )
                                    else:
                                        logger.warning(
                                            f"No book ID found in search result for '{book_title}'"
                                        )
                                else:
                                    logger.warning(
                                        f"No search results found for book '{book_title}'"
                                    )

                                logger.success(
                                    f"Successfully added '{book_title}' to LazyLibrarian"
                                )
                                results[user].append(
                                    {
                                        "title": book_title,
                                        "author": book_author,
                                        "url": book_url,
                                        "added_to_manager": True,
                                    }
                                )
                            except Exception as e:
                                logger.error(f"Error adding book to LazyLibrarian: {e}")
                                results[user].append(
                                    {
                                        "title": book_title,
                                        "author": book_author,
                                        "url": book_url,
                                        "added_to_manager": False,
                                        "error": str(e),
                                    }
                                )

                        elif manager == "Readarr":
                            try:
                                logger.debug(f"Adding '{book_title}' to Readarr")
                                readarr_client = ReadarrClient(
                                    host=readarr_host,
                                    port=readarr_port,
                                    api_key=readarr_api_key,
                                    use_https=readarr_use_https,
                                    base_path=readarr_base_path,
                                )

                                # First, try to add the author if they don't exist
                                logger.debug(
                                    f"Looking up author '{book_author}' in Readarr"
                                )
                                best_author_match, all_matches = (
                                    readarr_client.lookup_author_by_name(book_author)
                                )
                                author_in_readarr = False
                                author_id = None

                                # Check if author already exists
                                existing_authors = readarr_client.get_authors()
                                if isinstance(existing_authors, list):
                                    for author in existing_authors:
                                        if (
                                            author.get("authorName", "").lower()
                                            == book_author.lower()
                                        ):
                                            author_in_readarr = True
                                            author_id = author.get("id")
                                            logger.info(
                                                f"Author {book_author} already in Readarr (ID: {author_id})"
                                            )
                                            break

                                # Add the author if not found
                                if not author_in_readarr and best_author_match:
                                    logger.debug(
                                        f"Adding author '{book_author}' to Readarr"
                                    )
                                    author_result = readarr_client.add_author_by_name(
                                        name=book_author,
                                        quality_profile_id=readarr_quality_profile_id,
                                        metadata_profile_id=readarr_metadata_profile_id,
                                        root_folder_path=readarr_root_folder,
                                        monitored=True,
                                    )

                                    if author_result.get("id"):
                                        author_id = author_result.get("id")
                                        logger.success(
                                            f"Added author {book_author} to Readarr (ID: {author_id})"
                                        )
                                    else:
                                        logger.error(
                                            f"Failed to add author {book_author} to Readarr: {author_result.get('error', 'Unknown error')}"
                                        )

                                # Add the book if we have an author ID
                                if author_id:
                                    # Look up book
                                    logger.debug(
                                        f"Adding book '{book_title}' to Readarr"
                                    )
                                    book_result = readarr_client.add_book_by_name(
                                        title=book_title,
                                        author_id=author_id,
                                        monitored=True,
                                        search_on_add=True,
                                    )

                                    if book_result.get("id"):
                                        logger.success(
                                            f"Added book '{book_title}' to Readarr (ID: {book_result.get('id')})"
                                        )
                                        results[user].append(
                                            {
                                                "title": book_title,
                                                "author": book_author,
                                                "url": book_url,
                                                "added_to_manager": True,
                                                "readarr_book_id": book_result.get(
                                                    "id"
                                                ),
                                            }
                                        )
                                    else:
                                        error_msg = book_result.get(
                                            "error", "Unknown error"
                                        )
                                        logger.error(
                                            f"Failed to add book '{book_title}' to Readarr: {error_msg}"
                                        )
                                        results[user].append(
                                            {
                                                "title": book_title,
                                                "author": book_author,
                                                "url": book_url,
                                                "added_to_manager": False,
                                                "error": f"Failed to add book: {error_msg}",
                                            }
                                        )
                                else:
                                    logger.error(
                                        f"Failed to get or add author '{book_author}'"
                                    )
                                    results[user].append(
                                        {
                                            "title": book_title,
                                            "author": book_author,
                                            "url": book_url,
                                            "added_to_manager": False,
                                            "error": "Failed to get or add author",
                                        }
                                    )

                            except Exception as e:
                                logger.error(f"Error adding book to Readarr: {e}")
                                results[user].append(
                                    {
                                        "title": book_title,
                                        "author": book_author,
                                        "url": book_url,
                                        "added_to_manager": False,
                                        "error": str(e),
                                    }
                                )

                        else:
                            # Just collecting without adding to any manager
                            logger.info(
                                f"Collected book '{book_title}' without adding to manager"
                            )
                            results[user].append(
                                {
                                    "title": book_title,
                                    "author": book_author,
                                    "url": book_url,
                                }
                            )
                else:
                    logger.warning(
                        f"No books found for user {user} or an error occurred."
                    )
                    results[user] = []

    finally:
        # Destroy the shared session when finished with all users
        destroy_body = {
            "cmd": "sessions.destroy",
            "session": session_id,
        }
        destroy_req = client.post(base_url, json=destroy_body)
        if destroy_req.status_code == 200:
            logger.info("Shared session destroyed successfully")
        else:
            logger.error(f"Failed to destroy shared session: {destroy_req.text}")

    logger.info("StoryGrabber finished processing")
    return results


def main_cli():
    parser = argparse.ArgumentParser(description="StoryGrabber CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Dump books command
    dump_parser = subparsers.add_parser("dump-books", help="Dump books to a file")
    dump_parser.add_argument("--output", "-o", required=True, help="Output JSON file")

    # Import books command
    import_parser = subparsers.add_parser(
        "import-books", help="Import books from a file"
    )
    import_parser.add_argument("--input", "-i", required=True, help="Input JSON file")
    import_parser.add_argument(
        "--manager",
        "-m",
        choices=["Lazy", "Readarr"],
        default="Lazy",
        help="Book manager to import into",
    )

    # Unqueue all wanted books command
    unqueue_parser = subparsers.add_parser(
        "unqueue-wanted", help="Unqueue all wanted books"
    )
    unqueue_parser.add_argument(
        "--manager",
        "-m",
        choices=["Lazy", "Readarr"],
        default="Lazy",
        help="Book manager to unqueue from",
    )

    # Main scrape and add command (default)
    main_parser = subparsers.add_parser(
        "scrape-and-add", help="Scrape and add books (default main)"
    )

    args = parser.parse_args()

    if args.command == "dump-books":
        results = main()
        dump_books_to_file(
            {
                user: [(b["url"], b["title"], b["author"]) for b in books]
                if books and isinstance(books[0], dict)
                else books
                for user, books in results.items()
            },
            args.output,
        )
    elif args.command == "import-books":
        import_books_from_file(args.input, manager=args.manager)
    elif args.command == "unqueue-wanted":
        result = unqueue_all_wanted_books(manager=args.manager)
        if result["success"]:
            logger.success(f"Unqueued {result['total_unqueued']} books successfully")
            if result["failed_unqueues"] > 0:
                logger.warning(f"{result['failed_unqueues']} books failed to unqueue")
        else:
            logger.error(
                f"Unqueue operation failed: {result.get('error', 'Unknown error')}"
            )
    elif args.command == "scrape-and-add":
        main()
    else:
        parser.print_help()


if __name__ == "__main__":
    main_cli()
