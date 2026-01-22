from flask import Blueprint, jsonify, request
from storygrab.modules import storygraph
from storygrab.modules.lazylibrarian import LazyLibrarianClient
import os
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
import re

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/get_books/<username>", methods=["GET"])
def get_books_for_user(username: str):
    # Support TTL and explicit refresh via query params
    try:
        ttl = int(request.args.get("ttl", os.getenv("SG_CACHE_TTL", "900")))
    except Exception:
        ttl = 900
    refresh = str(request.args.get("refresh", "false")).lower() in ("1", "true", "yes")

    if not refresh:
        cached = _read_cache(username)
        if cached and cached.get("fetched_at"):
            try:
                fetched_time = datetime.fromisoformat(cached.get("fetched_at"))
                if datetime.now(timezone.utc) - fetched_time <= timedelta(seconds=ttl):
                    # Return cached payload
                    return jsonify(
                        {
                            "cached": True,
                            "fetched_at": cached.get("fetched_at"),
                            "books": cached.get("books"),
                        }
                    )
            except Exception:
                # ignore parse errors and fall through to refresh
                pass

    # Fetch fresh data and cache it
    books = storygraph.StoryGrabber(username).get_books() or []
    cached = _write_cache(username, books)
    return jsonify(
        {"cached": False, "fetched_at": cached.get("fetched_at"), "books": books}
    )


@api_bp.route("/match_books", methods=["POST"])
def match_books():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    types = data.get("types", ["eBook", "AudioBook"])
    max_books = int(data.get("max_books", 50))

    # Support cache refresh and TTL
    refresh = bool(data.get("refresh")) or str(
        request.args.get("refresh", "false")
    ).lower() in (
        "1",
        "true",
        "yes",
    )
    try:
        ttl = int(
            data.get("ttl", request.args.get("ttl", os.getenv("SG_CACHE_TTL", "900")))
        )
    except Exception:
        ttl = 900

    if not username:
        return jsonify({"success": False, "error": "username is required"}), 400

    # Get StoryGraph books (use cache if available)
    if not bool(data.get("refresh")):
        cached = _read_cache(username)
        if cached and cached.get("fetched_at"):
            try:
                fetched_time = datetime.fromisoformat(cached.get("fetched_at"))
                if datetime.now(timezone.utc) - fetched_time <= timedelta(seconds=ttl):
                    books = cached.get("books", []) or []
                    used_cache = True
                    fetched_at = cached.get("fetched_at")
                else:
                    books = None
                    used_cache = False
            except Exception:
                books = None
                used_cache = False
        else:
            books = None
            used_cache = False
    else:
        books = None
        used_cache = False

    if books is None:
        books = storygraph.StoryGrabber(username).get_books() or []
        cached_data = _write_cache(username, books)
        fetched_at = cached_data.get("fetched_at")
        used_cache = False

    # LazyLibrarian client
    ll_host = os.getenv("LL_HOST", "localhost")
    ll_port = int(os.getenv("LL_PORT", "5299"))
    ll_api_key = os.getenv("LL_API_KEY", "")
    ll_use_https = os.getenv("LL_HTTPS", "False").lower() == "true"

    if not ll_api_key:
        return (
            jsonify(
                {"success": False, "error": "LL_API_KEY not configured in environment"}
            ),
            400,
        )

    ll_client = LazyLibrarianClient(
        host=ll_host, port=ll_port, api_key=ll_api_key, use_https=ll_use_https
    )

    # Build a normalized index from getAllBooks (cached by _get_ll_library)
    title_map, title_author_map = _build_ll_index(ll_client, force=refresh)

    def _norm(s: str) -> str:
        if not s:
            return ""
        t = re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())
        return " ".join(t.split())

    results = []

    for i, b in enumerate(books[:max_books]):
        # b may be (url, title, author) or dict
        if isinstance(b, (list, tuple)):
            book_url, title, author = b[0], b[1], b[2]
        elif isinstance(b, dict):
            title = b.get("title") or b.get("BookName") or b.get("book_name")
            author = b.get("author") or b.get("Author") or ""
            book_url = b.get("url") or ""
        else:
            continue

        match_entry = {
            "title": title,
            "author": author,
            "storygraph_url": book_url,
            "matches": {},
            "library_matches": [],
        }

        ntitle = _norm(title)
        nauthor = _norm(author)

        matched_items = []
        if ntitle:
            key = f"{ntitle} {nauthor}".strip() if nauthor else ntitle
            if key and key in title_author_map:
                matched_items = title_author_map[key]
            elif ntitle in title_map:
                matched_items = title_map[ntitle]
            else:
                # fuzzy subset word matching
                twords = set(ntitle.split())
                if twords:
                    for k, items in title_map.items():
                        kwords = set(k.split())
                        if twords.issubset(kwords) or kwords.issubset(twords):
                            matched_items = items
                            break

        if matched_items:
            # summarize availability/status
            for t in types:
                available = False
                raw = []
                statuses = set()
                for item in matched_items:
                    raw.append(item)
                    if t == "eBook":
                        if item.get("BookLibrary"):
                            available = True
                            statuses.add("In Library")
                        if item.get("Status"):
                            statuses.add(str(item.get("Status")))
                    if t == "AudioBook":
                        if item.get("AudioLibrary"):
                            available = True
                            statuses.add("In Library")
                        if item.get("AudioStatus"):
                            statuses.add(str(item.get("AudioStatus")))

                if available:
                    status_str = "In Library"
                elif statuses:
                    status_str = ", ".join(sorted(statuses))
                else:
                    status_str = "Missing"

                match_entry["matches"][t] = {
                    "matched": bool(available),
                    "status": status_str,
                    "raw": raw,
                }

            match_entry["library_matches"] = matched_items
            match_entry["match_method"] = "library"

        else:
            # no library match; don't run remote searches automatically
            for t in types:
                match_entry["matches"][t] = {
                    "matched": False,
                    "status": "Missing",
                    "raw": None,
                }
            match_entry["search_possible"] = True

        results.append(match_entry)

    return jsonify(
        {
            "success": True,
            "username": username,
            "total_checked": len(results),
            "results": results,
            "cached": bool(used_cache),
            "fetched_at": fetched_at,
        }
    )


