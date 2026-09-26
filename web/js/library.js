const Library = {
  async render() {
    const el = document.getElementById("tab-library");
    el.innerHTML = `<h2>Library</h2><p class="subtitle">Your finished audiobooks.</p><div id="libwrap"></div>`;
    const wrap = document.getElementById("libwrap");
    let items;
    try { items = await T2A.api("/api/library"); }
    catch (e) { wrap.innerHTML = `<p class="muted">Could not load library.</p>`; return; }
    if (!items.length) { wrap.innerHTML = `<p class="muted">No audiobooks yet — create one in the Create tab.</p>`; return; }
    wrap.innerHTML = `<div class="libgrid">${items.map(m => `
      <div class="libcard" data-id="${m.id}">
        <div class="cover">${m.coverFile ? `<img src="/api/cover/${m.id}">` : "🎧"}</div>
        <div class="b"><div class="t">${T2A.esc(m.title)}</div>
          <div class="m">${T2A.esc(m.author || "—")}</div>
          <div class="m">${fmtDur(m.durationSeconds)} · ${m.chapters.length} ch</div></div>
      </div>`).join("")}</div>`;
    wrap.querySelectorAll(".libcard").forEach(c => c.onclick = () => this.detail(c.dataset.id));
    function fmtDur(s) { const h = Math.floor(s / 3600), m = Math.round((s % 3600) / 60); return h ? `${h}h ${m}m` : `${m}m`; }
  },

  async detail(id) {
    const el = document.getElementById("tab-library");
    let item;
    try { item = await T2A.api(`/api/library/${id}`); } catch (e) { T2A.toast("Not found"); return; }
    el.innerHTML = `<button class="backlink" id="back">← Library</button>
      <div id="playerwrap"></div>
      <div style="margin-top:16px;display:flex;gap:8px;flex-wrap:wrap">
        <button class="btn" id="retag">Retag</button>
        ${item.wavKept ? '<button class="btn" id="remaster">Re-master</button>' +
          '<button class="btn" id="export-wav">Export chapter WAVs</button>' +
          '<button class="btn" id="export-acx">Export ACX-review MP3s</button>' +
          '<button class="btn" id="purge">Purge source audio</button>' : ''}
        <button class="btn" id="quality">Audio quality report</button>
        <button class="btn" id="del">Delete</button></div>
      <div id="quality-report" class="panel" style="margin-top:12px" hidden></div>
      ${item.wavKept ? '<div class="muted" style="margin-top:8px;font-size:12px">Source audio kept — you can re-master instantly. Purge to reclaim disk space.</div>' : ''}`;
    document.getElementById("back").onclick = () => this.render();
    Player.mount(document.getElementById("playerwrap"), item);
    document.getElementById("del").onclick = async () => {
      if (!confirm("Delete this audiobook?")) return;
      try { await T2A.api(`/api/library/${id}`, { method: "DELETE" }); T2A.toast("Deleted"); this.render(); }
      catch (e) { T2A.toast("Delete failed: " + e.message); } };
    document.getElementById("retag").onclick = async () => {
      const title = prompt("Title", item.title); if (title === null) return;
      const author = prompt("Author", item.author || ""); if (author === null) return;
      try { await T2A.api(`/api/library/${id}/retag`, { method: "POST",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title, author }) });
        T2A.toast("Updated"); this.detail(id); } catch (e) { T2A.toast("Update failed: " + e.message); } };
    document.getElementById("quality").onclick = async () => {
      const wrap = document.getElementById("quality-report");
      try {
        const q = await T2A.api(`/api/library/${id}/quality`);
        wrap.hidden = false;
        wrap.innerHTML = `<div class="label">Audio quality</div>
          <p>${q.personalM4bPass ? "✓ Personal M4B checks passed" : "⚠ Personal M4B needs review"}</p>
          <p class="muted">${T2A.esc(q.audio.codec)} · ${q.audio.sampleRate.toLocaleString()} Hz · ${Math.round(q.audio.bitrate / 1000)} kbps · peak ${q.audio.peakDb ?? "unknown"} dB · mean ${q.audio.meanDb ?? "unknown"} dB</p>
          <p class="muted">ACX submission ready: ${q.acxSubmissionPass ? "yes" : "no"}. ${T2A.esc(q.note)}</p>`;
      } catch (e) { T2A.toast("Quality analysis failed: " + e.message); }
    };
    if (item.wavKept) {
      document.getElementById("export-wav").onclick = () => {
        location.href = `/api/library/${id}/export/wav`;
      };
      document.getElementById("export-acx").onclick = () => {
        location.href = `/api/library/${id}/export/acx-review`;
      };
      document.getElementById("remaster").onclick = async () => {
        T2A.toast("Re-mastering…");
        try { await T2A.api(`/api/library/${id}/remaster`, { method: "POST",
          headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) });
          T2A.toast("Re-mastered"); this.detail(id); } catch (e) { T2A.toast("Re-master failed: " + e.message); } };
      document.getElementById("purge").onclick = async () => {
        if (!confirm("Delete the source WAVs? You won't be able to re-master without re-rendering.")) return;
        try { await T2A.api(`/api/library/${id}/purge-wav`, { method: "POST" });
          T2A.toast("Source audio purged"); this.detail(id); } catch (e) { T2A.toast("Purge failed: " + e.message); } };
    }
  },
};
