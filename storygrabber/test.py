import time

from webdriver_manager.chrome import ChromeDriverManager

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service


def initialize_browser():
    """Initialize a Chrome browser using Selenium WebDriver"""
    # Set up Chrome options
    chrome_options = Options()
    # Uncomment the line below if you want to run headless
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    # Initialize the Chrome driver
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=chrome_options
    )

    # Set an implicit wait to handle timing issues
    driver.implicitly_wait(10)

    return driver


def main():
    # Initialize the browser
    print("Initializing browser...")
    browser = initialize_browser()

    try:
        # Navigate to Google
        print("Navigating to Google...")
        browser.get("https://www.google.com")

        # Verify we're on Google
        assert "Google" in browser.title
        print(f"Successfully loaded: {browser.title}")

        # Pause to see the page (remove in production)
        time.sleep(3)

    finally:
        # Clean up
        print("Closing browser...")
        browser.quit()


if __name__ == "__main__":
    main()
