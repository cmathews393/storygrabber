import storygrab.modules.storygraph as sg_mod
from storygrab import create_app


class DummySG:
    def __init__(self, username):
        self.username = username

    def get_books(self):
        return [("/books/1", "Cached Book", "Cached Author")]


def test_get_books_caching(monkeypatch, tmp_path):
    # Patch StoryGrabber
    monkeypatch.setattr(sg_mod, "StoryGrabber", DummySG)

    app = create_app({"TESTING": True})
    client = app.test_client()

    # Ensure cache is written to tmp_path during the test
    import storygrab.backend as backend_mod

    def _tmp_cache_dir():
        d = tmp_path / "cache"
        d.mkdir(exist_ok=True)
        return d

    monkeypatch.setattr(backend_mod, "_cache_dir", _tmp_cache_dir)

    # First request should produce a fresh cached response
    resp1 = client.get("/api/get_books/testuser")
    assert resp1.status_code == 200
    body1 = resp1.get_json()
    assert body1.get("cached") is False
    assert "books" in body1 and len(body1["books"]) == 1

    # Second request should return cached=True
    resp2 = client.get("/api/get_books/testuser")
    assert resp2.status_code == 200
    body2 = resp2.get_json()
    assert body2.get("cached") is True
    assert "fetched_at" in body2

    # Force refresh
    resp3 = client.get("/api/get_books/testuser?refresh=1")
    assert resp3.status_code == 200
    body3 = resp3.get_json()
    assert body3.get("cached") is False
    assert "fetched_at" in body3
    # fetched_at should be a fresh timestamp (or at least present)
    assert body3["fetched_at"] != body2.get("fetched_at")
