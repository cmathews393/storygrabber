"""Backend api for js calls."""

import logging
import os
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

from storygrabber.modules.audiobookshelf import AudioBookShelf
from storygrabber.modules.lazylibrarian import LazyLibrarian
from storygrabber.modules.storygraph import Storygraph
from storygrabber.modules.util import (
    abs_items_aggregated_df,
    read_cache,
    records_to_df,
    storygraph_records_to_df,
)

api_bp = Blueprint("api", __name__, url_prefix="/api")
logger = logging.getLogger(__name__)


@api_bp.route("/get_storygraph_list/<username>", methods=["GET"])
def get_storygraph_list(username: str) -> tuple:
    """Get a list of books for a user."""
    sg_cache_ttl = int(os.getenv("SG_CACHE_TTL", "1"))
    no_cache = request.args.get("no_cache", "false").lower() == "true"

    if no_cache:
        # Force bypass cache and fetch fresh
        books = Storygraph().get_books(username)
    else:
        # Try to read from cache; handle missing/stale cache gracefully
        cached = read_cache("storygraph", username) or {}
        ts_raw = cached.get("timestamp")
        ts = None
        if ts_raw:
            try:
                ts = datetime.fromisoformat(ts_raw)
            except Exception:
                ts = None

        if ts and ts > datetime.now(tz=timezone.utc) - timedelta(hours=sg_cache_ttl):
            return jsonify(cached.get("books", [])), 200

        # Cache missing or stale -> fetch fresh
        books = Storygraph().get_books(username)

    return jsonify(books), 200


@api_bp.route("/get_ll_books", methods=["GET"])
def get_ll_books() -> tuple:
    """Get a list of books from LL."""
    ll_host = os.getenv("LL_HOST", "localhost")
    ll_port = os.getenv("LL_PORT", "5299")
    ll_api_key = os.getenv("LL_API_KEY", "changeme")
    ll_https = os.getenv("LL_HTTPS", "false").lower() == "true"
    ll_books = LazyLibrarian(
        ll_host,
        int(ll_port),
        ll_api_key,
        ll_https,
    ).get_all_books()
    return jsonify(ll_books), 200


@api_bp.route("/match_books", methods=["POST"])
def match_books() -> tuple:
    """Match books between Storygraph and LazyLibrarian using pure-Python merging.

    This avoids importing pandas at module import time so the app and tests can
    run in environments where pandas is not installed.
    """
    data = request.get_json() or {}
    sg_books = data.get("sg_books", [])
    ll_books = data.get("ll_books", [])
    abs_books = data.get("abs_books", [])
    sg_df = storygraph_records_to_df(sg_books)
    ll_df = records_to_df(ll_books)
    abs_client = AudioBookShelf()
    abs_libraries = abs_client.get_libraries()
    lib_map = {lib.id: lib.name for lib in abs_libraries}
    # If caller didn't pass ABS items, fetch items from AudiobookShelf for each library
    if not abs_books:
        abs_books = []
        for lib in abs_libraries:
            try:
                items = abs_client.get_library_items(lib.id)
            except Exception:
                logger.exception("Error fetching ABS library items for %s", lib.id)
                items = []
            for item in items:
                if hasattr(item, "model_dump"):
                    d = item.model_dump()
                else:
                    try:
                        d = dict(item)
                    except Exception:
                        d = vars(item) if hasattr(item, "__dict__") else {}
                # Ensure library name present for aggregation
                d.setdefault("libraryName", lib.name)
                abs_books.append(d)
    # Debug: log number of abs items and a sample of the first item
    logger.debug("ABS books fetched: %d", len(abs_books))
    if abs_books:
        try:
            logger.debug("Sample ABS item keys: %s", list(abs_books[0].keys()))
        except Exception:
            logger.debug("Sample ABS item (raw): %s", str(abs_books[0]))
    abs_df = abs_items_aggregated_df(abs_books)
    logger.debug("abs_df rows=%d columns=%s", len(abs_df), list(abs_df.columns))
    merged_df = sg_df.merge(
        ll_df,
        on=["title", "author"],
        how="left",
        suffixes=("_sg", "_ll"),
    )
    # Merge aggregated ABS fields (adds abs_in_ebook/abs_in_audiobook and library lists)
    abs_merge = merged_df.merge(
        abs_df,
        on=["title", "author"],
        how="left",
    )
    # Ensure NaN values are converted to None (JSON null) since NaN is not valid JSON
    records = abs_merge.to_dict(orient="records")
    import math

    sanitized = []
    for rec in records:
        new_rec = {}
        for k, v in rec.items():
            try:
                if math.isnan(v):
                    new_rec[k] = None
                    continue
            except Exception:
                # math.isnan will raise for non-numeric types; leave value as-is
                pass
            new_rec[k] = v
        sanitized.append(new_rec)

    # Convert abs library strings to lists and build abs_by_library mapping
    for rec in sanitized:

        def _to_list(raw):
            if raw is None:
                return []
            if isinstance(raw, list):
                return raw
            if isinstance(raw, str):
                return [x for x in raw.split(",") if x]
            return []

        def _map_token(tok):
            return lib_map.get(tok, tok)

        ebook_list = [_map_token(x) for x in _to_list(rec.get("abs_ebook_libraries"))]
        audio_list = [
            _map_token(x) for x in _to_list(rec.get("abs_audiobook_libraries"))
        ]
        rec["abs_ebook_libraries"] = ebook_list
        rec["abs_audiobook_libraries"] = audio_list
        libs = sorted(set(ebook_list) | set(audio_list))
        rec["abs_by_library"] = {
            lib: {"ebook": lib in ebook_list, "audiobook": lib in audio_list}
            for lib in libs
        }

    return jsonify(sanitized), 200