def _cache_dir() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    cache_dir = repo_root / "app" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", name)


def _cache_path_for(username: str) -> Path:
    name = _safe_name(username)
    return _cache_dir() / f"{name}.json"


def _read_cache(username: str):
    p = _cache_path_for(username)
    if not p.exists():
        return None
    try:
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # corrupted cache; ignore
        return None


def _write_cache(username: str, books):
    p = _cache_path_for(username)
    tmp = p.with_suffix(".tmp")
    data = {
        "username": username,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "books": books,
    }
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f)
    tmp.replace(p)
    return data


@api_bp.route("/refresh_books/<username>", methods=["POST"])
def refresh_books(username: str):
    data = request.get_json(silent=True) or {}
    types = data.get("types", ["eBook", "AudioBook"])
    max_books = int(data.get("max_books", 50))

    # LazyLibrarian config from env
    ll_host = os.getenv("LL_HOST", "localhost")
    ll_port = int(os.getenv("LL_PORT", "5299"))
    ll_api_key = os.getenv("LL_API_KEY", "")
    ll_use_https = os.getenv("LL_HTTPS", "False").lower() == "true"

    if not ll_api_key:
        return (
            jsonify(
                {"success": False, "error": "LL_API_KEY not configured in environment"}
            ),
            400,
        )

    sg = storygraph.StoryGrabber(username)
    books = sg.get_books() or []

    ll_client = LazyLibrarianClient(
        host=ll_host, port=ll_port, api_key=ll_api_key, use_https=ll_use_https
    )

    # Build a LazyLibrarian title/author index for quick local matches
    title_map, title_author_map = _build_ll_index(ll_client)

    results = []

    for i, b in enumerate(books[:max_books]):
        # b may be (url, title, author) or dict
        if isinstance(b, (list, tuple)):
            book_url, title, author = b[0], b[1], b[2]
        elif isinstance(b, dict):
            title = b.get("title") or b.get("BookName") or b.get("book_name")
            author = b.get("author") or b.get("Author") or ""
            book_url = b.get("url") or ""
        else:
            # Unknown format
            continue

        match_entry = {
            "title": title,
            "author": author,
            "storygraph_url": book_url,
            "matches": {},
        }

        # Optionally fetch LazyLibrarian's entire library to match against locally
        use_library = data.get("use_library", True)
        ll_library = []
        title_map = {}

        if use_library:
            try:
                raw_all = ll_client.get_all_books()
                # Normalize: _make_request returns either list or dict (with 'data')
                if isinstance(raw_all, dict) and raw_all.get("data"):
                    ll_library = raw_all.get("data")
                elif isinstance(raw_all, list):
                    ll_library = raw_all
                else:
                    # try normalization helper
                    norm = ll_client._normalize_response(raw_all)
                    ll_library = norm.get("data") if isinstance(norm, dict) else []

                for item in ll_library:
                    name = (item.get("BookName") or "").strip().lower()
                    if name:
                        title_map.setdefault(name, []).append(item)
            except Exception:
                # If getAllBooks fails, we simply proceed without library index
                ll_library = []
                title_map = {}

        # Heuristic match against local library first
        matched_locally = False
        if ll_library and title_map:
            key = (title + " " + author).strip().lower()
            if key in title_map:
                matched_locally = True
                match_entry["matches"] = {
                    t: {"matched": True, "raw": title_map[key]} for t in types
                }
                match_entry["match_method"] = "library"

        if not matched_locally:
            # Try to match against LazyLibrarian's library index first (if available)
            def _norm(s):
                if not s:
                    return ""
                t = re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())
                t = " ".join(t.split())
                return t

            matched_items = []
            ntitle = _norm(title)
            nauthor = _norm(author)
            if ntitle:
                # exact title+author match
                key = f"{ntitle} {nauthor}".strip()
                if key and key in title_author_map:
                    matched_items = title_author_map[key]
                elif ntitle in title_map:
                    matched_items = title_map[ntitle]
                else:
                    # fuzzy: title words subset of candidate title words
                    twords = set(ntitle.split())
                    if twords:
                        for k, items in title_map.items():
                            kwords = set(k.split())
                            if twords.issubset(kwords) or kwords.issubset(twords):
                                matched_items = items
                                break

            if matched_items:
                # We have candidate(s) from library
                # For each requested type, aggregate availability and statuses across candidates
                for t in types:
                    available = False
                    raw = []
                    statuses = set()
                    for item in matched_items:
                        raw.append(item)
                        if t == "eBook":
                            if item.get("BookLibrary"):
                                available = True
                                statuses.add("In Library")
                            if item.get("Status"):
                                statuses.add(str(item.get("Status")))
                        if t == "AudioBook":
                            if item.get("AudioLibrary"):
                                available = True
                                statuses.add("In Library")
                            if item.get("AudioStatus"):
                                statuses.add(str(item.get("AudioStatus")))

                    if available:
                        status_str = "In Library"
                    elif statuses:
                        status_str = ", ".join(sorted(statuses))
                    else:
                        status_str = "Missing"

                    match_entry["matches"][t] = {
                        "matched": bool(available),
                        "raw": raw,
                        "status": status_str,
                    }

                match_entry["library_matches"] = matched_items
                match_entry["match_method"] = "library"
                results.append(match_entry)
                continue

            try:
                search_res = ll_client.find_book(title)
            except Exception as e:
                results.append({"title": title, "author": author, "error": str(e)})
                continue

            # Normalize result - find_book can return list or dict
            matched_id = None
            if isinstance(search_res, list) and len(search_res) > 0:
                best = search_res[0]
                # try common id fields
                for key in ("bookid", "id", "BookID"):
                    if isinstance(best, dict) and best.get(key):
                        matched_id = best.get(key)
                        break
            elif isinstance(search_res, dict):
                # sometimes dict with 'message' or 'data'
                if (
                    search_res.get("success")
                    and isinstance(search_res.get("data"), list)
                    and len(search_res.get("data")) > 0
                ):
                    best = search_res.get("data")[0]
                    for key in ("bookid", "id", "BookID"):
                        if best.get(key):
                            matched_id = best.get(key)
                            break

            match_entry["lazy_match_id"] = matched_id
            match_entry["lazy_find_raw"] = search_res

            # Do not run remote find/search automatically here. Let the UI trigger explicit searches.
            for t in types:
                match_entry["matches"][t] = {"matched": False, "raw": None}
            match_entry["search_possible"] = True

            results.append(match_entry)
            continue

    # Update cache
    _write_cache(username, results)

    return jsonify(
        {
            "success": True,
            "username": username,
            "total_checked": len(results),
            "results": results,
        }
    )


