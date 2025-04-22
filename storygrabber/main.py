import getpass
import json
import os
import re
import time
from datetime import datetime
import urllib.parse

import httpx
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class WebsiteScraper:
    def __init__(self, login_url, target_url, use_selenium=False):
        """
        Initialize the scraper with login and target URLs

        Args:
            login_url (str): URL of the login page
            target_url (str): URL of the page to scrape after login
            use_selenium (bool): Whether to use Selenium for browser automation
        """
        self.login_url = login_url
        self.target_url = target_url
        self.use_selenium = use_selenium
        self.driver = None

        # Initialize httpx session for non-Selenium operations
        self.session = httpx.Client()
        # Add common headers to mimic a browser
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )

        if use_selenium:
            self._initialize_selenium()

    def _initialize_selenium(self):
        """Initialize Selenium WebDriver for browser automation"""
        chrome_options = Options()

        # Add argument to disable the "Chrome is being controlled by automated software" banner
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")

        # Add other Chrome options
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--disable-popup-blocking")

        # Add option to disable dev shm usage which can cause problems in containerized environments
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--headless")
        # Add no-sandbox option which can help with some environments
        chrome_options.add_argument("--no-sandbox")

        # Add additional options for frontend scraping
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)

        # Try multiple times to initialize Chrome with our options
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                self.driver = webdriver.Chrome(options=chrome_options)
                print(
                    f"Successfully initialized Chrome WebDriver (attempt {attempt+1}/{max_attempts})"
                )
                break
            except Exception as e:
                print(f"Attempt {attempt+1}/{max_attempts} failed: {str(e)}")
                if attempt == max_attempts - 1:
                    print("All attempts to initialize Chrome WebDriver failed.")
                    raise
                time.sleep(2)  # Wait before retrying

    def get_login_form_details(self):
        """
        Get the login form details from the login page

        Returns:
            dict: Form details with action URL and input fields
        """
        try:
            response = self.session.get(self.login_url)
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

    def login(self, username, password):
        """
        Login to the website using provided credentials

        Args:
            username (str): Username or email
            password (str): Password

        Returns:
            bool: True if login was successful, False otherwise
        """
        if self.use_selenium:
            return self._login_with_selenium(username, password)
        else:
            return self._login_with_requests(username, password)

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

            # Submit the login form
            if form_details["method"] == "post":
                response = self.session.post(
                    form_details["action"], data=form_details["inputs"]
                )
            else:
                response = self.session.get(
                    form_details["action"], params=form_details["inputs"]
                )

            # Check if login was successful
            if response.status_code == 200 and len(self.session.cookies) > 0:
                print("Login successful!")
                return True
            else:
                print(f"Login failed with status code: {response.status_code}")
                return False

        except Exception as e:
            print(f"Error during login: {e}")
            return False

    def _login_with_selenium(self, username, password):
        """Login using Selenium WebDriver"""
        try:
            # Navigate to login page
            self.driver.get(self.login_url)

            # Wait for the page to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "form"))
            )

            # Find username and password fields
            username_field = None
            password_field = None

            # Look for common username/password field patterns
            for input_element in self.driver.find_elements(By.TAG_NAME, "input"):
                input_type = input_element.get_attribute("type").lower()
                input_name = (
                    input_element.get_attribute("name").lower()
                    if input_element.get_attribute("name")
                    else ""
                )
                input_id = (
                    input_element.get_attribute("id").lower()
                    if input_element.get_attribute("id")
                    else ""
                )

                # Check for username/email field
                if input_type in ["text", "email"] and any(
                    term in input_name or term in input_id
                    for term in ["user", "email", "login"]
                ):
                    username_field = input_element

                # Check for password field
                if input_type == "password":
                    password_field = input_element

            if not username_field or not password_field:
                print(
                    "Error: Could not identify username or password fields in the browser."
                )
                return False

            # Fill in the login fields
            username_field.clear()
            username_field.send_keys(username)

            password_field.clear()
            password_field.send_keys(password)

            # Submit the form
            password_field.submit()

            # Wait for login to complete
            time.sleep(3)  # Basic wait

            # Check if login was successful - this is website-specific
            # For now, we'll just check if we're not still on the login page
            current_url = self.driver.current_url
            if self.login_url not in current_url or "login" not in current_url.lower():
                print("Login successful!")

                # Transfer cookies from Selenium to httpx session
                for cookie in self.driver.get_cookies():
                    self.session.cookies.set(cookie["name"], cookie["value"])

                return True
            else:
                print("Login failed. Still on login page.")
                return False

        except Exception as e:
            print(f"Error during Selenium login: {e}")
            return False

    def extract_cookies(self):
        """
        Extract cookies from the current session

        Returns:
            dict: Dictionary of cookies
        """
        if self.use_selenium and self.driver:
            # Get cookies from Selenium
            return {
                cookie["name"]: cookie["value"] for cookie in self.driver.get_cookies()
            }
        else:
            # Get cookies from httpx session
            return {k: v for k, v in self.session.cookies.items()}

    def save_cookies_to_file(self, filename="cookies.json"):
        """
        Save cookies to a file

        Args:
            filename (str): Name of the file to save cookies to
        """
        cookies = self.extract_cookies()
        with open(filename, "w") as f:
            json.dump(cookies, f, indent=4)
        print(f"Cookies saved to {filename}")

    def load_cookies_from_file(self, filename="cookies.json"):
        """
        Load cookies from a file

        Args:
            filename (str): Name of the file to load cookies from
        """
        try:
            with open(filename, "r") as f:
                cookies = json.load(f)

            # Set cookies in the appropriate context
            if self.use_selenium and self.driver:
                self.driver.get(
                    self.target_url.split("/")[0] + "//" + self.target_url.split("/")[2]
                )  # Load domain first
                for name, value in cookies.items():
                    self.driver.add_cookie({"name": name, "value": value})

            # Always set cookies in the httpx session too
            for name, value in cookies.items():
                self.session.cookies.set(name, value)

            print(f"Cookies loaded from {filename}")
        except FileNotFoundError:
            print(f"Cookie file {filename} not found.")
        except Exception as e:
            print(f"Error loading cookies: {e}")

    def extract_alt_tags_with_deduplication(self, html_content):
        """
        Extract alt text from img tags within book pane divs, ensuring only
        one alt text per book pane to avoid duplicates.

        Args:
            html_content (str): HTML content to parse

        Returns:
            list: List of extracted alt text strings without duplicates
        """
        # Parse the HTML
        soup = BeautifulSoup(html_content, "html.parser")

        # Find all book pane divs
        book_panes = soup.find_all("div", class_="book-pane-content grid grid-cols-10")

        # Extract one alt text from each book pane
        alt_texts = []
        seen_alt_texts = set()  # For tracking duplicates

        for pane in book_panes:
            # Find the book cover div within this pane
            book_cover = pane.find("div", class_="book-cover")
            if book_cover:
                # Find the img tag
                img = book_cover.find("img")
                if img and img.has_attr("alt"):
                    alt_text = img["alt"]

                    # Only add if we haven't seen this alt text before
                    if alt_text not in seen_alt_texts:
                        alt_texts.append(alt_text)
                        seen_alt_texts.add(alt_text)

        return alt_texts

    def scrape_target_page(self, scroll_count=10, scroll_pause_time=2):
        """
        Scrape the target page using the authenticated session,
        handling infinite scroll if using Selenium

        Args:
            scroll_count (int): Number of times to scroll the page (for Selenium)
            scroll_pause_time (float): Time to pause between scrolls in seconds

        Returns:
            list: List of extracted alt texts
        """
        if self.use_selenium and self.driver:
            return self._scrape_with_selenium(scroll_count, scroll_pause_time)
        else:
            return self._scrape_with_requests()

    def _scrape_with_requests(self):
        """Scrape using httpx library (no infinite scroll support)"""
        try:
            # Request the target page
            response = self.session.get(self.target_url)

            if response.status_code != 200:
                print(
                    f"Error accessing target page: Status code {response.status_code}"
                )
                return []

            # Extract alt tags from the response with deduplication
            alt_texts = self.extract_alt_tags_with_deduplication(response.text)

            return alt_texts

        except Exception as e:
            print(f"Error scraping target page with httpx: {e}")
            return []

    def _scrape_with_selenium(self, scroll_count=10, scroll_pause_time=2):
        """
        Scrape using Selenium with infinite scroll support

        Args:
            scroll_count (int): Number of times to scroll the page
            scroll_pause_time (float): Time to pause between scrolls in seconds

        Returns:
            list: List of extracted alt texts
        """
        try:
            # Navigate to the target page
            self.driver.get(self.target_url)

            # Wait for the page to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "book-cover"))
            )

            print(f"Starting to scroll the page {scroll_count} times...")
            print("Use Ctrl+C to stop scrolling if you've loaded enough content.")

            # Get initial scroll height
            last_height = self.driver.execute_script(
                "return document.body.scrollHeight"
            )

            # Track the number of scrolls without new content
            no_change_count = 0
            max_no_change = (
                3  # Stop if we've scrolled this many times without new content
            )

            # Track the number of books found after each scroll
            last_book_count = 0

            try:
                # Scroll down to load more content
                for i in range(scroll_count):
                    print(f"Scroll {i+1}/{scroll_count}", end="")

                    # Scroll down to bottom
                    self.driver.execute_script(
                        "window.scrollTo(0, document.body.scrollHeight);"
                    )

                    # Wait to load page
                    time.sleep(scroll_pause_time)

                    # Calculate new scroll height and compare with last scroll height
                    new_height = self.driver.execute_script(
                        "return document.body.scrollHeight"
                    )

                    # Get current book count
                    current_book_panes = self.driver.find_elements(
                        By.CLASS_NAME, "book-pane-content"
                    )
                    current_book_count = len(current_book_panes)

                    print(
                        f" - Found {current_book_count} books (New: {current_book_count - last_book_count})"
                    )

                    # Check if the page height has changed
                    if new_height == last_height:
                        no_change_count += 1
                        print(
                            f"  No new content detected ({no_change_count}/{max_no_change})"
                        )
                        if no_change_count >= max_no_change:
                            print("  No new content after multiple scrolls. Stopping.")
                            break
                    else:
                        no_change_count = 0

                    # Check if new books were found
                    if current_book_count == last_book_count and current_book_count > 0:
                        no_change_count += 1
                        print(
                            f"  No new books detected ({no_change_count}/{max_no_change})"
                        )
                        if no_change_count >= max_no_change:
                            print("  No new books after multiple scrolls. Stopping.")
                            break

                    last_height = new_height
                    last_book_count = current_book_count

            except KeyboardInterrupt:
                print("\nScrolling stopped by user")

            # Extract page source after scrolling
            page_source = self.driver.page_source

            # Extract alt tags with deduplication
            alt_texts = self.extract_alt_tags_with_deduplication(page_source)

            return alt_texts

        except Exception as e:
            print(f"Error scraping target page with Selenium: {e}")
            return []

    def close(self):
        """Close the browser if using Selenium and the httpx client"""
        if self.use_selenium and self.driver:
            self.driver.quit()
        self.session.close()


