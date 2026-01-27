(function () {
  const form = document.getElementById("match-books-form");
  const usernameInput = document.getElementById("match-username");
  const btn = document.getElementById("match-books-btn");
  const clearBtn = document.getElementById("match-clear-btn");
  const meta = document.getElementById("match-books-meta");
  const results = document.getElementById("match-books-results");

  const typeEbook = document.getElementById("type-ebook");
  const typeAudio = document.getElementById("type-audio");
  const forceRefresh = document.getElementById("match-refresh");

  function showLoading(isLoading) {
    btn.disabled = isLoading;
    btn.textContent = isLoading ? "Matching…" : "Start Matching";
  }

  async function getMatchedBooks(username, noCache = false) {
    const url = `/api/match_books/${encodeURIComponent(username)}?no_cache=${noCache}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Match fetch failed: ${res.status}`);
    return res.json();
  }

  async function getLLBooks() {
    const res = await fetch(`/api/get_ll_books`);
    if (!res.ok) throw new Error(`LL fetch failed: ${res.status}`);
    return res.json();
  }

  // Helper: map LL status text to letter code
  function mapStatusLetterFromString(s) {
    if (!s && s !== 0) return null;
    const t = String(s).toLowerCase();
    if (t.includes("want") || t.includes("missing")) return "W";
    if (t.includes("skip")) return "S";
    if (t.includes("ignor")) return "I";
    if (t.includes("avail") || t.includes("in library") || t.includes("have"))
      return "H";
    return null;
  }

  function statusClassForLetter(letter) {
    switch (letter) {
      case "H":
        return "status-H";
      case "W":
        return "status-W";
      case "S":
        return "status-S";
      case "I":
        return "status-I";
      default:
        return "status-empty";
    }
  }

  function getEbookStatusLetter(item) {
    const stat = item.status || item.Status;
    const lib = item.book_library || item.BookLibrary;
    const letter = mapStatusLetterFromString(stat);
    if (letter) return letter;
    if (lib) return "H";
    return "-";
  }

  function getAudioStatusLetter(item) {
    const stat = item.audio_status || item.AudioStatus;
    const lib = item.audio_library || item.AudioLibrary;
    const letter = mapStatusLetterFromString(stat);
    if (letter) return letter;
    if (lib) return "H";
    return "-";
  }

  function isIsoTimestamp(s) {
    if (!s || typeof s !== "string") return false;
    // Match YYYY-MM-DD or YYYY-MM-DDThh:mm:ss (basic ISO forms)
    return /^\d{4}-\d{2}-\d{2}(T|$)/.test(s);
  }

  function renderMatchRow(item) {
    const row = document.createElement("div");
    row.className = "match-row";

    const left = document.createElement("div");
    left.className = "match-left";
    const title = document.createElement("div");
    title.className = "match-title";
    title.textContent = item.title || item.BookName || "(no title)";

    const author = document.createElement("div");
    author.className = "match-author";
    author.textContent = item.author || item.AuthorName || "";

    left.appendChild(title);
    left.appendChild(author);

    // Status column (two sub-columns: Ebook / Audio) — fixed width
    const statusCol = document.createElement("div");
    statusCol.className = "match-status";

    const ebookLetter = getEbookStatusLetter(item);
    const audioLetter = getAudioStatusLetter(item);

    const ebookRow = document.createElement("div");
    ebookRow.className = "match-status-row";
    const ebookLabel = document.createElement("div");
    ebookLabel.className = "match-status-label";
    ebookLabel.textContent = "E";
    const ebookValue = document.createElement("div");
    // apply a compact base class and a status modifier
    ebookValue.className = `match-status-badge ${statusClassForLetter(ebookLetter)}`;
    ebookValue.textContent = ebookLetter;
    // Tooltip should not show timestamps; prefer status or a clean library label
    const ebookLib = item.book_library || item.BookLibrary || "";
    ebookValue.title =
      item.status ||
      item.Status ||
      (isIsoTimestamp(ebookLib) ? "" : ebookLib) ||
      "";
    // attach identifiers for actions
    ebookValue.dataset.bookId = item.book_id || item.BookID || "";
    ebookValue.dataset.bookType = "eBook";
    ebookRow.appendChild(ebookLabel);
    ebookRow.appendChild(ebookValue);

    if (ebookLetter === "W") {
      ebookValue.addEventListener("click", async () => {
        if (!ebookValue.dataset.bookId)
          return alert("No book id available to force search.");
        if (!confirm("Search for this eBook in LazyLibrarian?")) return;
        const prev = ebookValue.textContent;
        ebookValue.textContent = "...";
        try {
          const res = await fetch(`/api/ll/force_search`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              book_id: ebookValue.dataset.bookId,
              book_type: "eBook",
            }),
          });
          const j = await res.json();
          if (res.ok && j.success) {
            ebookValue.textContent = "W";
            ebookValue.className = `match-status-badge ${statusClassForLetter("W")}`;
            ebookValue.title = "Wanted";
          } else {
            ebookValue.textContent = prev;
            alert(`Failed: ${j.error || JSON.stringify(j)}`);
          }
        } catch (err) {
          ebookValue.textContent = prev;
          alert(`Error: ${err.message}`);
        }
      });
    }

    // If status is Skipped or Ignored make badge clickable to mark Wanted
    if (ebookLetter === "S" || ebookLetter === "I") {
      ebookValue.style.cursor = "pointer";
      ebookValue.addEventListener("click", async () => {
        if (!ebookValue.dataset.bookId)
          return alert("No book id available to mark wanted.");
        if (!confirm("Mark this eBook as Wanted in LazyLibrarian?")) return;
        const prev = ebookValue.textContent;
        ebookValue.textContent = "...";
        try {
          const res = await fetch(`/api/ll/mark_wanted`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              book_id: ebookValue.dataset.bookId,
              book_type: "eBook",
            }),
          });
          const j = await res.json();
          if (res.ok && j.success) {
            ebookValue.textContent = "W";
            ebookValue.className = `match-status-badge ${statusClassForLetter("W")}`;
            ebookValue.title = "Wanted";
          } else {
            ebookValue.textContent = prev;
            alert(`Failed: ${j.error || JSON.stringify(j)}`);
          }
        } catch (err) {
          ebookValue.textContent = prev;
          alert(`Error: ${err.message}`);
        }
      });
    }

    const audioRow = document.createElement("div");
    audioRow.className = "match-status-row";
    const audioLabel = document.createElement("div");
    audioLabel.className = "match-status-label";
    audioLabel.textContent = "A";
    const audioValue = document.createElement("div");
    audioValue.className = `match-status-badge ${statusClassForLetter(audioLetter)}`;
    audioValue.textContent = audioLetter;
    const audioLib = item.audio_library || item.AudioLibrary || "";
    audioValue.title =
      item.audio_status ||
      item.AudioStatus ||
      (isIsoTimestamp(audioLib) ? "" : audioLib) ||
      "";
    // attach identifiers for actions
    audioValue.dataset.bookId = item.book_id || item.BookID || "";
    audioValue.dataset.bookType = "AudioBook";
    audioRow.appendChild(audioLabel);
    audioRow.appendChild(audioValue);

    // If status is Skipped or Ignored make badge clickable to mark Wanted
    if (audioLetter === "S" || audioLetter === "I") {
      audioValue.style.cursor = "pointer";
      audioValue.addEventListener("click", async () => {
        if (!audioValue.dataset.bookId)
          return alert("No book id available to mark wanted.");
        if (!confirm("Mark this AudioBook as Wanted in LazyLibrarian?")) return;
        const prev = audioValue.textContent;
        audioValue.textContent = "...";
        try {
          const res = await fetch(`/api/ll/mark_wanted`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              book_id: audioValue.dataset.bookId,
              book_type: "AudioBook",
            }),
          });
          const j = await res.json();
          if (res.ok && j.success) {
            audioValue.textContent = "W";
            audioValue.className = `match-status-badge ${statusClassForLetter("W")}`;
            audioValue.title = "Wanted";
          } else {
            audioValue.textContent = prev;
            alert(`Failed: ${j.error || JSON.stringify(j)}`);
          }
        } catch (err) {
          audioValue.textContent = prev;
          alert(`Error: ${err.message}`);
        }
      });
    }
    if (audioLetter === "W") {
      audioValue.addEventListener("click", async () => {
        if (!audioValue.dataset.bookId)
          return alert("No book id available to force search.");
        if (!confirm("Search for this audio in LazyLibrarian?")) return;
        const prev = audioValue.textContent;
        audioValue.textContent = "...";
        try {
          const res = await fetch(`/api/ll/force_search`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              book_id: audioValue.dataset.bookId,
              book_type: "AudioBook",
            }),
          });
          const j = await res.json();
          if (res.ok && j.success) {
            audioValue.textContent = "W";
            audioValue.className = `match-status-badge ${statusClassForLetter("W")}`;
            audioValue.title = "Wanted";
          } else {
            audioValue.textContent = prev;
            alert(`Failed: ${j.error || JSON.stringify(j)}`);
          }
        } catch (err) {
          audioValue.textContent = prev;
          alert(`Error: ${err.message}`);
        }
      });
    }

    statusCol.appendChild(ebookRow);
    statusCol.appendChild(audioRow);

    const right = document.createElement("div");
    right.className = "match-actions";

    // Show basic LL info if present
    const info = document.createElement("div");
    info.className = "match-info";
    // Detect LL presence using any of the known LL field names (API may use different casings)
    const lib =
      item.book_library ||
      item.BookLibrary ||
      item.audio_library ||
      item.AudioLibrary ||
      "";
    const id = item.book_id || item.BookID || "";
    const hasLL = Boolean(
      lib ||
      id ||
      item.BookID ||
      item.book_id ||
      item.BookLibrary ||
      item.book_library ||
      item.AudioLibrary ||
      item.audio_library,
    );

    if (hasLL) {
      const libLabel = lib || item.BookLibrary || item.AudioLibrary || "";
      const displayLabel = isIsoTimestamp(libLabel)
        ? "in LL"
        : libLabel || "in LL";
      info.textContent = displayLabel;
    } else {
      info.textContent = "not in LL";
    }

    // Search LL button (checks LL dataset live)
    const searchBtn = document.createElement("button");
    searchBtn.type = "button";
    searchBtn.className = "match-search-btn";
    searchBtn.textContent = "Search LL";
    searchBtn.addEventListener("click", async () => {
      try {
        searchBtn.disabled = true;
        searchBtn.textContent = "Searching…";
        const ll = await getLLBooks();
        const found = ll.find((rec) => {
          const t = (rec.title || rec.BookName || "").toString().toLowerCase();
          const a = (rec.author || rec.AuthorName || "")
            .toString()
            .toLowerCase();
          return (
            (t && t === (item.title || "").toLowerCase()) ||
            (a && a === (item.author || "").toLowerCase())
          );
        });
        if (found) {
          // Show found details inline (hide timestamps)
          const libLabel = found.BookLibrary || found.book_library || "";
          const displayLabel = isIsoTimestamp(libLabel)
            ? "in LL"
            : libLabel || "in LL";
          info.textContent = `Found in LL: ${displayLabel}`;
        } else {
          info.textContent = "No match found in LL";
        }
      } catch (err) {
        info.textContent = `Error: ${err.message}`;
      } finally {
        searchBtn.disabled = false;
        searchBtn.textContent = "Search LL";
      }
    });

    right.appendChild(info);
    right.appendChild(searchBtn);

    row.appendChild(left);

    // ABS presence column (explicit E/A flags)
    const absCol = document.createElement("div");
    absCol.className = "match-abs";
    // Explicitly check abs_in_ebook / abs_in_audiobook columns and mark Y/N
    const hasEbookFlag =
      item.abs_in_ebook === true ||
      item.abs_in_ebook === "True" ||
      item.abs_in_ebook === "true" ||
      item.abs_in_ebook === 1;
    const hasAudioFlag =
      item.abs_in_audiobook === true ||
      item.abs_in_audiobook === "True" ||
      item.abs_in_audiobook === "true" ||
      item.abs_in_audiobook === 1;
    const e = hasEbookFlag ? "Y" : "N";
    const a = hasAudioFlag ? "Y" : "N";
    absCol.textContent = `E:${e} A:${a}`;

    row.appendChild(statusCol);
    row.appendChild(absCol);
    row.appendChild(right);
    return row;
  }

  function applyTypeFilters(items) {
    // If no type boxes are checked, show everything
    const ebook = typeEbook.checked;
    const audio = typeAudio.checked;
    if (ebook && audio) return items;
    return items.filter((it) => {
      const hasEbook = Boolean(it.book_library || it.BookLibrary);
      const hasAudio = Boolean(it.audio_library || it.AudioLibrary);
      if (ebook && !audio) return hasEbook;
      if (audio && !ebook) return hasAudio;
      return hasEbook || hasAudio;
    });
  }

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const username = usernameInput.value && usernameInput.value.trim();
    if (!username) {
      meta.textContent = "Please enter a username.";
      return;
    }

    try {
      showLoading(true);
      results.innerHTML = "";
      meta.textContent = "Fetching matches…";

      const matched = await getMatchedBooks(username, Boolean(forceRefresh.checked));

      // Show raw JSON response in the debug panel (if present)
      const rawBtn = document.getElementById("match-show-raw-btn");
      const rawPre = document.getElementById("match-raw-json");
      if (rawPre) {
        try {
          rawPre.textContent = JSON.stringify(matched, null, 2);
        } catch (err) {
          rawPre.textContent = String(matched);
        }
        rawPre.style.display = "none";
      }
      if (rawBtn && rawPre) {
        rawBtn.textContent = "Show raw JSON";
        rawBtn.onclick = () => {
          if (rawPre.style.display === "none") {
            rawPre.style.display = "block";
            rawBtn.textContent = "Hide raw JSON";
          } else {
            rawPre.style.display = "none";
            rawBtn.textContent = "Show raw JSON";
          }
        };
      }

      // Apply type filters and render
      const filtered = applyTypeFilters(matched || []);

      results.innerHTML = "";
      if (!filtered || filtered.length === 0) {
        results.textContent = "No matches found.";
      } else {
        const container = document.createElement("div");
        container.className = "match-container";

        // Header that lines up with rows: Title | LL Status (E / A) | actions
        const header = document.createElement("div");
        header.className = "match-header";
        const headerLeft = document.createElement("div");
        headerLeft.className = "match-header-left";
        headerLeft.textContent = "Title";
        const headerStatus = document.createElement("div");
        headerStatus.className = "match-header-status";
        headerStatus.textContent = "LL Status (E / A)";
        const headerAbs = document.createElement("div");
        headerAbs.className = "match-header-abs";
        headerAbs.textContent = "ABS";
        const headerRight = document.createElement("div");
        headerRight.className = "match-header-right";
        headerRight.textContent = "";
        header.appendChild(headerLeft);
        header.appendChild(headerStatus);
        header.appendChild(headerAbs);
        header.appendChild(headerRight);
        container.appendChild(header);

        filtered.forEach((it) => container.appendChild(renderMatchRow(it)));
        results.appendChild(container);
      }

      meta.textContent = `Matches: ${matched.length} • Shown: ${filtered.length} • Fetched at ${new Date().toLocaleString()}`;
    } catch (err) {
      meta.textContent = `Error: ${err.message}`;
    } finally {
      showLoading(false);
    }
  });

  clearBtn.addEventListener("click", () => {
    results.innerHTML = "";
    meta.textContent = "";
    usernameInput.value = "";
  });
})();