@api_bp.route("/cached_books/<username>", methods=["GET"])
def cached_books(username: str):
    data = _read_cache(username)
    if not data:
        return jsonify({"success": False, "error": "No cached data found"}), 404

    # Optionally respect a TTL (time-to-live) for the cache
    ttl = 300  # default TTL 5 minutes
    fetched_at = data.get("fetched_at")
    if fetched_at:
        try:
            fetched_time = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) - fetched_time > timedelta(seconds=ttl):
                return jsonify({"success": False, "error": "Cached data expired"}), 410
        except Exception:
            pass  # ignore parse errors, treat as expired

    return jsonify({"success": True, "username": username, "books": data["books"]})


@api_bp.route("/find_books_ll", methods=["POST"])
def find_books_ll():
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    author = data.get("author", "")
    remote = bool(data.get("remote", False))

    if not title:
        return jsonify({"success": False, "error": "title is required"}), 400

    ll_host = os.getenv("LL_HOST", "localhost")
    ll_port = int(os.getenv("LL_PORT", "5299"))
    ll_api_key = os.getenv("LL_API_KEY", "")
    ll_use_https = os.getenv("LL_HTTPS", "False").lower() == "true"

    if not ll_api_key:
        return jsonify(
            {"success": False, "error": "LL_API_KEY not configured in environment"}
        ), 400

    ll_client = LazyLibrarianClient(
        host=ll_host, port=ll_port, api_key=ll_api_key, use_https=ll_use_https
    )

    # Build an index of local LL books
    title_map, title_author_map = _build_ll_index(ll_client, force=False)

    def _norm(s: str) -> str:
        if not s:
            return ""
        t = re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())
        return " ".join(t.split())

    ntitle = _norm(title)
    nauthor = _norm(author)

    candidates = []

    # exact title+author
    key = f"{ntitle} {nauthor}".strip()
    if key and key in title_author_map:
        candidates = title_author_map[key]

    # exact title
    if not candidates and ntitle in title_map:
        candidates = title_map[ntitle]

    # fuzzy subset/overlap
    if not candidates and ntitle:
        twords = set(ntitle.split())
        if twords:
            scored = []
            for k, items in title_map.items():
                kwords = set(k.split())
                inter = len(twords & kwords)
                if inter == 0:
                    continue
                score = inter / max(len(twords), len(kwords))
                if score >= 0.5:
                    scored.append((score, items))
            scored.sort(key=lambda x: x[0], reverse=True)
            for _, items in scored[:10]:
                candidates.extend(items)

    if candidates and len(candidates) > 0:
        # return first N candidates
        return jsonify({"success": True, "source": "local", "results": candidates[:10]})

    # fallback to remote find_book if requested
    if remote:
        try:
            res = ll_client.find_book(title)
            return jsonify({"success": True, "source": "remote", "results": res})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    # no local candidates and remote not requested
    return jsonify({"success": True, "source": "local", "results": []})