class LazyLibrarianAPI:
    """Interface with LazyLibrarian API endpoints to add books and authors"""

    def __init__(self, base_url="http://localhost:5299", api_key=None):
        """
        Initialize the LazyLibrarian API client

        Args:
            base_url (str): Base URL for LazyLibrarian API
            api_key (str): API key for authentication
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
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

    # Ask if user wants to use Selenium for browser automation
    use_selenium = (
        input(
            "Do you want to use browser automation for infinite scrolling? (y/n): "
        ).lower()
        == "y"
    )

    if use_selenium:
        try:
            import selenium

            print("Selenium is installed. Browser automation will be used.")
        except ImportError:
            print(
                "Selenium is not installed. Please install it with: pip install selenium webdriver-manager"
            )
            print("Continuing without browser automation...")
            use_selenium = False

    # Create scraper instance
    scraper = WebsiteScraper(login_url, target_url, use_selenium=use_selenium)

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

        if use_selenium:
            # For Selenium, navigate to the target URL and check if we're redirected to login
            scraper.driver.get(target_url)
            time.sleep(2)  # Wait for page to load
            current_url = scraper.driver.current_url
            if "login" in current_url.lower():
                print("Cookies are invalid or expired. Please login again.")
                use_saved_cookies = False
            else:
                print("Cookies are valid!")
        else:
            # For requests, make a request and check if we're redirected
            response = scraper.session.get(target_url)
            if "login" in response.url.lower():
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
    scroll_count = 10
    scroll_pause_time = 2

    if use_selenium:
        try:
            scroll_input = input("Enter number of times to scroll (default: 10): ")
            if scroll_input.strip():
                scroll_count = int(scroll_input)

            pause_input = input("Enter seconds to pause between scrolls (default: 2): ")
            if pause_input.strip():
                scroll_pause_time = float(pause_input)
        except ValueError:
            print("Invalid input. Using defaults.")

    # Scrape the target page
    print("\nScraping target page...")
    if use_selenium:
        print("Using browser automation with infinite scroll support.")
        print("The browser will scroll down automatically to load more content.")
        print(
            "Press Ctrl+C at any time to stop scrolling and extract the currently loaded books."
        )

    alt_texts = scraper.scrape_target_page(
        scroll_count=scroll_count, scroll_pause_time=scroll_pause_time
    )

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
