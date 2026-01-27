"""Backend api for js calls."""

import os
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request
from loguru import logger

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


@api_bp.route("/get_storygraph_list/<username>", methods=["GET"])
def get_storygraph_list(username: str) -> tuple:
    """Get books for a user."""
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
            except (ValueError, TypeError):
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


@api_bp.route("/match_books/<sg_username>", methods=["GET"])
def match_books(sg_username: str) -> tuple:
    """Match books between Storygraph and LazyLibrarian."""
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
    sg_cache_ttl = int(os.getenv("SG_CACHE_TTL", "1"))
    no_cache = request.args.get("no_cache", "false").lower() == "true"

    if no_cache:
        # Force bypass cache and fetch fresh
        sg_books = Storygraph().get_books(sg_username)
    else:
        # Try to read from cache; handle missing/stale cache gracefully
        cached = read_cache("storygraph", sg_username) or {}
        ts_raw = cached.get("timestamp")
        ts = None
        if ts_raw:
            try:
                ts = datetime.fromisoformat(ts_raw)
            except (ValueError, TypeError):
                ts = None

        # If cache exists and is fresh, use it for matching instead of returning early
        if ts and ts > datetime.now(tz=timezone.utc) - timedelta(hours=sg_cache_ttl):
            sg_books = cached.get("books", [])
        else:
            # Cache missing or stale -> fetch fresh
            sg_books = Storygraph().get_books(sg_username)
    abs_client = AudioBookShelf()
    abs_libraries = abs_client.get_libraries()
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
    abs_df = abs_items_aggregated_df(abs_books)
    ll_df = records_to_df(ll_books)
    sg_df = storygraph_records_to_df(sg_books)
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

    abs_merge.fillna(value="", inplace=True)

    return jsonify(abs_merge.to_dict(orient="records")), 200


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
        )  # TODO(@cmathews393): make a new helper function.
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
        )  # TODO(@cmathews393): make a new helper function.

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

    return jsonify({"success": True, "result": resp}), 200