@api_bp.route("/add_book_ll", methods=["POST"])
def add_book_ll():
    data = request.get_json(silent=True) or {}
    book_id = data.get("book_id")
    if not book_id:
        return jsonify({"success": False, "error": "book_id is required"}), 400

    ll_host = os.getenv("LL_HOST", "localhost")
    ll_port = int(os.getenv("LL_PORT", "5299"))
    ll_api_key = os.getenv("LL_API_KEY", "")
    ll_use_https = os.getenv("LL_HTTPS", "False").lower() == "true"

    if not ll_api_key:
        return jsonify(
            {"success": False, "error": "LL_API_KEY not configured in environment"}
        ), 400

    ll_client = LazyLibrarianClient(
        host=ll_host, port=ll_port, api_key=ll_api_key, use_https=ll_use_https
    )

    try:
        res = ll_client.add_book(book_id)
        return jsonify({"success": True, "book_id": book_id, "result": res})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/queue_book_ll", methods=["POST"])
def queue_book_ll():
    data = request.get_json(silent=True) or {}
    book_id = data.get("book_id")
    book_type = data.get("book_type", "eBook")
    if not book_id:
        return jsonify({"success": False, "error": "book_id is required"}), 400

    ll_host = os.getenv("LL_HOST", "localhost")
    ll_port = int(os.getenv("LL_PORT", "5299"))
    ll_api_key = os.getenv("LL_API_KEY", "")
    ll_use_https = os.getenv("LL_HTTPS", "False").lower() == "true"

    if not ll_api_key:
        return jsonify(
            {"success": False, "error": "LL_API_KEY not configured in environment"}
        ), 400

    ll_client = LazyLibrarianClient(
        host=ll_host, port=ll_port, api_key=ll_api_key, use_https=ll_use_https
    )

    try:
        res = ll_client.queue_book(book_id, book_type=book_type)
        return jsonify(
            {"success": True, "book_id": book_id, "book_type": book_type, "result": res}
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# In-memory cache for LazyLibrarian getAllBooks to avoid hammering the API
_LL_CACHE_TTL = int(os.getenv("LL_CACHE_TTL", "60"))  # seconds
_ll_cache = {"data": None, "fetched_at": None}


def _get_ll_library(ll_client, force: bool = False):
    """Return the list of books from LazyLibrarian, using a short-lived in-memory cache."""
    now = datetime.now(timezone.utc)
    if not force and _ll_cache["data"] and _ll_cache["fetched_at"]:
        if (now - _ll_cache["fetched_at"]).total_seconds() <= _LL_CACHE_TTL:
            return _ll_cache["data"]

    try:
        raw_all = ll_client.get_all_books()
        if isinstance(raw_all, dict) and raw_all.get("data"):
            ll_library = raw_all.get("data")
        elif isinstance(raw_all, list):
            ll_library = raw_all
        else:
            norm = ll_client._normalize_response(raw_all)
            ll_library = norm.get("data") if isinstance(norm, dict) else []

        _ll_cache["data"] = ll_library
        _ll_cache["fetched_at"] = now
        return ll_library
    except Exception:
        # on error, return whatever is in cache (may be None)
        return _ll_cache.get("data")


# update _build_ll_index to use the short-lived ll cache
def _build_ll_index(ll_client, force: bool = False):
    """Return (title_map, title_author_map) built from getAllBooks."""
    title_map = {}
    title_author_map = {}

    def _norm(s: str) -> str:
        if not s:
            return ""
        t = re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())
        return " ".join(t.split())

    ll_library = _get_ll_library(ll_client, force=force) or []

    try:
        for item in ll_library:
            bname = _norm(item.get("BookName") or "")
            aname = _norm(item.get("AuthorName") or item.get("Author") or "")
            if bname:
                title_map.setdefault(bname, []).append(item)
            if bname and aname:
                title_author_map.setdefault(f"{bname} {aname}", []).append(item)
    except Exception:
        return {}, {}

    return title_map, title_author_map
