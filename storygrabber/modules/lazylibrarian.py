import json
import urllib.parse
from typing import Any

import httpx
from loguru import logger


class LazyLibrarian:
    """LazyLibrarian API client."""

    def __init__(
        self,
        host: str,
        port: int,
        api_key: str,
        use_https: bool = False,  # noqa: FBT001, FBT002
    ) -> None:
        """Setup connection and session."""
        protocol = "https" if use_https else "http"
        self.base_url = f"{protocol}://{host}:{port}/api"
        self.api_key = api_key
        self.session = httpx.Client(timeout=60)

    def _make_request(
        self,
        command: str,
        params: dict[str, str] | None = None,
        wait: bool = False,
    ) -> dict:
        if params is None:
            params = {}
        params["cmd"] = command
        params["apikey"] = self.api_key
        if wait:
            params["wait"] = "1"
        encoded_params = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        # Use urllib.parse.urlencode for proper encoding
        url = f"{self.base_url}?{encoded_params}"
        response = self.session.get(url)
        response.raise_for_status()
        response_text = response.text.strip()
        logger.debug(f"Raw response text (first 200 chars): {response_text[:200]}")

        if response_text == "OK":
            logger.debug("Response is 'OK' - returning success dictionary")
            return {"success": True, "message": "OK"}
        # Parse as JSON using json.loads()
        try:
            parsed_response = json.loads(response_text)
            logger.debug(
                f"Successfully parsed JSON response, type: {type(parsed_response)}",
            )

        except json.JSONDecodeError as json_error:
            # If it's not valid JSON, return as message
            logger.warning(f"Failed to parse response as JSON: {json_error}")
            logger.debug(f"Non-JSON response text: {response_text}")
            return {"success": True, "message": response_text}
        return parsed_response

    def _normalize_response(self, response: Any) -> dict[str, Any]:
        """Normalize API responses to ensure they're always dictionaries.

        Lazy Librarian's API is inconsistent across endpoints, we normalize so we can
        always process a response with the same (ish) keys.

        Args:
            response: The raw API response

        Returns:
            A normalized dictionary response
        """
        logger.debug(f"Normalizing response of type: {type(response)}")

        if isinstance(response, dict):
            logger.debug("Response is already a dictionary")
            return response
        if isinstance(response, list):
            logger.debug(
                f"Response is a list with {len(response)} items - normalizing to dict",
            )
            return {"success": True, "data": response}
        logger.warning(
            f"Unexpected response format: {type(response)}, value: {response}",
        )
        return {
            "success": False,
            "error": f"Unexpected response format: {type(response)}",
        }

    def get_all_books(self) -> dict[str, Any]:
        """List all books in the database.

        Returns:
            List of all books
        """
        logger.debug("Getting all books from database")
        result = self._make_request("getAllBooks")
        logger.debug(
            f"get_all_books response count: {len(result) if isinstance(result, list) else 'N/A'}",
        )
        return self._normalize_response(result)
