"""General utility functions for StoryGrabber."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd
from loguru import logger


def write_cache(cache_type: str, username: str, data: list) -> None:
    """Write the cache for a given type and username."""
    if None in (cache_type, username, data):
        logger.error("Missing cache parameters.")
        return
    cache_dir = Path("cache") / cache_type
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_data = {
        "username": username,
        "books": data,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }
    with Path.open(cache_dir / f"{username}.json", "w", encoding="utf-8") as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=4)


def read_cache(cache_type: str, username: str) -> dict | None:
    """Read the cache for a given type and username."""
    if None in (cache_type, username):
        logger.error("No cache or no username specified.")
        return None
    cache_dir = Path("cache") / cache_type
    cache_file = cache_dir / f"{username}.json"
    if not cache_file.exists():
        logger.error("Cache file does not exist.")
        return None
    with Path.open(cache_file, "r", encoding="utf-8") as f:
        return json.load(f)


def records_to_df(
    records: list | dict[str, Any],
    link_base: str | None = None,
) -> pd.DataFrame:
    """Convert a list of book dicts into a normalized DataFrame.

    - Accepts either a list of dicts or a dict like {"success": True, "data": [...]}
    - Renames keys to snake_case column names
    - Keeps fields as strings unless strict parsing requested
    - Optionally prepends link_base to BookLink when it starts with '/'
    """
    if isinstance(records, dict):
        if isinstance(records.get("data"), list):
            records = records["data"]
        else:
            # Try to find the first list value in the dict
            for v in records.values():
                if isinstance(v, list):
                    records = v
                    break

    if not records:
        return pd.DataFrame()

    # Normalize JSON -> flat DataFrame
    ll_df = pd.json_normalize(records)

    # Column rename map
    rename_map = {
        "AuthorID": "author_id",
        "AuthorName": "author",
        "AuthorLink": "author_link",
        "BookName": "title",
        "BookSub": "subtitle",
        "BookGenre": "genre",
        "BookIsbn": "isbn",
        "BookPub": "publisher",
        "BookRate": "rating",
        "BookImg": "image",
        "BookPages": "pages",
        "BookLink": "link",
        "BookID": "book_id",
        "BookDate": "published_year",
        "BookLang": "language",
        "BookAdded": "added",
        "Status": "status",
        "AudioStatus": "audio_status",
        "BookLibrary": "book_library",
        "AudioLibrary": "audio_library",
    }
    ll_df = ll_df.rename(columns=rename_map)

    # Keep fields as strings; only normalize missing values to None and strip whitespace
    for _col in ("rating", "pages", "added", "published_year"):
        if _col in ll_df.columns:
            ll_df[_col] = ll_df[_col].apply(
                lambda x: None if pd.isna(x) else str(x).strip(),
            )

    # Optionally prepend base to relative links (e.g. "/works/...")
    if link_base and "link" in ll_df.columns:
        ll_df["link"] = ll_df["link"].apply(
            lambda x: f"{link_base}{x}"
            if isinstance(x, str) and x.startswith("/")
            else x,
        )

    # Pick / reorder relevant columns (keep only existing)
    preferred_order = [
        "book_id",
        "title",
        "subtitle",
        "author_id",
        "author",
        "author_name",
        "author_link",
        "isbn",
        "publisher",
        "rating",
        "pages",
        "published_year",
        "language",
        "added",
        "status",
        "audio_status",
        "book_library",
        "audio_library",
        "genre",
        "image",
        "link",
    ]
    cols = [c for c in preferred_order if c in ll_df.columns]
    return ll_df[cols]


def _strip_subtitles(title: str) -> str:
    """Remove subtitles from a book title string.

    E.g. "The Great Book: A Novel" -> "The Great Book"
    """
    if not isinstance(title, str):
        return title
    # Split on common subtitle separators
    for sep in [":", "-", "–", "|"]:  # noqa: RUF001
        if sep in title:
            return title.split(sep)[0].strip()
    return title.strip()


def storygraph_records_to_df(
    records: list | dict,
    link_base: str | None = None,
) -> pd.DataFrame:
    """Convert Storygraph `get_books` output into a normalized DataFrame.

    Accepts records like: [(link, title, author), ...] or a dict wrapper and returns
    columns: `id`, `link`, `title`, `author` (all strings).
    """
    # Unwrap dict wrappers (e.g. {"data": [...]})
    if isinstance(records, dict):
        if isinstance(records.get("data"), list):
            records = records["data"]
        else:
            for v in records.values():
                if isinstance(v, list):
                    records = v
                    break

    if not records:
        return pd.DataFrame()

    rows = []
    for item in records:
        if not item:
            continue
        # tuple/list format: (link, title, author)
        if isinstance(item, (list | tuple)):
            link = str(item[0]) if len(item) > 0 else None
            title = str(item[1]) if len(item) > 1 else None
            author = str(item[2]) if len(item) > 2 else None
        # dicts with keys
        elif isinstance(item, dict):
            link = (
                item.get("link")
                or item.get("url")
                or item.get("book_url")
                or item.get("BookLink")
            )
            title = item.get("title") or item.get("BookName")
            author = item.get("author") or item.get("AuthorName")
        else:
            # fallback to string
            s = str(item)
            link = None
            title = s
            author = None

        # derive id from final path segment of link when possible
        id_ = None
        if link:
            path = urlparse(link).path.rstrip("/")
            id_ = path.split("/")[-1] if path else None
            if isinstance(link, str) and link.startswith("/") and link_base:
                link = f"{link_base}{link}"

        rows.append(
            {
                "id": id_,
                "link": link,
                "title": title.strip() if isinstance(title, str) else title,
                "author": author.strip() if isinstance(author, str) else author,
            },
        )

    df_sg = pd.DataFrame(rows, columns=["id", "link", "title", "author"])
    df_sg["title"] = df_sg["title"].apply(lambda x: _strip_subtitles(x))

    # Keep values as strings
    for c in df_sg.columns:
        df_sg[c] = df_sg[c].apply(lambda x: None if pd.isna(x) else str(x).strip())

    return df_sg


def abs_items_to_df(records: list | dict[str, Any]) -> pd.DataFrame:
    """Convert Audiobookshelf library items into a normalized DataFrame.

    Accepts either a list of ABSLibraryItem objects/dicts or a dict wrapper like
    {"results": [...]} or {"items": [...]}.

    Returns columns:
      - library_id
      - library_item_id
      - title
      - author
      - subtitle
      - isbn
      - duration
      - added_at
      - updated_at
      - is_missing
      - is_invalid
      - path
      - tags
      - cover_path

    The function accepts either dict payloads or Pydantic model instances.
    """
    if isinstance(records, dict):
        if isinstance(records.get("results"), list):
            records = records["results"]
        elif isinstance(records.get("items"), list):
            records = records["items"]
        else:
            for v in records.values():
                if isinstance(v, list):
                    records = v
                    break

    if not records:
        return pd.DataFrame()

    rows = []
    for item in records:
        if not item:
            continue

        # Support both dicts and model instances
        def _get(o, *keys, default=None):
            if o is None:
                return default
            cur = o
            for k in keys:
                if cur is None:
                    return default
                if isinstance(cur, dict):
                    cur = cur.get(k)
                else:
                    cur = getattr(cur, k, None)
            return cur if cur is not None else default

        library_id = _get(item, "libraryId") or _get(item, "library_id")
        library_item_id = _get(item, "id") or _get(item, "libraryItemId")
        path = _get(item, "path")
        added_at = _get(item, "addedAt")
        updated_at = _get(item, "updatedAt")
        is_missing = _get(item, "isMissing")
        is_invalid = _get(item, "isInvalid")

        media = _get(item, "media")
        title = _get(media, "metadata", "title") or _get(media, "title")
        subtitle = _get(media, "metadata", "subtitle")
        isbn = _get(media, "metadata", "isbn")
        author = _get(media, "metadata", "authorName")
        if not author:
            authors = _get(media, "metadata", "authors")
            if authors and isinstance(authors, (list, tuple)):
                a0 = authors[0]
                author = _get(a0, "name") or (a0 if isinstance(a0, str) else None)

        duration = _get(media, "duration") or _get(media, "audioFiles", "duration")
        tags = _get(media, "tags") or _get(item, "tags")
        cover_path = _get(media, "coverPath") or _get(media, "cover_path")

        rows.append(
            {
                "library_id": library_id,
                "library_item_id": library_item_id,
                "title": title if title is not None else None,
                "author": author if author is not None else None,
                "subtitle": subtitle if subtitle is not None else None,
                "isbn": isbn if isbn is not None else None,
                "duration": duration if duration is not None else None,
                "added_at": added_at,
                "updated_at": updated_at,
                "is_missing": bool(is_missing) if is_missing is not None else None,
                "is_invalid": bool(is_invalid) if is_invalid is not None else None,
                "path": path,
                "tags": tags,
                "cover_path": cover_path,
            },
        )

    df = pd.DataFrame(rows)

    # Coerce columns to strings / normalize
    for c in [
        "library_id",
        "library_item_id",
        "title",
        "author",
        "subtitle",
        "isbn",
        "path",
        "cover_path",
    ]:
        if c in df.columns:
            df[c] = df[c].apply(lambda x: None if pd.isna(x) else str(x).strip())

    return df


def abs_items_to_minimal_df(
    records: list | dict[str, Any],
    library_name: str | None = None,
) -> pd.DataFrame:
    """Return a small DataFrame with only library, title, author from ABS items.

    - Accepts the output of AudioBookShelf.get_library_items (list of
      ABSLibraryItem models or dicts) or a dict wrapper with "results"/"items".
    - Optionally pass the library name so each row includes the originating
      library: `library` column. If not provided the function will try to
      read a library name from the item (if present) or fall back to
      library_id.
    """
    if isinstance(records, dict):
        if isinstance(records.get("results"), list):
            records = records["results"]
        elif isinstance(records.get("items"), list):
            records = records["items"]
        else:
            for v in records.values():
                if isinstance(v, list):
                    records = v
                    break

    if not records:
        return pd.DataFrame(columns=["library", "title", "author"])

    rows = []

    for item in records:
        if not item:
            continue

        # helper to pull nested attributes from dicts/models
        def _get(o, *keys, default=None):
            if o is None:
                return default
            cur = o
            for k in keys:
                if cur is None:
                    return default
                if isinstance(cur, dict):
                    cur = cur.get(k)
                else:
                    cur = getattr(cur, k, None)
            return cur if cur is not None else default

        # library name resolution: explicit param > item.libraryName > item.libraryId
        lib = (
            library_name
            or _get(item, "libraryName")
            or _get(item, "library_id")
            or _get(item, "libraryId")
        )

        media = _get(item, "media")
        title = _get(media, "metadata", "title") or _get(media, "title")
        author = _get(media, "metadata", "authorName")
        if not author:
            authors = _get(media, "metadata", "authors")
            if authors and isinstance(authors, (list, tuple)):
                a0 = authors[0]
                author = _get(a0, "name") or (a0 if isinstance(a0, str) else None)

        # Normalize title by stripping common subtitles to match app behavior
        title = _strip_subtitles(title) if isinstance(title, str) else title

        if title:
            rows.append(
                {
                    "library": lib,
                    "title": title.strip(),
                    "author": author.strip() if isinstance(author, str) else author,
                },
            )

    df = pd.DataFrame(rows, columns=["library", "title", "author"])
    # Normalize strings
    for c in ["library", "title", "author"]:
        if c in df.columns:
            df[c] = df[c].apply(lambda x: None if pd.isna(x) else str(x).strip())

    return df


def _unwrap_records(recs):
    """Unwrap common dict wrappers (results/items) returning a list or original input."""
    if isinstance(recs, dict):
        if isinstance(recs.get("results"), list):
            return recs["results"]
        if isinstance(recs.get("items"), list):
            return recs["items"]
        for v in recs.values():
            if isinstance(v, list):
                return v
    return recs


def _get_attr(o, *keys, default=None):
    """Robustly fetch nested attributes or dict keys; returns default when missing."""
    if o is None:
        return default
    cur = o
    for k in keys:
        if cur is None:
            return default
        if isinstance(cur, dict):
            cur = cur.get(k)
        else:
            cur = getattr(cur, k, None)
    return cur if cur is not None else default


def _parse_abs_item(item, library_name: str | None = None) -> dict:
    """Parse a single ABS record into a normalized dict with format flags."""
    lib = (
        library_name
        or _get_attr(item, "libraryName")
        or _get_attr(item, "library_id")
        or _get_attr(item, "libraryId")
    )
    media = _get_attr(item, "media")
    title = _get_attr(media, "metadata", "title") or _get_attr(media, "title")
    author = _get_attr(media, "metadata", "authorName")

    if not author:
        authors = _get_attr(media, "metadata", "authors")
        if authors and isinstance(authors, (list, tuple)):
            a0 = authors[0]
            author = _get_attr(a0, "name") or (a0 if isinstance(a0, str) else None)

    # Detect formats
    is_ebook = False
    is_audiobook = False
    if media:
        if (
            _get_attr(media, "ebookFile")
            or _get_attr(media, "ebookFormat")
            or _get_attr(media, "ebookFormat")
        ):
            is_ebook = True

        if (
            _get_attr(media, "audioFiles")
            or _get_attr(media, "numAudioFiles")
            or _get_attr(media, "numTracks")
        ):
            af = _get_attr(media, "audioFiles")
            if isinstance(af, (list, tuple)):
                is_audiobook = len(af) > 0
            else:
                is_audiobook = bool(
                    _get_attr(media, "numAudioFiles") or _get_attr(media, "numTracks"),
                )

    title = _strip_subtitles(title) if isinstance(title, str) else title

    parsed = {
        "library": lib,
        "title": title.strip() if isinstance(title, str) else title,
        "author": author.strip() if isinstance(author, str) else author,
        "is_ebook": bool(is_ebook),
        "is_audiobook": bool(is_audiobook),
    }
    return parsed


def _normalize_text(df: pd.DataFrame, columns: list[str]):
    """Normalize text columns: None for NaN, strip strings."""
    for c in columns:
        if c in df.columns:
            df[c] = df[c].apply(lambda x: None if pd.isna(x) else str(x).strip())


def _aggregate_libs(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate per-item DataFrame into the presence + library-list view."""
    # normalize empty library names
    df["library"] = df["library"].fillna("")

    ebook = df[df["is_ebook"]]
    ebook_libs = (
        ebook.groupby(["title", "author"])["library"]
        .apply(lambda s: ",".join(sorted({x for x in s if x})))
        .rename("abs_ebook_libraries")
    )

    audio = df[df["is_audiobook"]]
    audio_libs = (
        audio.groupby(["title", "author"])["library"]
        .apply(lambda s: ",".join(sorted({x for x in s if x})))
        .rename("abs_audiobook_libraries")
    )

    presence = (
        df.groupby(["title", "author"])[["is_ebook", "is_audiobook"]]
        .any()
        .rename(
            columns={"is_ebook": "abs_in_ebook", "is_audiobook": "abs_in_audiobook"}
        )
    )

    out = (
        presence.join(ebook_libs, how="left").join(audio_libs, how="left").reset_index()
    )

    for c in ["abs_ebook_libraries", "abs_audiobook_libraries"]:
        if c in out.columns:
            out[c] = out[c].fillna("")

    return out


