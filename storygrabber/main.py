import os
import re

import httpx
from bs4 import BeautifulSoup


class StoryGrabber:
    def __init__(self: "StoryGrabber") -> None:
        self.client = httpx.Client(timeout=60)
        self.base_url = os.getenv("FS_URL", "localhost:8191/v1")
        self.sg_username = os.getenv("SG_USERNAME")
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
    sg = StoryGrabber()

    books = sg.get_books()
    if books:
        for book in books:
            print(f"Title: {book[1]}, Author: {book[2]}, URL: {book[0]}")
    else:
        print("No books found or an error occurred.")
    return books


if __name__ == "__main__":
    books = main()
    print(books)
