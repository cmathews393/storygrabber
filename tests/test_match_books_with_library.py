import json
import storygrab.modules.storygraph as sg_mod
import storygrab.modules.lazylibrarian as ll_mod
import storygrab.backend as backend_mod
from storygrab import create_app


class DummySG:
    def __init__(self, username):
        self.username = username

    def get_books(self):
        return [("/books/ff94854a", "Waif", "Samantha Kolesnik")]


class DummyLL:
    def __init__(self, host, port, api_key, use_https=False):
        pass

    def get_all_books(self):
        return [
            {
                "AuthorID": "OL9155324A",
                "AuthorName": "Samantha Kolesnik",
                "BookName": "Waif",
                "BookID": "OL27280527W",
                "BookLibrary": None,
                "AudioLibrary": None,
                "Status": "Wanted",
                "AudioStatus": "Wanted",
            }
        ]


def test_match_books_uses_library(monkeypatch):
    monkeypatch.setenv("LL_API_KEY", "fake")
    monkeypatch.setattr(sg_mod, "StoryGrabber", DummySG)
    monkeypatch.setattr(ll_mod, "LazyLibrarianClient", DummyLL)
    monkeypatch.setattr(backend_mod, "LazyLibrarianClient", DummyLL)

    app = create_app({"TESTING": True})
    client = app.test_client()

    resp = client.post(
        "/api/match_books",
        data=json.dumps(
            {"username": "dummy", "types": ["eBook", "AudioBook"], "max_books": 5}
        ),
        content_type="application/json",
    )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body.get("success") is True
    assert body.get("total_checked") == 1
    r = body["results"][0]
    # Should have library_matches
    assert "library_matches" in r
    # eBook and AudioBook should be False because BookLibrary and AudioLibrary are None
    assert r["matches"]["eBook"]["matched"] is False
    assert r["matches"]["AudioBook"]["matched"] is False
