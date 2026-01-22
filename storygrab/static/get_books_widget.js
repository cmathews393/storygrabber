(function () {
  function escapeHtml(str) {
    if (typeof str !== "string") return str;
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("get-books-form");
    if (!form) return;

    const input = document.getElementById("username-input");
    const btn = document.getElementById("get-books-btn");
    const results = document.getElementById("get-books-results");
    const meta = document.getElementById("get-books-meta");
    const updated = document.getElementById("get-books-updated");
    const refreshBtn = document.getElementById("refresh-books-btn");

    function timeSince(date) {
      const seconds = Math.floor((new Date() - date) / 1000);
      if (seconds < 60) return `${seconds}s ago`;
      const minutes = Math.floor(seconds / 60);
      if (minutes < 60) return `${minutes}m ago`;
      const hours = Math.floor(minutes / 60);
      if (hours < 24) return `${hours}h ago`;
      const days = Math.floor(hours / 24);
      return `${days}d ago`;
    }

    function renderList(data) {
      const books = data || [];
      if (!books.length) {
        results.innerHTML =
          '<div class="bg-blue-600 text-white p-3 rounded-md">No books found for that user.</div>';
        updated.innerHTML = "";
        refreshBtn.classList.add("hidden");
        return;
      }

      const list = document.createElement("ul");
      list.className = "divide-y divide-gray-700 mt-2";

      books.forEach((b) => {
        const li = document.createElement("li");
        li.className = "py-3";

        if (Array.isArray(b)) {
          const [url, title, author] = b;
          li.innerHTML = `<div class=\"flex items-start justify-between\"><div><strong class=\"text-white\">${escapeHtml(title)}</strong><div class=\"text-sm text-gray-400\">${escapeHtml(author)}</div></div>${url ? `<a class=\"ml-4 text-sg-accent hover:underline\" href=\"${escapeHtml(url)}\" target=\"_blank\" rel=\"noopener\">view</a>` : ""}</div>`;
        } else if (b && typeof b === "object") {
          const title = b.title || b[1] || "";
          const author = b.author || b[2] || "";
          const url = b.url || b[0] || "";
          li.innerHTML = `<div class=\"flex items-start justify-between\"><div><strong class=\"text-white\">${escapeHtml(title)}</strong><div class=\"text-sm text-gray-400\">${escapeHtml(author)}</div></div>${url ? `<a class=\"ml-4 text-sg-accent hover:underline\" href=\"${escapeHtml(url)}\" target=\"_blank\" rel=\"noopener\">view</a>` : ""}</div>`;
        } else {
          li.textContent = String(b);
        }

        list.appendChild(li);
      });

      results.innerHTML = "";
      results.appendChild(list);
    }

    async function fetchBooks(username, force = false) {
      results.innerHTML =
        '<div class="flex items-center text-gray-300"><svg class="animate-spin -ml-1 mr-3 h-5 w-5 text-sg-accent" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"></path></svg>Fetching books...</div>';

      let url = `/api/get_books/${encodeURIComponent(username)}`;
      if (force) url += "?refresh=1";

      try {
        const res = await fetch(url);
        if (!res.ok) {
          const errText = await res.text();
          results.innerHTML = `<div class="bg-red-600 text-white p-3 rounded-md">Error ${res.status}: ${escapeHtml(errText)}</div>`;
          updated.innerHTML = "";
          refreshBtn.classList.add("hidden");
          return;
        }

        const data = await res.json();
        // Support both legacy array response and new structured cache response
        if (Array.isArray(data)) {
          renderList(data);
          updated.innerHTML = "";
          refreshBtn.classList.remove("hidden");
          refreshBtn.onclick = () => fetchBooks(username, true);
        } else if (data && data.books) {
          renderList(data.books || []);
          updated.innerHTML = data.fetched_at
            ? `Last updated: ${timeSince(new Date(data.fetched_at))}`
            : "";
          refreshBtn.classList.remove("hidden");
          refreshBtn.onclick = () => fetchBooks(username, true);
        } else {
          renderList([]);
          updated.innerHTML = "";
          refreshBtn.classList.add("hidden");
        }
      } catch (err) {
        results.innerHTML = `<div class="bg-red-600 text-white p-3 rounded-md">${escapeHtml(err && err.message ? err.message : String(err))}</div>`;
        updated.innerHTML = "";
        refreshBtn.classList.add("hidden");
      } finally {
        btn.disabled = false;
      }
    }

    refreshBtn?.addEventListener("click", function (e) {
      const username = ((input && input.value) || "").trim();
      if (username) fetchBooks(username, true);
    });

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      const username = ((input && input.value) || "").trim();
      if (!username) {
        results.innerHTML =
          '<div class="bg-yellow-500 text-black p-3 rounded-md">Please enter a username.</div>';
        return;
      }
      btn.disabled = true;
      fetchBooks(username, false);
    });
  });
})();
