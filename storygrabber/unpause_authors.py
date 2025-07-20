from lazylibrarian import LazyLibrarianClient
import os
from loguru import logger
from time import sleep
import dotenv
import json

dotenv.load_dotenv()
ll_host = os.getenv("LL_HOST", "localhost")
ll_port = int(os.getenv("LL_PORT", "5299"))
ll_api_key = os.getenv("LL_API_KEY", "")
ll_use_https = os.getenv("LL_HTTPS", "False").lower() == "true"
logger.debug(
    f"LazyLibrarian config: host={ll_host}, port={ll_port}, https={ll_use_https}"
)
ll = LazyLibrarianClient(
    host=ll_host, port=ll_port, api_key=ll_api_key, use_https=ll_use_https
)

ll.test_connection()

authors = ll.get_all_authors()

json.dump(authors["message"], open("authors.json", "w"), indent=2)


def extract_author_ids(authors_data):
    """Extract author IDs from the LazyLibrarian response"""
    author_ids = []

    # Check if authors_data is a string and parse it
    if isinstance(authors_data, str):
        try:
            import json

            authors_data = json.loads(authors_data)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse authors JSON: {e}")
            return []

    # Now process the parsed data
    if isinstance(authors_data, list):
        for author in authors_data:
            if isinstance(author, dict):
                # Try AuthorID first (LazyLibrarian standard)
                if "AuthorID" in author:
                    author_id = author["AuthorID"]
                    if author_id:
                        author_ids.append(author_id)
                # Fallback to id field
                elif "id" in author:
                    author_id = author["id"]
                    if author_id:
                        author_ids.append(author_id)
    else:
        logger.warning(f"Expected list but got {type(authors_data)}")

    return author_ids


def unpause_authors():
    """Unpause all authors found in the system"""
    try:
        # Extract author IDs from the response
        author_ids = extract_author_ids(authors["message"])

        logger.info(f"Found {len(author_ids)} authors to process")

        # Filter for paused authors if needed, or unpause all
        unpaused_count = 0

        for author_id in author_ids:
            try:
                # Use the resume_author method (resume = unpause in LazyLibrarian)
                result = ll.resume_author(author_id)

                if result.get("success", True):
                    logger.info(f"Successfully unpaused author ID: {author_id}")
                    unpaused_count += 1
                else:
                    logger.warning(
                        f"Failed to unpause author ID: {author_id} - {result}"
                    )

                # Add a small delay to avoid overwhelming the API
                sleep(0.1)

            except Exception as e:
                logger.error(f"Error unpausing author ID {author_id}: {e}")

        logger.info(f"Successfully unpaused {unpaused_count}/{len(author_ids)} authors")

    except Exception as e:
        logger.error(f"Error in unpause_authors: {e}")


# Debug: Log sample author data to understand the structure
if authors["message"]:
    sample_author = authors["message"][0]
    logger.info(f"Sample author structure: {sample_author}")

    # Extract and log author IDs
    author_ids = extract_author_ids(authors["message"])
    logger.info(f"Extracted author IDs: {author_ids[:5]}...")  # Log first 5 IDs

    # Run the unpause logic
    unpause_authors()
else:
    logger.warning("No authors found in response")
