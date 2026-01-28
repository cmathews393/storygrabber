(function () {
  const form = document.getElementById("get-books-form");
  const input = document.getElementById("username-input");
  const btn = document.getElementById("get-books-btn");
  const results = document.getElementById("get-books-results");
  const updated = document.getElementById("get-books-updated");
  const refreshBtn = document.getElementById("refresh-books-btn");

  function formatItem(item) {
    let title = "";
    let author = "";
    let link = null;

    if (Array.isArray(item) || Array.isArray(item)) {
      // (link, title, author)
      link = item[0] || null;
      title = item[1] || "(no title)";
      author = item[2] || "";
    } else if (item && typeof item === "object") {
      // StoryGraph dict or LazyLibrarian-like object
      title = item.title || item.BookName || "(no title)";
      author = item.author || item.AuthorName || "";
      link = item.link || item.url || item.BookLink || null;
    } else {
      title = String(item);
      author = "";
    }

    const wrapper = document.createElement("div");
    wrapper.className = "py-2 border-b border-gray-700";

    const titleEl = document.createElement("div");
    titleEl.className = "font-medium text-gray-100";
    if (link) {
      const a = document.createElement("a");
      a.href = link;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.textContent = title;
      a.className = "text-sg-accent hover:underline";
      titleEl.appendChild(a);
    } else {
      titleEl.textContent = title;
    }

    const authorEl = document.createElement("div");
    authorEl.className = "text-sm text-gray-400";
    authorEl.textContent = author;

    wrapper.appendChild(titleEl);
    wrapper.appendChild(authorEl);
    return wrapper;
  }

  function showLoading(isLoading) {
    btn.disabled = isLoading;
    btn.textContent = isLoading ? "Loading…" : "Get books";
  }

  async function fetchBooks(username, noCache = false) {
    const url = `/api/get_storygraph_list/${encodeURIComponent(username)}?no_cache=${noCache}`;
    const res = await fetch(url, { method: "GET" });
    if (!res.ok) {
      throw new Error(`Request failed: ${res.status}`);
    }
    return res.json();
  }

  function renderBooksList(items) {
    results.innerHTML = "";
    if (!items || items.length === 0) {
      results.textContent = "No books found.";
      return;
    }

    const container = document.createElement("div");
    container.className = "space-y-1";
    items.forEach((it) => container.appendChild(formatItem(it)));
    results.appendChild(container);
  }

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const username = input.value && input.value.trim();
    if (!username) {
      results.textContent = "Please enter a username.";
      return;
    }

    try {
      showLoading(true);
      const items = await fetchBooks(username, false);
      renderBooksList(items);
      updated.textContent = `Fetched at ${new Date().toLocaleString()}`;
      refreshBtn.classList.remove("hidden");
    } catch (err) {
      results.textContent = `Error: ${err.message}`;
    } finally {
      showLoading(false);
    }
  });

  refreshBtn.addEventListener("click", async () => {
    const username = input.value && input.value.trim();
    if (!username) {
      results.textContent = "Please enter a username.";
      return;
    }

    try {
      showLoading(true);
      const items = await fetchBooks(username, true);
      renderBooksList(items);
      updated.textContent = `Refreshed at ${new Date().toLocaleString()}`;
    } catch (err) {
      results.textContent = `Error: ${err.message}`;
    } finally {
      showLoading(false);
    }
  });
})();
