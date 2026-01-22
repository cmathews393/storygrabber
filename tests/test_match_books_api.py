import json

import storygrab.modules.storygraph as sg_mod
import storygrab.modules.lazylibrarian as ll_mod
from storygrab import create_app


class DummySG:
    def __init__(self, username):
        self.username = username

    def get_books(self):
        # Return a single sample book
        return [("/books/1", "My Sample Book", "Sample Author")]


class DummyLL:
    def __init__(self, host, port, api_key, use_https=False):
        pass

    def find_book(self, title):
        # Pretend we found a book and return an object with an id
        return [{"bookid": "1234", "title": title}]

    def search_book(self, book_id, book_type="eBook", wait=False):
        # eBook available, AudioBook not
        if book_type == "eBook":
            return {"success": True}
        return {"success": False}


def test_match_books_endpoint(monkeypatch):
    # Ensure LL env vars are set so endpoint doesn't reject early
    monkeypatch.setenv("LL_API_KEY", "fake-api-key")
    monkeypatch.setenv("LL_HOST", "localhost")
    monkeypatch.setenv("LL_PORT", "5299")

    # Patch StoryGrabber and LazyLibrarian
    monkeypatch.setattr(sg_mod, "StoryGrabber", DummySG)
    monkeypatch.setattr(ll_mod, "LazyLibrarianClient", DummyLL)

    # Also patch the LazyLibrarianClient used directly by the backend module
    import storygrab.backend as backend_mod

    monkeypatch.setattr(backend_mod, "LazyLibrarianClient", DummyLL)

    app = create_app({"TESTING": True})
    client = app.test_client()

    resp = client.post(
        "/api/match_books",
        data=json.dumps(
            {"username": "dummy", "types": ["eBook", "AudioBook"], "max_books": 1}
        ),
        content_type="application/json",
    )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body.get("success") is True
    assert body.get("total_checked") == 1
    results = body.get("results")
    assert isinstance(results, list) and len(results) == 1
    r = results[0]
    assert r["title"] == "My Sample Book"
    # Remote search is not performed automatically; match flags indicate local library availability
    assert r["matches"]["eBook"]["matched"] is False
    assert r["matches"]["AudioBook"]["matched"] is False
    assert r.get("search_possible") is True
