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
                                if author_search.get("success", False):
                                    logger.debug(
                                        f"Adding author '{book_author}' to LazyLibrarian"
                                    )
                                    ll_client.add_author(book_author)

                                # Now search for the book
                                logger.debug(
                                    f"Searching for book '{book_title}' in LazyLibrarian"
                                )
                                book_search = ll_client.find_book(book_title)
                                logger.debug(book_search)
                                if book_search.get("success", False):
                                    # If found, queue the book
                                    logger.debug(
                                        f"Queuing book '{book_title}' in LazyLibrarian"
                                    )
                                    add_result = ll_client.add_book(
                                        book_search.get("id")
                                    )
                                    logger.debug(add_result)
                                    ll_client.queue_book(book_search.get("id"))
                                    ll_client.search_book(book_search.get("id"))

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


if __name__ == "__main__":
    result = main()
    logger.info(
        f"Processed {sum(len(books) for books in result.values())} books across {len(result)} users"
    )