def abs_items_aggregated_df(
    records: list | dict[str, Any],
    library_name: str | None = None,
    *,
    detailed: bool = False,
) -> pd.DataFrame:
    """Parse Audiobookshelf items and optionally return either a detailed
    DataFrame (one row per library item) or an aggregated DataFrame grouped by
    (title, author).

    This function is modularized into small helpers: parsing, normalization and
    aggregation. Behavior and return shapes remain unchanged.
    """
    records = _unwrap_records(records)

    # Empty early
    if not records:
        if detailed:
            return pd.DataFrame(
                columns=["library", "title", "author", "is_ebook", "is_audiobook"]
            )
        return pd.DataFrame(
            columns=[
                "title",
                "author",
                "abs_in_ebook",
                "abs_in_audiobook",
                "abs_ebook_libraries",
                "abs_audiobook_libraries",
            ]
        )

    parsed_rows = [
        _parse_abs_item(item, library_name=library_name) for item in records if item
    ]

    df = pd.DataFrame(
        parsed_rows, columns=["library", "title", "author", "is_ebook", "is_audiobook"]
    )

    _normalize_text(df, ["library", "title", "author"])

    # ensure boolean columns exist
    for c in ["is_ebook", "is_audiobook"]:
        if c in df.columns:
            df[c] = df[c].astype(bool)
        else:
            df[c] = False

    if detailed:
        return df

    return _aggregate_libs(df)
