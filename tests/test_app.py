def test_create_app_works():
    from storygrab import create_app

    app = create_app({"TESTING": True})
    assert app is not None
    assert app.testing


def test_health_route():
    from storygrab import create_app

    app = create_app({"TESTING": True})
    client = app.test_client()
    rv = client.get("/health")
    assert rv.status_code == 200
    assert rv.is_json
    assert rv.get_json() == {"status": "healthy"}


def test_pages_render_and_nav_links():
    from storygrab import create_app

    app = create_app({"TESTING": True})
    client = app.test_client()

    checks = [
        ("/", b"Welcome to StoryGrab"),
        ("/dashboard", b"Dashboard"),
        ("/settings", b"Settings"),
    ]

    for path, expected in checks:
        rv = client.get(path)
        assert rv.status_code == 200
        assert expected in rv.data

    # Check nav links are present on the home page
    rv = client.get("/")
    assert b'href="/' in rv.data
    assert b'href="/dashboard"' in rv.data
    assert b'href="/settings"' in rv.data


def test_widget_and_static_served():
    from storygrab import create_app

    app = create_app({"TESTING": True})
    client = app.test_client()

    rv = client.get("/")
    assert rv.status_code == 200
    assert b'id="get-books-form"' in rv.data

    js = client.get("/static/get_books_widget.js")
    assert js.status_code == 200
    assert b"escapeHtml" in js.data or b"get-books-form" in js.data


def test_match_widget_and_static_served():
    from storygrab import create_app

    app = create_app({"TESTING": True})
    client = app.test_client()

    rv = client.get("/dashboard")
    assert rv.status_code == 200
    assert b'id="match-books-form"' in rv.data

    js = client.get("/static/match_books_widget.js")
    assert js.status_code == 200
    assert b"Search LL" in js.data
