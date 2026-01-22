import json
import storygrab.modules.lazylibrarian as ll_mod
import storygrab.backend as backend_mod
from storygrab import create_app


class DummyLL:
    def __init__(self, host, port, api_key, use_https=False):
        pass

    def find_book(self, title):
        return [{"bookid": "123", "title": title}]

    def add_book(self, book_id):
        return {"success": True, "book_id": book_id}

    def queue_book(self, book_id, book_type="eBook"):
        return {"success": True, "book_id": book_id, "type": book_type}


def test_find_and_add_queue_ll(monkeypatch):
    monkeypatch.setenv("LL_API_KEY", "fake")
    monkeypatch.setattr(ll_mod, "LazyLibrarianClient", DummyLL)
    monkeypatch.setattr(backend_mod, "LazyLibrarianClient", DummyLL)

    app = create_app({"TESTING": True})
    client = app.test_client()

    r = client.post(
        "/api/find_books_ll",
        data=json.dumps({"title": "Waif"}),
        content_type="application/json",
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body.get("success") is True
    assert isinstance(body.get("results"), list)

    r2 = client.post(
        "/api/add_book_ll",
        data=json.dumps({"book_id": "123"}),
        content_type="application/json",
    )
    assert r2.status_code == 200
    b2 = r2.get_json()
    assert b2.get("success") is True

    r3 = client.post(
        "/api/queue_book_ll",
        data=json.dumps({"book_id": "123", "book_type": "AudioBook"}),
        content_type="application/json",
    )
    assert r3.status_code == 200
    b3 = r3.get_json()
    assert b3.get("success") is True


def test_remote_find_ll(monkeypatch):
    monkeypatch.setenv("LL_API_KEY", "fake")
    monkeypatch.setattr(ll_mod, "LazyLibrarianClient", DummyLL)
    monkeypatch.setattr(backend_mod, "LazyLibrarianClient", DummyLL)

    app = create_app({"TESTING": True})
    client = app.test_client()

    r = client.post(
        "/api/find_books_ll",
        data=json.dumps({"title": "Waif", "remote": True}),
        content_type="application/json",
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body.get("success") is True
    assert body.get("source") == "remote"
    assert isinstance(body.get("results"), list)
