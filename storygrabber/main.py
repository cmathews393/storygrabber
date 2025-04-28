import os
import re

import httpx
from bs4 import BeautifulSoup
from storygrabber.lazylibrarian import LazyLibrarianClient
from storygrabber.readarr import ReadarrClient


class StoryGrabber:
    def __init__(self: "StoryGrabber", sg_user: str) -> None:
        self.client = httpx.Client(timeout=60)
        self.base_url = os.getenv("FS_URL", "localhost:8191/v1")
        self.sg_username = sg_user
        self.sg_url = f"https://app.thestorygraph.com/to-read/{self.sg_username}"
        body = {
            "cmd": "sessions.create",
            "maxTimeout": 60000,
        }
        session_req = self.client.post(self.base_url, json=body)
        print(session_req.text)
        self.session_id = session_req.json().get("session")

    def get_books(self: "StoryGrabber") -> list[dict]:
        body = {
            "cmd": "request.get",
            "session": self.session_id,
            "url": self.sg_url,
        }
        books_req = self.client.post(self.base_url, json=body)
        if books_req.status_code == 200:
            response = books_req.json().get("solution").get("response")
            if "search-results-count my-4" in response:
                # Extract the number of books using regex
                book_count_match = re.search(
                    r'<p class="search-results-count my-4">(\d+) books</p>', response
                )
                if book_count_match:
                    book_count = int(book_count_match.group(1))

                    iterations = book_count // 10
                    if book_count % 10 != 0:
                        iterations += 1
                    books = []
                    for i in range(iterations):
                        body = {
                            "cmd": "request.get",
                            "session": self.session_id,
                            "url": f"{self.sg_url}?page={i + 1}",
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

                            books.append((book_url, book_title, author))

                    return books

            else:
                print("No book count")

        else:
            books_req.raise_for_status()

        # If we can't extract the count or there's an error
        return []


def main():
    results = {}
    manager = os.getenv("SG_MANAGER", "Lazy")
    users = os.getenv("SG_USERS", "").strip().replace(" ", "").split(",")

    # LazyLibrarian setup
    ll_host = os.getenv("LL_HOST", "localhost")
    ll_port = int(os.getenv("LL_PORT", "5299"))
    ll_api_key = os.getenv("LL_API_KEY", "")
    ll_use_https = os.getenv("LL_HTTPS", "False").lower() == "true"

    # Readarr setup
    readarr_host = os.getenv("READARR_HOST", "localhost")
    readarr_port = int(os.getenv("READARR_PORT", "8787"))
    readarr_api_key = os.getenv("READARR_API_KEY", "")
    readarr_use_https = os.getenv("READARR_HTTPS", "False").lower() == "true"
    readarr_base_path = os.getenv("READARR_BASE_PATH", "")

    # Quality and metadata profile IDs for Readarr
    readarr_quality_profile_id = int(os.getenv("READARR_QUALITY_PROFILE_ID", "1"))
    readarr_metadata_profile_id = int(os.getenv("READARR_METADATA_PROFILE_ID", "1"))
    readarr_root_folder = os.getenv("READARR_ROOT_FOLDER", "/books")

    for user in users:
        if user:
            sg = StoryGrabber(user)
            books = sg.get_books()

            if books:
                print(f"Found {len(books)} books for user {user}")
                results[user] = []

                for book in books:
                    book_title = book[1]
                    book_author = book[2]
                    book_url = book[0]
                    print(
                        f"Title: {book_title}, Author: {book_author}, URL: {book_url}"
                    )

                    # Add to appropriate book manager
                    if manager == "Lazy":
                        try:
                            ll_client = LazyLibrarianClient(
                                host=ll_host,
                                port=ll_port,
                                api_key=ll_api_key,
                                use_https=ll_use_https,
                            )

                            # First check if author exists, if not add them
                            author_search = ll_client.find_author(book_author)
                            if author_search.get("success", False):
                                ll_client.add_author(book_author)

                            # Now search for the book
                            book_search = ll_client.find_book(book_title)
                            if book_search.get("success", False):
                                # If found, queue the book
                                ll_client.queue_book(book_search.get("id"))

                            results[user].append(
                                {
                                    "title": book_title,
                                    "author": book_author,
                                    "url": book_url,
                                    "added_to_manager": True,
                                }
                            )
                        except Exception as e:
                            print(f"Error adding book to LazyLibrarian: {e}")
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
                            readarr_client = ReadarrClient(
                                host=readarr_host,
                                port=readarr_port,
                                api_key=readarr_api_key,
                                use_https=readarr_use_https,
                                base_path=readarr_base_path,
                            )

                            # First, try to add the author if they don't exist
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
                                        print(
                                            f"Author {book_author} already in Readarr (ID: {author_id})"
                                        )
                                        break

                            # Add the author if not found
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
                                    print(
                                        f"Added author {book_author} to Readarr (ID: {author_id})"
                                    )
                                else:
                                    print(
                                        f"Failed to add author {book_author} to Readarr: {author_result.get('error', 'Unknown error')}"
                                    )

                            # Add the book if we have an author ID
                            if author_id:
                                # Look up book
                                book_result = readarr_client.add_book_by_name(
                                    title=book_title,
                                    author_id=author_id,
                                    monitored=True,
                                    search_on_add=True,
                                )

                                if book_result.get("id"):
                                    print(
                                        f"Added book '{book_title}' to Readarr (ID: {book_result.get('id')})"
                                    )
                                    results[user].append(
                                        {
                                            "title": book_title,
                                            "author": book_author,
                                            "url": book_url,
                                            "added_to_manager": True,
                                            "readarr_book_id": book_result.get("id"),
                                        }
                                    )
                                else:
                                    error_msg = book_result.get(
                                        "error", "Unknown error"
                                    )
                                    print(
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
                            print(f"Error adding book to Readarr: {e}")
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
                        results[user].append(
                            {
                                "title": book_title,
                                "author": book_author,
                                "url": book_url,
                            }
                        )
            else:
                print(f"No books found for user {user} or an error occurred.")
                results[user] = []

    return results


if __name__ == "__main__":
    result = main()
    print(
        f"Processed {sum(len(books) for books in result.values())} books across {len(result)} users"
    )