@api_bp.route("/ll/mark_wanted", methods=["POST"])
def ll_mark_wanted() -> tuple:
    """Mark a LazyLibrarian book as Wanted (skeleton implementation).

    Expected payload: {"book_id": "123", "book_type": "eBook"}
    """
    data = request.get_json() or {}
    book_id = data.get("book_id")
    book_type = data.get("book_type", "eBook")
    if not book_id:
        return jsonify({"success": False, "error": "missing book_id"}), 400

    ll_host = os.getenv("LL_HOST", "localhost")
    ll_port = os.getenv("LL_PORT", "5299")
    ll_api_key = os.getenv("LL_API_KEY", "changeme")
    ll_https = os.getenv("LL_HTTPS", "false").lower() == "true"

    try:
        ll = LazyLibrarian(ll_host, int(ll_port), ll_api_key, ll_https)

        resp = ll._make_request(
            "queueBook",
            {"id": book_id, "type": book_type},
        )
        ll_force_search(data=data)

    except Exception as e:  # pragma: no cover - conservative error handling
        return jsonify({"success": False, "error": str(e)}), 500

    return jsonify({"success": True, "result": resp}), 200


@api_bp.route("/ll/force_search", methods=["POST"])
def ll_force_search(data: dict | None = None) -> tuple:
    data = request.get_json() or data
    if data is None:
        return jsonify({"success": False, "error": "missing data"}), 400
    book_id = data.get("book_id")
    book_type = data.get("book_type", "eBook")
    if not book_id:
        return jsonify({"success": False, "error": "missing book_id"}), 400

    ll_host = os.getenv("LL_HOST", "localhost")
    ll_port = os.getenv("LL_PORT", "5299")
    ll_api_key = os.getenv("LL_API_KEY", "changeme")
    ll_https = os.getenv("LL_HTTPS", "false").lower() == "true"

    try:
        ll = LazyLibrarian(ll_host, int(ll_port), ll_api_key, ll_https)

        resp = ll._make_request(
            "searchBook",
            {"id": book_id, "type": book_type},
        )

    except Exception as e:  # pragma: no cover - conservative error handling
        return jsonify({"success": False, "error": str(e)}), 500

    return jsonify({"success": True, "result": resp}), 200


def abs_get_libraries() -> list:
    """Get a list of libraries from Audiobookshelf."""
    from storygrabber.modules.audiobookshelf import AudioBookShelf

    abs_client = AudioBookShelf()
    return abs_client.get_libraries()

    # Convert to list of dicts for JSON serialization


@api_bp.route("/abs/get_items", methods=["GET"])
def abs_get_items() -> tuple:
    """Get a list of items from a specific Audiobookshelf library.

    Expects a 'library_id' query parameter.
    """
    from storygrabber.modules.audiobookshelf import AudioBookShelf

    libraries = abs_get_libraries()
    for library in libraries:
        library_id = library.id

        abs_client = AudioBookShelf()
        items = abs_client.get_library_items(library_id)

        # Convert to list of dicts for JSON serialization
        items_dicts = [item.model_dump() for item in items]

        return jsonify(items_dicts), 200
    return jsonify({"error": "No libraries found"}), 404
