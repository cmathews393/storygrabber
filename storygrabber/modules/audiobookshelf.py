"""Module and classes for ABS interaction."""

# ruff: noqa: N815 It's better to preserve the ABS capitalization for clarity.
from __future__ import annotations

import os
from typing import Any, Literal

import httpx
from loguru import logger
from pydantic import BaseModel, ConfigDict


class ABSBaseModel(BaseModel):
    """Configuration base model."""

    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow",
    )


class ABSFileMetadata(ABSBaseModel):
    """Metadata model for ABS files."""

    filename: str | None = None
    ext: str | None = None
    path: str | None = None
    relPath: str | None = None
    size: int | None = None
    mtimeMs: int | None = None
    ctimeMs: int | None = None
    birthtimeMs: int | None = None


class ABSLibraryFile(ABSBaseModel):
    """Library File model."""

    ino: str | None = None
    metadata: ABSFileMetadata | None = None
    addedAt: int | None = None
    updatedAt: int | None = None
    fileType: str | None = None


class ABSBookChapter(ABSBaseModel):
    """Chapter model for ABS books."""

    id: int | None = None
    start: float | None = None
    end: float | None = None
    title: str | None = None


class ABSAuthorMinified(ABSBaseModel):
    """Minified author model for ABS books."""

    id: str | None = None
    name: str | None = None


class ABSSeriesSequence(ABSBaseModel):
    """Series sequence model for ABS books."""

    id: str | None = None
    name: str | None = None
    sequence: str | None = None


class ABSBookMetadata(ABSBaseModel):
    """Metadata model for ABS books."""

    # Common
    title: str | None = None
    subtitle: str | None = None
    genres: list[str] | None = None
    publishedYear: str | None = None
    publishedDate: str | None = None
    publisher: str | None = None
    description: str | None = None
    isbn: str | None = None
    asin: str | None = None
    language: str | None = None
    explicit: bool | None = None

    # Minified additions
    titleIgnorePrefix: str | None = None
    authorName: str | None = None
    authorNameLF: str | None = None
    narratorName: str | None = None
    seriesName: str | None = None

    # Expanded additions
    authors: list[ABSAuthorMinified] | None = None
    narrators: list[str] | None = None
    series: list[ABSSeriesSequence] | None = None


class ABSAudioFile(ABSBaseModel):
    """File model for audiobooks."""

    index: int | None = None
    ino: str | None = None
    metadata: ABSFileMetadata | None = None

    addedAt: int | None = None
    updatedAt: int | None = None

    trackNumFromMeta: int | None = None
    discNumFromMeta: int | None = None
    trackNumFromFilename: int | None = None
    discNumFromFilename: int | None = None

    manuallyVerified: bool | None = None
    exclude: bool | None = None
    error: str | None = None

    format: str | None = None
    duration: float | None = None
    bitRate: int | None = None
    language: str | None = None
    codec: str | None = None
    timeBase: str | None = None
    channels: int | None = None
    channelLayout: str | None = None
    chapters: list[ABSBookChapter] | None = None
    embeddedCoverArt: str | None = None
    metaTags: dict[str, Any] | None = None
    mimeType: str | None = None


class ABSBook(ABSBaseModel):
    """Individual Book Model."""

    # Expanded/common
    libraryItemId: str | None = None
    metadata: ABSBookMetadata | None = None
    coverPath: str | None = None
    tags: list[str] | None = None
    audioFiles: list[ABSAudioFile] | None = None
    chapters: list[ABSBookChapter] | None = None
    ebookFile: dict[str, Any] | None = None

    # Minified additions
    numTracks: int | None = None
    numAudioFiles: int | None = None
    numChapters: int | None = None
    duration: float | None = None
    size: int | None = None
    ebookFormat: str | None = None

    # Expanded additions
    tracks: list[dict[str, Any]] | None = None


class ABSLibraryItem(ABSBaseModel):
    """Library Item model."""

    id: str | None = None
    ino: str | None = None

    libraryId: str | None = None
    folderId: str | None = None

    path: str | None = None
    relPath: str | None = None

    isFile: bool | None = None

    mtimeMs: int | None = None
    ctimeMs: int | None = None
    birthtimeMs: int | None = None

    addedAt: int | None = None
    updatedAt: int | None = None

    lastScan: int | None = None
    scanVersion: str | None = None

    isMissing: bool | None = None
    isInvalid: bool | None = None

    mediaType: Literal["book", "podcast"] | str | None = None  # noqa: PYI051

    # For our current use cases we're primarily concerned with books.
    media: ABSBook | dict[str, Any] | None = None

    # Present on expanded, absent on minified
    libraryFiles: list[ABSLibraryFile] | None = None

    # Minified/expanded extras
    numFiles: int | None = None
    size: int | None = None


class ABSGetLibraryItemsResponse(ABSBaseModel):
    """Response model for Get a Library's Items endpoint."""

    results: list[ABSLibraryItem] | None = None
    total: int | None = None
    limit: int | None = None
    page: int | None = None

    # Some endpoints use `items` instead; keep both.
    items: list[ABSLibraryItem] | None = None

    # a catch-all so we can still access the raw payload for unknown props
    raw: dict[str, Any] | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> ABSGetLibraryItemsResponse:
        """Create an instance from a raw payload."""
        return cls(
            results=payload.get("results"),
            items=payload.get("items"),
            total=payload.get("total"),
            limit=payload.get("limit"),
            page=payload.get("page"),
            raw=payload,
        )


class ABSLibrary(BaseModel):
    """Audiobookshelf library model."""

    id: str
    name: str
    folders: list
    displayOrder: int
    icon: str
    # Audiobookshelf uses camelCase already; keep it as-is.
    mediaType: str
    provider: str
    settings: dict
    createdAt: int
    lastUpdate: int

    model_config = {
        "populate_by_name": True,
        "extra": "allow",
    }


class AudioBookShelf:
    """ABS interaction class."""

    def __init__(self: AudioBookShelf) -> None:
        """Setup reusable client."""
        self.base_url = os.getenv("ABS_URL")
        self.key = os.getenv("ABS_KEY")
        self.client = httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.key}"},
        )

    def get_libraries(self: AudioBookShelf) -> list[ABSLibrary]:
        """Fetch libraries from Audiobookshelf.

        Audiobookshelf returns a JSON object with a top-level `libraries` key.
        Use a transient AsyncClient per call to avoid holding a client bound to a
        possibly closed event loop when called from synchronous code via
        `asyncio.run()` multiple times.
        """
        response = self.client.get("/api/libraries")
        response.raise_for_status()
        payload = response.json()
        raw_libraries = (
            payload.get("libraries", []) if isinstance(payload, dict) else []
        )
        logger.error(raw_libraries)
        return [ABSLibrary.model_validate(item) for item in raw_libraries]

    def get_library_items(
        self: AudioBookShelf,
        library_id: str,
    ) -> list[ABSLibraryItem]:
        """Get all items in a library and validate objects."""
        logger.error("Getting items for a library.")
        response = self.client.get(f"/api/libraries/{library_id}/items")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            return []

        # According to docs, this endpoint returns `results`.
        raw_items = payload.get("results") or payload.get("items") or []
        return [ABSLibraryItem.model_validate(item) for item in raw_items]
