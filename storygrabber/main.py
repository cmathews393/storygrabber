import getpass
import json
import os
import re
import time
import urllib.parse
from datetime import datetime

import httpx
from bs4 import BeautifulSoup


class WebsiteScraper:
    def __init__(
        self, login_url, target_url, use_selenium=False, html_dump_dir="html_dumps"
    ):
        """
        Initialize the scraper with login and target URLs

        Args:
            login_url (str): URL of the login page
            target_url (str): URL of the page to scrape after login
            use_selenium (bool): Whether to use Selenium for browser automation
            html_dump_dir (str): Directory to save HTML dumps
        """
        self.login_url = login_url
        self.target_url = target_url

        self.html_dump_dir = html_dump_dir

        # Initialize httpx session with longer timeouts for Cloudflare challenges
        self.session = httpx.Client(timeout=60.0, follow_redirects=True)
        # Add common headers to mimic a browser
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-User": "?1",
            }
        )

    def _cloudflare_request(self, method, url, **kwargs):
        """
        Make a request that can handle Cloudflare challenges

        Args:
            method (str): HTTP method to use (get, post)
            url (str): URL to request
            **kwargs: Additional arguments to pass to the request

        Returns:
            httpx.Response: The response
        """
        max_retries = 5
        retry_delay = 5  # seconds

        for attempt in range(max_retries):
            try:
                if method.lower() == "get":
                    response = self.session.get(url, **kwargs)
                elif method.lower() == "post":
                    response = self.session.post(url, **kwargs)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                # Check for Cloudflare challenge page
                if (response.status_code == 503 or response.status_code == 403) and (
                    "cloudflare" in response.text.lower()
                    or "cf-browser-verification" in response.text.lower()
                    or "just a moment" in response.text.lower()
                ):
                    print(
                        f"Cloudflare challenge detected (attempt {attempt+1}/{max_retries})"
                    )

                    # Extract challenge tokens if present
                    soup = BeautifulSoup(response.text, "html.parser")

                    # Look for the refresh meta tag (indicates how long to wait)
                    refresh_tag = soup.find("meta", {"http-equiv": "refresh"})
                    wait_seconds = 10  # Default wait time
                    if refresh_tag and refresh_tag.get("content"):
                        try:
                            wait_seconds = int(refresh_tag.get("content"))
                            print(f"Found refresh directive: {wait_seconds} seconds")
                        except ValueError:
                            pass

                    # Check for any form submission that might be required
                    form = soup.find("form")
                    if form:
                        form_action = form.get("action")
                        form_method = form.get("method", "post").lower()
                        form_inputs = {}

                        for input_tag in form.find_all("input"):
                            input_name = input_tag.get("name")
                            input_value = input_tag.get("value", "")
                            if input_name:
                                form_inputs[input_name] = input_value

                        if form_action and form_inputs:
                            print(f"Found form submission. Action: {form_action}")

                            # Try to submit the form after waiting
                            wait_time = max(wait_seconds, retry_delay * (attempt + 1))
                            print(
                                f"Waiting {wait_time} seconds before submitting form..."
                            )
                            time.sleep(wait_time)

                            # Make form submission
                            if form_method == "post":
                                return self._cloudflare_request(
                                    "post", form_action, data=form_inputs
                                )
                            else:
                                return self._cloudflare_request(
                                    "get", form_action, params=form_inputs
                                )

                    # Extract JavaScript challenge parameters
                    scripts = soup.find_all("script")
                    cf_params = {}

                    for script in scripts:
                        script_text = script.string if script.string else ""

                        # Look for the _cf_chl_opt JavaScript object
                        if "_cf_chl_opt" in script_text:
                            # Extract key parameters if possible
                            for key in ["cvId", "cType", "cNounce", "cRay", "cHash"]:
                                match = re.search(
                                    f"{key}: ['\"]?([^'\",:]+)", script_text
                                )
                                if match:
                                    cf_params[key] = match.group(1)

                            # Extract challenge token
                            token_match = re.search(
                                r"__cf_chl_tk=([^'\"&]+)", script_text
                            )
                            if token_match:
                                cf_params["token"] = token_match.group(1)

                    if cf_params:
                        print(f"Extracted Cloudflare parameters: {cf_params}")

                    # Wait longer with each retry attempt
                    wait_time = max(wait_seconds, retry_delay * (attempt + 1))
                    print(f"Waiting {wait_time} seconds for Cloudflare challenge...")
                    time.sleep(wait_time)

                    # Check for clearance cookie
                    if "cf_clearance" in self.session.cookies:
                        print("Found Cloudflare clearance cookie!")
                        # Try again with the cookie
                        continue

                    # Try to get to the real page again after waiting
                    continue

                # Check for specific Cloudflare redirects
                if response.status_code in (301, 302, 307, 308):
                    redirect_url = response.headers.get("location")
                    if redirect_url:
                        # Check if it's a Cloudflare-related redirect
                        if (
                            "cloudflare" in response.headers.get("server", "").lower()
                            or "__cf_chl" in redirect_url
                            or "cf_chl_" in redirect_url
                        ):
                            print(f"Following Cloudflare redirect to: {redirect_url}")

                            # If URL is relative, make it absolute
                            if not redirect_url.startswith("http"):
                                from urllib.parse import urljoin

                                redirect_url = urljoin(url, redirect_url)

                            return self._cloudflare_request(
                                method, redirect_url, **kwargs
                            )

                # If the response has JavaScript challenges embedded, extract and process them
                if "window._cf_chl_opt" in response.text:
                    print("Found embedded Cloudflare challenge script")
                    # Save the challenge page for debugging
                    self._dump_html_to_file(response.text, "cloudflare_challenge")

                    # Wait and retry
                    wait_time = retry_delay * (attempt + 1)
                    print(f"Waiting {wait_time} seconds before retrying...")
                    time.sleep(wait_time)
                    continue

                # Check if we got a successful response without challenge
                return response

            except httpx.TimeoutException:
                print(f"Request timed out (attempt {attempt+1}/{max_retries})")
                time.sleep(retry_delay)
            except httpx.HTTPError as e:
                print(f"HTTP error occurred: {e} (attempt {attempt+1}/{max_retries})")
                time.sleep(retry_delay)

        # If we've exhausted our retries, raise an exception
        raise Exception(f"Failed to bypass Cloudflare after {max_retries} attempts")

    def _dump_html_to_file(self, html_content, prefix="dump"):
        """
        Save HTML content to a file for debugging

        Args:
            html_content (str): HTML content to save
            prefix (str): Prefix for the filename
        """
        if not os.path.exists(self.html_dump_dir):
            os.makedirs(self.html_dump_dir)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.html_dump_dir}/{prefix}_{timestamp}.html"

        with open(filename, "w", encoding="utf-8") as f:
            f.write(html_content)

        print(f"Saved HTML dump to {filename}")

    def get_login_form_details(self):
        """
        Get the login form details from the login page

        Returns:
            dict: Form details with action URL and input fields
        """
        try:
            # Use the Cloudflare-aware request method
            response = self._cloudflare_request("get", self.login_url)

            # Save the HTML for debugging
            self._dump_html_to_file(response.text, "login_form")

            soup = BeautifulSoup(response.text, "html.parser")

            # Find the login form - this is very website-specific and may need adjustment
            login_form = soup.find("form")
            if not login_form:
                print(
                    "Warning: Login form not found using basic selector. Trying alternative approaches."
                )
                # Try to find any form that might be a login form
                all_forms = soup.find_all("form")
                for form in all_forms:
                    # Look for common patterns in login forms
                    if form.find("input", {"type": "password"}):
                        login_form = form
                        print(
                            "Found a form with password field, using this as login form."
                        )
                        break

                if not login_form:
                    print(
                        "Error: No suitable login form found. Will try with Selenium instead."
                    )
                    return {"action": self.login_url, "inputs": {}, "method": "post"}

            # Get form action URL
            form_action = login_form.get("action")
            if form_action and not form_action.startswith("http"):
                # Handle relative URLs
                if form_action.startswith("/"):
                    from urllib.parse import urlparse

                    parsed_url = urlparse(self.login_url)
                    form_action = (
                        f"{parsed_url.scheme}://{parsed_url.netloc}{form_action}"
                    )
                else:
                    form_action = (
                        self.login_url.rstrip("/") + "/" + form_action.lstrip("/")
                    )

            # If no action is specified, use the login URL
            if not form_action:
                form_action = self.login_url

            # Get input fields
            form_inputs = {}
            for input_tag in login_form.find_all("input"):
                input_name = input_tag.get("name")
                input_value = input_tag.get("value", "")
                input_type = input_tag.get("type", "text").lower()

                if input_name:
                    # Skip hidden fields with preset values and submit buttons
                    if input_type == "hidden":
                        form_inputs[input_name] = input_value
                    # We'll handle password and text fields later
                    elif input_type in ["text", "email", "password"]:
                        form_inputs[input_name] = ""

            return {
                "action": form_action,
                "inputs": form_inputs,
                "method": login_form.get("method", "post").lower(),
            }
        except Exception as e:
            print(f"Error getting login form details: {e}")
            # Return a default structure that can be used by Selenium
            return {"action": self.login_url, "inputs": {}, "method": "post"}

    def _login_with_requests(self, username, password):
        """Login using httpx library"""
        try:
            # Get the login form details
            form_details = self.get_login_form_details()

            # Populate username and password fields
            # This is website-specific and may need adjustment
            username_field = None
            password_field = None

            # Try to identify username and password fields
            for field_name in form_details["inputs"].keys():
                lower_field = field_name.lower()
                if (
                    "user" in lower_field
                    or "email" in lower_field
                    or "login" in lower_field
                ):
                    username_field = field_name
                elif "pass" in lower_field:
                    password_field = field_name

            if not username_field or not password_field:
                print("Error: Could not identify username or password fields.")
                print(f"Available fields: {list(form_details['inputs'].keys())}")
                username_field = input("Please enter the username field name: ")
                password_field = input("Please enter the password field name: ")

            # Set the username and password in the form data
            form_details["inputs"][username_field] = username
            form_details["inputs"][password_field] = password

            # Submit the login form using Cloudflare-aware request method
            if form_details["method"] == "post":
                response = self._cloudflare_request(
                    "post",
                    form_details["action"],
                    data=form_details["inputs"],
                    headers={
                        "Referer": self.login_url
                    },  # Add referer for better authenticity
                )
            else:
                response = self._cloudflare_request(
                    "get",
                    form_details["action"],
                    params=form_details["inputs"],
                    headers={"Referer": self.login_url},
                )

            # Dump HTML to file
            self._dump_html_to_file(response.text, "login_response")

            # Check if login was successful
            if response.status_code == 200 and len(self.session.cookies) > 0:
                # Additional check for login success - look for elements that indicate logged in state
                soup = BeautifulSoup(response.text, "html.parser")
                # This is site-specific and may need to be adjusted
                if soup.find("a", string=re.compile("sign out|logout", re.IGNORECASE)):
                    print("Login successful! Found logout link in response.")
                    return True
                elif not soup.find("form", {"id": "new_user"}):  # No login form visible
                    print("Login successful! Login form no longer present.")
                    return True
                else:
                    print("Login may have failed. Still seeing login form.")
                    return False
            else:
                print(f"Login failed with status code: {response.status_code}")
                return False

        except Exception as e:
            print(f"Error during login: {e}")
            return False

    def _scrape_with_requests(self, max_pages=25):
        """
        Scrape using httpx library with pagination support

        Args:
            max_pages (int): Maximum number of pages to scrape

        Returns:
            list: List of extracted alt texts from all pages combined
        """
        try:
            all_alt_texts = []

            for page_num in range(1, max_pages + 1):
                # Construct URL with page parameter
                if "?" in self.target_url:
                    # URL already has query parameters
                    page_url = f"{self.target_url}&page={page_num}"
                else:
                    # URL doesn't have query parameters yet
                    page_url = f"{self.target_url}?page={page_num}"

                print(f"Scraping page {page_num} of {max_pages}: {page_url}")

                # Request the target page using Cloudflare-aware request
                response = self._cloudflare_request("get", page_url)

                # Dump HTML for debugging
                self._dump_html_to_file(response.text, f"page_{page_num}")

                if response.status_code != 200:
                    print(
                        f"Error accessing page {page_num}: Status code {response.status_code}"
                    )
                    # Don't try any more pages if we hit an error
                    break

                # Extract alt tags from the response with deduplication
                page_alt_texts = self.extract_alt_tags_with_deduplication(response.text)

                # Log the results for this page
                print(
                    f"Found {len(page_alt_texts)} unique book entries on page {page_num}"
                )

                # Add to our combined list
                all_alt_texts.extend(page_alt_texts)

                # If we got fewer items than expected, we might be on the last page
                if len(page_alt_texts) == 0:
                    print(
                        f"No more items found on page {page_num}. Stopping pagination."
                    )
                    break

                # Optional: Add a small delay between requests to avoid overloading the server
                time.sleep(1)

            # Remove any duplicates that might have appeared across different pages
            unique_alt_texts = list(dict.fromkeys(all_alt_texts))
            print(f"Total unique books found across all pages: {len(unique_alt_texts)}")

            return unique_alt_texts

        except Exception as e:
            print(f"Error scraping target pages with httpx: {e}")
            return []

    def close(self):
        """Close the browser if using Selenium and the httpx client"""

        self.session.close()


