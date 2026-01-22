(function () {
  function escapeHtml(str) {
    if (typeof str !== "string") return String(str);
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("match-books-form");
    if (!form) return;

    const usernameInput = document.getElementById("match-username");
    const ebookCheckbox = document.getElementById("type-ebook");
    const audioCheckbox = document.getElementById("type-audio");
    const btn = document.getElementById("match-books-btn");
    const results = document.getElementById("match-books-results");
    const matchRefreshCheckbox = document.getElementById("match-refresh");
    const meta = document.getElementById("match-books-meta");

    function normalize(s) {
      if (!s) return "";
      return s
        .toString()
        .toLowerCase()
        .replace(/[^a-z0-9 ]+/g, " ")
        .split(/\s+/)
        .filter(Boolean)
        .join(" ");
    }

    function renderInitialTable(sgList, types) {
      const table = document.createElement("table");
      table.className = "min-w-full divide-y divide-gray-700";

      const thead = document.createElement("thead");
      thead.className = "bg-gray-800";
      const headerRow = document.createElement("tr");
      headerRow.innerHTML =
        '<th class="px-2 py-2 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">In LL</th><th class="px-3 py-2 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Title</th><th class="px-3 py-2 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Author</th>' +
        types
          .map(
            (t) =>
              `<th class="px-3 py-2 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">${escapeHtml(t)}</th>`,
          )
          .join("") +
        '<th class="px-3 py-2 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Actions</th>';
      thead.appendChild(headerRow);
      table.appendChild(thead);

      const tbody = document.createElement("tbody");
      tbody.className = "bg-transparent divide-y divide-gray-700";

      sgList.forEach((b) => {
        const tr = document.createElement("tr");
        tr.className = "hover:bg-gray-900";

        const [url, title, author] = Array.isArray(b)
          ? b
          : [
              b.url || b[0] || "",
              b.title || b.BookName || b[1] || "",
              b.author || b.AuthorName || b[2] || "",
            ];

        const key = normalize(title) + "|" + normalize(author);
        tr.dataset.key = key;

        const tdInLL = document.createElement("td");
        tdInLL.className = "px-2 py-3 text-sm";
        tdInLL.innerHTML = '<span class="text-muted">—</span>';
        tr.appendChild(tdInLL);

        const tdTitle = document.createElement("td");
        tdTitle.className = "px-3 py-3 text-sm";
        tdTitle.innerHTML = `${escapeHtml(title)} ${url ? `<a class=\"ml-2 text-sg-accent hover:underline\" href=\"${escapeHtml(url)}\" target=\"_blank\">(sg)</a>` : ""}`;
        tr.appendChild(tdTitle);

        const tdAuthor = document.createElement("td");
        tdAuthor.className = "px-3 py-3 text-sm text-gray-300";
        tdAuthor.innerText = author || "";
        tr.appendChild(tdAuthor);

        types.forEach((t) => {
          const td = document.createElement("td");
          td.className = "px-3 py-3 text-sm";
          td.innerHTML = `<span class=\"text-muted\">Missing</span>`;
          tr.appendChild(td);
        });

        const tdActions = document.createElement("td");
        tdActions.className = "px-3 py-3 text-sm";
        const searchBtn = document.createElement("button");
        searchBtn.className =
          "inline-flex items-center px-3 py-1 bg-gray-700 text-gray-200 rounded-md hover:bg-gray-600";
        searchBtn.innerText = "Search LL";
        searchBtn.dataset.title = title || "";
        searchBtn.dataset.author = author || "";
        tdActions.appendChild(searchBtn);
        const resultBox = document.createElement("div");
        resultBox.className = "mt-2 text-sm text-gray-300";
        tdActions.appendChild(resultBox);

        // attach handler
        searchBtn.addEventListener("click", async function (ev) {
          ev.preventDefault();
          resultBox.innerHTML =
            '<div class="flex items-center text-gray-300"><svg class="animate-spin -ml-1 mr-3 h-4 w-4 text-sg-accent" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"></path></svg>Searching...</div>';

          const renderCandidates = (resultsList, sourceLabel) => {
            resultBox.innerHTML = "";
            if (sourceLabel) {
              const src = document.createElement("div");
              src.className = "text-xs text-gray-500 mb-1";
              src.innerText = `Source: ${sourceLabel}`;
              resultBox.appendChild(src);
            }
            resultsList.forEach((c) => {
              const row = document.createElement("div");
              row.className = "flex items-center justify-between gap-2 py-1";
              const info = document.createElement("div");
              info.innerHTML = `<div class=\"text-white\">${escapeHtml(c.title || c.BookName || JSON.stringify(c))}</div><div class=\"text-gray-400 text-xs\">id: ${escapeHtml(c.bookid || c.BookID || "")}</div>`;
              row.appendChild(info);
              const actions = document.createElement("div");
              actions.className = "flex gap-2";
              const addBtn = document.createElement("button");
              addBtn.className =
                "px-2 py-1 bg-sg-accent text-white rounded-md text-xs";
              addBtn.innerText = "Add";
              addBtn.addEventListener("click", async () => {
                actions.innerHTML =
                  '<span class="text-gray-400">Processing...</span>';
                try {
                  const r = await fetch("/api/add_book_ll", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                      book_id: c.bookid || c.BookID || c.id,
                    }),
                  });
                  const jr = await r.json();
                  if (!r.ok)
                    actions.innerHTML = `<div class=\"text-red-500\">Error adding</div>`;
                  else
                    actions.innerHTML = `<div class=\"text-green-400\">Added</div>`;
                } catch (err) {
                  actions.innerHTML = `<div class=\"text-red-500\">${escapeHtml(err.message || String(err))}</div>`;
                }
              });
              const queueE = document.createElement("button");
              queueE.className =
                "px-2 py-1 bg-gray-700 text-gray-200 rounded-md text-xs";
              queueE.innerText = "Queue eBook";
              queueE.addEventListener("click", async () => {
                actions.innerHTML =
                  '<span class="text-gray-400">Processing...</span>';
                try {
                  const r = await fetch("/api/queue_book_ll", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                      book_id: c.bookid || c.BookID || c.id,
                      book_type: "eBook",
                    }),
                  });
                  const jr = await r.json();
                  if (!r.ok)
                    actions.innerHTML = `<div class=\"text-red-500\">Error</div>`;
                  else
                    actions.innerHTML = `<div class=\"text-green-400\">Queued</div>`;
                } catch (err) {
                  actions.innerHTML = `<div class=\"text-red-500\">${escapeHtml(err.message || String(err))}</div>`;
                }
              });
              const queueA = document.createElement("button");
              queueA.className =
                "px-2 py-1 bg-gray-700 text-gray-200 rounded-md text-xs";
              queueA.innerText = "Queue Audio";
              queueA.addEventListener("click", async () => {
                actions.innerHTML =
                  '<span class="text-gray-400">Processing...</span>';
                try {
                  const r = await fetch("/api/queue_book_ll", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                      book_id: c.bookid || c.BookID || c.id,
                      book_type: "AudioBook",
                    }),
                  });
                  const jr = await r.json();
                  if (!r.ok)
                    actions.innerHTML = `<div class=\"text-red-500\">Error</div>`;
                  else
                    actions.innerHTML = `<div class=\"text-green-400\">Queued</div>`;
                } catch (err) {
                  actions.innerHTML = `<div class=\"text-red-500\">${escapeHtml(err.message || String(err))}</div>`;
                }
              });
              actions.appendChild(addBtn);
              actions.appendChild(queueE);
              actions.appendChild(queueA);
              row.appendChild(actions);
              resultBox.appendChild(row);
            });
          };

          try {
            const res = await fetch("/api/find_books_ll", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                title: searchBtn.dataset.title,
                author: searchBtn.dataset.author,
              }),
            });
            const j = await res.json();
            if (!res.ok) {
              resultBox.innerHTML = `<div class="bg-red-600 text-white p-2 rounded-md">Error: ${escapeHtml(JSON.stringify(j))}</div>`;
              return;
            }
            const resultsList = j.results || j;
            if (!resultsList || resultsList.length === 0) {
              resultBox.innerHTML =
                "<div class='text-gray-400'>No candidates found.</div>";

              // Offer an explicit remote search against LazyLibrarian if local candidates weren't found
              const remoteBtn = document.createElement("button");
              remoteBtn.className =
                "ml-2 px-2 py-1 bg-gray-700 text-gray-200 rounded-md text-xs";
              remoteBtn.innerText = "Search remote LL";
              remoteBtn.addEventListener("click", async (e2) => {
                e2.preventDefault();
                remoteBtn.disabled = true;
                remoteBtn.innerText = "Searching remote...";
                try {
                  const rr = await fetch("/api/find_books_ll", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                      title: searchBtn.dataset.title,
                      author: searchBtn.dataset.author,
                      remote: true,
                    }),
                  });
                  const jr = await rr.json();
                  if (!rr.ok) {
                    resultBox.innerHTML = `<div class="bg-red-600 text-white p-2 rounded-md">Error: ${escapeHtml(JSON.stringify(jr))}</div>`;
                    return;
                  }
                  const remoteList = jr.results || jr;
                  if (!remoteList || remoteList.length === 0) {
                    resultBox.innerHTML =
                      "<div class='text-gray-400'>No remote candidates found.</div>";
                    return;
                  }
                  renderCandidates(remoteList, jr.source || "remote");
                } catch (err) {
                  resultBox.innerHTML = `<div class="bg-red-600 text-white p-2 rounded-md">${escapeHtml(err && err.message ? err.message : String(err))}</div>`;
                }
              });
              resultBox.appendChild(remoteBtn);
              return;
            }
            resultBox.innerHTML = "";
            renderCandidates(resultsList, j.source || "local");
          } catch (err) {
            resultBox.innerHTML = `<div class="bg-red-600 text-white p-2 rounded-md">${escapeHtml(err && err.message ? err.message : String(err))}</div>`;
          }
        });
        tr.appendChild(tdActions);
        tbody.appendChild(tr);
      });

      table.appendChild(tbody);
      results.innerHTML = "";
      results.appendChild(table);
    }

    async function applyMatchesToTable(matches, types) {
      if (!matches || !matches.length) return;
      matches.forEach((r) => {
        const key = normalize(r.title) + "|" + normalize(r.author || "");
        const row = document.querySelector(`tr[data-key="${key}"]`);
        if (!row) return;
        // Update In LL cell (first cell)
        const inLLCell = row.children[0];
        const anyInLL =
          r.library_matches &&
          r.library_matches.some((it) => it.BookLibrary || it.AudioLibrary);
        inLLCell.innerHTML = anyInLL
          ? '<span class="text-green-400">✔</span>'
          : '<span class="text-muted">—</span>';

        // Update type cells
        types.forEach((t, idx) => {
          const td = row.children[3 + idx]; // InLL(0), Title(1), Author(2), types start at 3
          const mt = r.matches && r.matches[t] ? r.matches[t] : null;
          let statusText = "Missing";
          let statusClass = "text-muted";
          if (mt) {
            if (mt.matched) {
              statusText = mt.status || "In Library";
              statusClass = "text-green-400 font-semibold";
            } else {
              statusText = mt.status || "Missing";
              if (/want/i.test(statusText)) statusClass = "text-yellow-400";
              else statusClass = "text-muted";
            }
          } else if (r.search_possible) {
            statusText = "Unknown";
            statusClass = "text-gray-300";
          }
          td.innerHTML = `<span class=\"${statusClass}\">${escapeHtml(statusText)}</span>`;
        });

        // If the item was matched by library, remove Search button
        if (r.library_matches && r.library_matches.length) {
          const actionsCell = row.children[row.children.length - 1];
          actionsCell.innerHTML = "";

          // Use the first matched item for quick actions
          const primary = r.library_matches[0];

          // eBook: offer Mark Wanted if status indicates skipped/missing
          const ebookMatch = r.matches && r.matches["eBook"];
          if (
            (ebookMatch && /skip/i.test(ebookMatch.status || "")) ||
            (ebookMatch && ebookMatch.status === "Missing")
          ) {
            const markE = document.createElement("button");
            markE.className =
              "px-2 py-1 bg-sg-accent text-white rounded-md text-xs mr-2";
            markE.innerText = "Mark Wanted (eBook)";
            markE.addEventListener("click", async () => {
              actionsCell.innerHTML =
                '<span class="text-gray-400">Processing...</span>';
              try {
                const r = await fetch("/api/queue_book_ll", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({
                    book_id: primary.BookID,
                    book_type: "eBook",
                  }),
                });
                const jr = await r.json();
                if (!r.ok)
                  actionsCell.innerHTML = `<div class=\"text-red-500\">Error</div>`;
                else {
                  actionsCell.innerHTML = `<div class=\"text-green-400\">Marked Wanted (eBook)</div>`;
                  // update the eBook cell in the row to reflect 'Wanted'
                  const eCell = row.children[3];
                  if (eCell)
                    eCell.innerHTML =
                      '<span class="text-yellow-400">Wanted</span>';
                }
              } catch (err) {
                actionsCell.innerHTML = `<div class=\"text-red-500\">${escapeHtml(err.message || String(err))}</div>`;
              }
            });
            actionsCell.appendChild(markE);
          }

          // Audio: offer Mark Wanted if status indicates skipped/missing
          const audioMatch = r.matches && r.matches["AudioBook"];
          if (
            (audioMatch && /skip/i.test(audioMatch.status || "")) ||
            (audioMatch && audioMatch.status === "Missing")
          ) {
            const markA = document.createElement("button");
            markA.className =
              "px-2 py-1 bg-sg-accent text-white rounded-md text-xs";
            markA.innerText = "Mark Wanted (Audio)";
            markA.addEventListener("click", async () => {
              actionsCell.innerHTML =
                '<span class="text-gray-400">Processing...</span>';
              try {
                const r = await fetch("/api/queue_book_ll", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({
                    book_id: primary.BookID,
                    book_type: "AudioBook",
                  }),
                });
                const jr = await r.json();
                if (!r.ok)
                  actionsCell.innerHTML = `<div class=\"text-red-500\">Error</div>`;
                else {
                  actionsCell.innerHTML = `<div class=\"text-green-400\">Marked Wanted (Audio)</div>`;
                  const aCell = row.children[4];
                  if (aCell)
                    aCell.innerHTML =
                      '<span class="text-yellow-400">Wanted</span>';
                }
              } catch (err) {
                actionsCell.innerHTML = `<div class=\"text-red-500\">${escapeHtml(err.message || String(err))}</div>`;
              }
            });
            actionsCell.appendChild(markA);
          }

          // If no action was added, show matched note
          if (!actionsCell.innerHTML) {
            actionsCell.innerHTML =
              '<div class="text-sm text-gray-400">Matched in LL</div>';
          }
        }
      });
    }

    // Form submit: first fetch SG books to display them, then call match endpoint to enrich statuses
    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      const username = ((usernameInput && usernameInput.value) || "").trim();
      if (!username) {
        results.innerHTML =
          '<div class="bg-yellow-500 text-black p-3 rounded-md">Please enter a StoryGraph username.</div>';
        return;
      }
      const types = [];
      if (ebookCheckbox && ebookCheckbox.checked) types.push("eBook");
      if (audioCheckbox && audioCheckbox.checked) types.push("AudioBook");
      if (types.length === 0) {
        results.innerHTML =
          '<div class="bg-yellow-500 text-black p-3 rounded-md">Select at least one format to check.</div>';
        return;
      }

      btn.disabled = true;
      results.innerHTML =
        '<div class="flex items-center text-gray-300"><svg class="animate-spin -ml-1 mr-3 h-5 w-5 text-sg-accent" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"></path></svg>Fetching StoryGraph books...</div>';

      // Fetch SG books first
      const sgFetch = await fetch(
        `/api/get_books/${encodeURIComponent(username)}${matchRefreshCheckbox && matchRefreshCheckbox.checked ? "?refresh=1" : ""}`,
      );
      if (!sgFetch.ok) {
        results.innerHTML = `<div class=\"bg-red-600 text-white p-3 rounded-md\">Error fetching StoryGraph books: ${sgFetch.status}</div>`;
        btn.disabled = false;
        return;
      }
      const sgBody = await sgFetch.json();
      let sgList = [];
      if (Array.isArray(sgBody)) sgList = sgBody;
      else if (sgBody && sgBody.books) sgList = sgBody.books;

      renderInitialTable(sgList, types);

      // Now call match endpoint to enrich the results
      try {
        const res = await fetch("/api/match_books", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username: username,
            types: types,
            max_books: 50,
            refresh: !!(matchRefreshCheckbox && matchRefreshCheckbox.checked),
          }),
        });
        const data = await res.json();
        if (res.ok && data && data.results && data.results.length) {
          applyMatchesToTable(data.results, types);
          meta.innerHTML = data.fetched_at
            ? `Last updated: ${new Date(data.fetched_at).toLocaleString()} ${data.cached ? "(cached)" : "(fresh)"}`
            : "";
        } else {
          meta.innerHTML =
            sgBody && sgBody.fetched_at
              ? `Last updated: ${sgBody.fetched_at} (SG only)`
              : "";
        }
      } catch (err) {
        // Ignore enrich failures; SG list is already shown
      }

      btn.disabled = false;
    });
  });
})();