class LazyLibrarianAPI:
    """Interface with LazyLibrarian API endpoints to add books and authors"""

    def __init__(
        self, base_url="http://localhost:5299", api_key=None, html_dump_dir="html_dumps"
    ):
        """
        Initialize the LazyLibrarian API client

        Args:
            base_url (str): Base URL for LazyLibrarian API
            api_key (str): API key for authentication
            html_dump_dir (str): Directory to save HTML dumps
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.html_dump_dir = html_dump_dir

        # Create HTML dump directory if it doesn't exist
        if not os.path.exists(self.html_dump_dir):
            os.makedirs(self.html_dump_dir)
            print(f"Created HTML dump directory: {self.html_dump_dir}")

        self.client = httpx.Client(
            timeout=30.0
        )  # Create a persistent client with longer timeout

    def _make_request(self, endpoint, params=None):
        """
        Make a request to the LazyLibrarian API

        Args:
            endpoint (str): API endpoint to call
            params (dict): Parameters to include in the request

        Returns:
            dict: Response from the API (parsed JSON)
        """
        if params is None:
            params = {}

        # Add API key if we have one
        if self.api_key:
            params["apikey"] = self.api_key

        url = f"{self.base_url}/api?cmd={endpoint}"

        # Add parameters to the URL
        for key, value in params.items():
            if value is not None:
                url += f"&{key}={urllib.parse.quote_plus(str(value))}"

        try:
            response = self.client.get(url)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error {response.status_code}: {response.text}")
                return {"error": f"HTTP Error {response.status_code}"}
        except Exception as e:
            print(f"API request failed: {str(e)}")
            return {"error": str(e)}

    def add_author_by_name(self, author_name):
        """
        Add an author to LazyLibrarian by name

        Args:
            author_name (str): Name of the author to add

        Returns:
            dict: Response from the API
        """
        return self._make_request("addAuthor", {"name": author_name})

    def add_author_by_id(self, author_id):
        """
        Add an author to LazyLibrarian by ID

        Args:
            author_id (str): ID of the author to add

        Returns:
            dict: Response from the API
        """
        return self._make_request("addAuthorID", {"id": author_id})

    def add_book(self, book_id):
        """
        Add a book to LazyLibrarian by ID

        Args:
            book_id (str): ID of the book to add

        Returns:
            dict: Response from the API
        """
        return self._make_request("addBook", {"id": book_id})

    def find_book(self, book_name):
        """
        Search for a book in LazyLibrarian

        Args:
            book_name (str): Name of the book to search for

        Returns:
            dict: Response from the API with search results
        """
        return self._make_request("findBook", {"name": book_name})

    def find_author(self, author_name):
        """
        Search for an author in LazyLibrarian

        Args:
            author_name (str): Name of the author to search for

        Returns:
            dict: Response from the API with search results
        """
        return self._make_request("findAuthor", {"name": author_name})

    def process_book_from_title_author(self, title, author):
        """
        Process a book by title and author - find and add both

        Args:
            title (str): Book title
            author (str): Book author

        Returns:
            dict: Status of the operations
        """
        print(f"Processing: {title} by {author}")

        # First try to find the author
        author_result = self.find_author(author)

        if "error" in author_result:
            print(f"Error finding author '{author}': {author_result['error']}")
            return {
                "status": "error",
                "message": f"Failed to find author: {author_result['error']}",
            }

        # Check if we got valid author results
        if (
            not author_result
            or not isinstance(author_result, dict)
            or "authorlist" not in author_result
        ):
            print(f"No valid results for author '{author}'")
            return {"status": "error", "message": "No author results found"}

        # If we have author results, add the first matching author
        author_list = author_result.get("authorlist", [])
        if not author_list:
            print(f"No authors found for '{author}'")
            return {"status": "error", "message": "No matching authors found"}

        # Find the best author match
        best_author = None
        for author_entry in author_list:
            if author_entry.get("authorname", "").lower() == author.lower():
                best_author = author_entry
                break

        if not best_author:
            # Just use the first one if no exact match
            best_author = author_list[0]

        print(
            f"Adding author: {best_author.get('authorname')} (ID: {best_author.get('authorid')})"
        )

        # Add the author
        add_author_result = self.add_author_by_id(best_author.get("authorid"))
        if "error" in add_author_result:
            print(f"Error adding author: {add_author_result['error']}")
            return {
                "status": "error",
                "message": f"Failed to add author: {add_author_result['error']}",
            }

        # Now search for the book
        book_result = self.find_book(title)

        if "error" in book_result:
            print(f"Error finding book '{title}': {book_result['error']}")
            return {
                "status": "error",
                "message": f"Failed to find book: {book_result['error']}",
            }

        # Check if we got valid book results
        if (
            not book_result
            or not isinstance(book_result, dict)
            or "books" not in book_result
        ):
            print(f"No valid results for book '{title}'")
            return {"status": "error", "message": "No book results found"}

        # If we have book results, find the one that matches our author
        book_list = book_result.get("books", [])
        if not book_list:
            print(f"No books found for '{title}'")
            return {"status": "error", "message": "No matching books found"}

        # Find the best book match by author
        best_book = None
        for book_entry in book_list:
            book_author = book_entry.get("authorname", "").lower()
            if author.lower() in book_author or book_author in author.lower():
                best_book = book_entry
                break

        if not best_book:
            # Just use the first one if no author match
            best_book = book_list[0]

        print(
            f"Adding book: {best_book.get('bookname')} by {best_book.get('authorname')} (ID: {best_book.get('bookid')})"
        )

        # Add the book
        add_book_result = self.add_book(best_book.get("bookid"))
        if "error" in add_book_result:
            print(f"Error adding book: {add_book_result['error']}")
            return {
                "status": "error",
                "message": f"Failed to add book: {add_book_result['error']}",
            }

        return {
            "status": "success",
            "message": f"Added '{best_book.get('bookname')}' by {best_author.get('authorname')}",
            "book": best_book,
            "author": best_author,
        }

    def process_books_from_alt_texts(self, alt_texts):
        """
        Process a list of book alt texts and add them to LazyLibrarian

        Args:
            alt_texts (list): List of book alt texts in format "Title by Author"

        Returns:
            dict: Summary of processing results
        """
        results = {"total": len(alt_texts), "successful": 0, "failed": 0, "details": []}

        for i, alt_text in enumerate(alt_texts, 1):
            print(f"Processing book {i}/{len(alt_texts)}: {alt_text}")

            # Parse title and author from alt text
            match = re.search(r"(.*)\s+by\s+(.*)", alt_text)
            if match:
                title, author = match.groups()
                title = title.strip()
                author = author.strip()

                # Process this book
                result = self.process_book_from_title_author(title, author)

                if result["status"] == "success":
                    results["successful"] += 1
                else:
                    results["failed"] += 1

                results["details"].append(
                    {
                        "alt_text": alt_text,
                        "title": title,
                        "author": author,
                        "result": result,
                    }
                )

                # Add a small delay to avoid overwhelming the API
                time.sleep(1)
            else:
                print(f"Could not parse title and author from: {alt_text}")
                results["failed"] += 1
                results["details"].append(
                    {"alt_text": alt_text, "error": "Could not parse title and author"}
                )

        return results

    def close(self):
        """Close the HTTP client"""
        self.client.close()


def main():
    print("=" * 50)
    print("Website Login and Scraper")
    print("=" * 50)
    print(
        f"Current Date and Time (UTC): {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    print("Current User's Login: cmathews393")

    # Get login and target URLs from user
    login_url = "https://app.thestorygraph.com/users/sign_in"
    target_url = "https://app.thestorygraph.com/to-read/0xchloe"

    # Create scraper instance
    scraper = WebsiteScraper(login_url, target_url)

    # Ask if user wants to use saved cookies
    use_saved_cookies = (
        input("Do you want to use saved cookies? (y/n): ").lower() == "y"
    )

    if use_saved_cookies:
        # Try to load cookies from file
        cookie_file = (
            input("Enter cookie file path (default: cookies.json): ") or "cookies.json"
        )
        scraper.load_cookies_from_file(cookie_file)

        # Test if cookies are valid
        print("Testing cookies...")

        # For requests, make a request and check if we're redirected
        response = scraper.session.get(target_url)
        print(response.text)
        if "sign_in" in response.url.lower():
            print("Cookies are invalid or expired. Please login again.")
            use_saved_cookies = False
        else:
            print("Cookies are valid!")

    if not use_saved_cookies:
        # Get login credentials
        username = input("Enter your username or email: ")
        password = getpass.getpass("Enter your password: ")

        # Login to the website
        login_success = scraper.login(username, password)

        if not login_success:
            print("Login failed. Exiting.")
            scraper.close()
            return

        # Save cookies for future use
        save_cookies = (
            input("Do you want to save cookies for future use? (y/n): ").lower() == "y"
        )
        if save_cookies:
            cookie_file = (
                input("Enter cookie file path (default: cookies.json): ")
                or "cookies.json"
            )
            scraper.save_cookies_to_file(cookie_file)

    # If using Selenium, ask for scroll count and pause time

    page = scraper.scrape_target_page()
    print(page)
    alt_texts = scraper.scrape_target_page()

    if alt_texts:
        print(f"\nFound {len(alt_texts)} unique book alt tags!")

        # Ask if user wants to see the full list
        show_full_list = (
            input("Do you want to see the full list of books? (y/n): ").lower() == "y"
        )
        if show_full_list:
            for i, alt_text in enumerate(alt_texts, 1):
                print(f"{i}. {alt_text}")

        # Optional: Parse book titles and authors from the alt text
        # Assuming the alt text follows the pattern "Title by Author"
        print("\nSample of parsed book information (first 5):")
        for alt_text in alt_texts[:5]:
            match = re.search(r"(.*)\s+by\s+(.*)", alt_text)
            if match:
                title, author = match.groups()
                print(f"Title: {title.strip()}")
                print(f"Author: {author.strip()}")
                print()

        # Ask if user wants to add books to LazyLibrarian
        add_to_lazylibrarian = (
            input("Do you want to add these books to LazyLibrarian? (y/n): ").lower()
            == "y"
        )

        if add_to_lazylibrarian:
            # Get LazyLibrarian API details
            ll_url = (
                input("Enter LazyLibrarian URL (default: http://localhost:5299): ")
                or "http://localhost:5299"
            )
            ll_api_key = input(
                "Enter LazyLibrarian API key (leave blank if not required): "
            )

            # Initialize LazyLibrarian API
            ll_api = LazyLibrarianAPI(ll_url, ll_api_key)

            # Process books
            print("\nAdding books to LazyLibrarian...")
            results = ll_api.process_books_from_alt_texts(alt_texts)

            # Display results
            print("\nLazyLibrarian Addition Results:")
            print(f"Total books processed: {results['total']}")
            print(f"Successfully added: {results['successful']}")
            print(f"Failed to add: {results['failed']}")

            # Ask if user wants to see details of failures
            if results["failed"] > 0:
                show_failures = (
                    input("Do you want to see details of failures? (y/n): ").lower()
                    == "y"
                )
                if show_failures:
                    print("\nFailed additions:")
                    for detail in results["details"]:
                        if detail.get("result", {}).get("status") == "error":
                            print(f"- {detail['alt_text']}")
                            print(
                                f"  Error: {detail.get('result', {}).get('message', 'Unknown error')}"
                            )

            # Close the LazyLibrarian API client
            ll_api.close()

        # Save the results to a file
        save_results = (
            input("Do you want to save the results to a file? (y/n): ").lower() == "y"
        )
        if save_results:
            result_file = (
                input("Enter result file path (default: book_results.txt): ")
                or "book_results.txt"
            )
            with open(result_file, "w", encoding="utf-8") as f:
                f.write(
                    f"Extracted on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
                )
                f.write("User: cmathews393\n\n")
                f.write(f"Found {len(alt_texts)} unique books:\n\n")

                for i, alt_text in enumerate(alt_texts, 1):
                    f.write(f"{i}. {alt_text}\n")
                    match = re.search(r"(.*)\s+by\s+(.*)", alt_text)
                    if match:
                        title, author = match.groups()
                        f.write(f"Title: {title.strip()}\n")
                        f.write(f"Author: {author.strip()}\n")
                    f.write("\n")
            print(f"Results saved to {result_file}")

            # Also save as CSV
            save_csv = input("Do you want to also save as CSV? (y/n): ").lower() == "y"
            if save_csv:
                import csv

                csv_file = os.path.splitext(result_file)[0] + ".csv"
                with open(csv_file, "w", encoding="utf-8", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(["Book Number", "Full Text", "Title", "Author"])

                    for i, alt_text in enumerate(alt_texts, 1):
                        title = ""
                        author = ""
                        match = re.search(r"(.*)\s+by\s+(.*)", alt_text)
                        if match:
                            title, author = match.groups()
                            title = title.strip()
                            author = author.strip()

                        writer.writerow([i, alt_text, title, author])
                print(f"CSV saved to {csv_file}")
    else:
        print("No alt tags found in the target page that match the criteria.")
        print("If this is unexpected, you might need to modify the extraction logic")
        print("to match the specific HTML structure of the website.")

    # Close the browser if using Selenium
    scraper.close()


if __name__ == "__main__":
    main()
