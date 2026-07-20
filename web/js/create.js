const Create = {
  render() {
    const el = document.getElementById("tab-create");
    const opt = v => `<option value="${T2A.esc(v.id)}" ${v.id === T2A.state.voice ? "selected" : ""}>${T2A.esc(v.label)}${v.kind === "cloned" ? " (cloned)" : ` · ${T2A.esc(v.accent)} ${T2A.esc(v.gender)}`}</option>`;
    const presets = T2A.state.voices.filter(v => v.kind !== "cloned").map(opt).join("");
    const cloned = T2A.state.voices.filter(v => v.kind === "cloned").map(opt).join("");
    const voiceOpts = presets + (cloned ? `<optgroup label="Your voices">${cloned}</optgroup>` : "");
    el.innerHTML = `
      <h2>Create audiobook</h2>
      <p class="subtitle">Drop in your chapter files (.md or .txt), set options, and generate.</p>
      <div class="grid2">
        <div class="panel">
          <div class="label">Source files</div>
          <div class="dropzone" id="dz">Drop .md / .txt files here, or click to browse
            <input type="file" id="fi" multiple accept=".md,.txt" hidden></div>
          <div class="filelist" id="fl"></div>
        </div>
        <div class="panel">
          <div class="label">Settings</div>
          <div class="field"><label>Title</label><input id="f-title" placeholder="My Book"></div>
          <div class="field"><label>Author</label><input id="f-author" placeholder="Author name"></div>
          <div class="field"><label>Narrator voice</label>
            <div class="voicepick"><select id="f-voice">${voiceOpts}</select>
              <button class="btn" id="f-prev">▶ Preview</button></div></div>
          <div class="field"><label>Speed · <span id="spd">${T2A.state.speed}</span>×</label>
            <input type="range" id="f-speed" min="0.5" max="1.5" step="0.05" value="${T2A.state.speed}"></div>
          <button class="btn primary" id="gen" disabled>Generate Audiobook</button>
          <div class="progress" id="prog" hidden>
            <div class="bar"><div class="barf" id="barf"></div></div>
            <div class="meta"><span id="pmsg">Starting…</span><span id="ppct">0%</span></div>
          </div>
        </div>
      </div>
      <div class="panel" style="margin-top:20px">
        <div class="label">Detected chapters <span id="chcount" class="muted"></span></div>
        <div class="chaplist" id="chaps"><span class="muted">Add files to see chapters.</span></div>
      </div>`;
    this.bind();
  },

  bind() {
    const dz = document.getElementById("dz"), fi = document.getElementById("fi");
    dz.onclick = () => fi.click();
    fi.onchange = () => this.addFiles([...fi.files]);
    dz.ondragover = e => { e.preventDefault(); dz.classList.add("drag"); };
    dz.ondragleave = () => dz.classList.remove("drag");
    dz.ondrop = e => { e.preventDefault(); dz.classList.remove("drag"); this.addFiles([...e.dataTransfer.files]); };
    document.getElementById("f-voice").onchange = e => T2A.state.voice = e.target.value;
    document.getElementById("f-speed").oninput = e => {
      T2A.state.speed = parseFloat(e.target.value); document.getElementById("spd").textContent = e.target.value; };
    document.getElementById("f-prev").onclick = () => this.preview();
    document.getElementById("gen").onclick = () => this.generate();
    this.renderFiles();
  },

  addFiles(fileList) {
    const wanted = fileList.filter(f => /\.(md|txt)$/i.test(f.name));
    T2A.state.files.push(...wanted);
    T2A.state.bookText = ""; T2A.state.ingestReady = false;
    T2A.state.files.sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }));
    this.renderFiles(); this.refreshChapters();
  },

  renderFiles() {
    const fl = document.getElementById("fl");
    fl.innerHTML = T2A.state.files.map((f, i) =>
      `<div class="filerow" draggable="true" data-i="${i}">
         <span class="grip">⋮⋮</span><span class="nm">${T2A.esc(f.name)}</span>
         <span class="wc">${Math.round(f.size / 6)}w</span>
         <button class="x" data-x="${i}">✕</button></div>`).join("");
    fl.querySelectorAll(".x").forEach(b => b.onclick = () => {
      T2A.state.files.splice(+b.dataset.x, 1); T2A.state.bookText = "";
      T2A.state.ingestReady = false; this.renderFiles(); this.refreshChapters(); });
    this.enableReorder(fl);
    document.getElementById("gen").disabled = !T2A.state.files.length || !T2A.state.ingestReady;
  },

  enableReorder(fl) {
    let dragI = null;
    fl.querySelectorAll(".filerow").forEach(row => {
      row.ondragstart = () => { dragI = +row.dataset.i; row.classList.add("dragging"); };
      row.ondragend = () => row.classList.remove("dragging");
      row.ondragover = e => e.preventDefault();
      row.ondrop = e => {
        e.preventDefault(); const dropI = +row.dataset.i;
        const arr = T2A.state.files; const [m] = arr.splice(dragI, 1); arr.splice(dropI, 0, m);
        T2A.state.bookText = ""; T2A.state.ingestReady = false;
        this.renderFiles(); this.refreshChapters();
      };
    });
  },

  async refreshChapters() {
    const version = ++T2A.state.ingestVersion;
    const chaps = document.getElementById("chaps");
    if (!T2A.state.files.length) { chaps.innerHTML = `<span class="muted">Add files to see chapters.</span>`;
      T2A.state.bookText = ""; T2A.state.ingestReady = false; T2A.state.chapters = [];
      document.getElementById("chcount").textContent = ""; return false; }
    T2A.state.ingestReady = false;
    document.getElementById("gen").disabled = true;
    const fd = new FormData();
    T2A.state.files.forEach(f => fd.append("files", f));
    try {
      const data = await T2A.api("/api/ingest", { method: "POST", body: fd });
      if (version !== T2A.state.ingestVersion) return false;
      T2A.state.bookText = data.bookText; T2A.state.chapters = data.chapters;
      T2A.state.ingestReady = data.chapters.length > 0;
      document.getElementById("gen").disabled = !T2A.state.ingestReady;
      document.getElementById("chcount").textContent = `· ${data.chapters.length}`;
      chaps.innerHTML = data.chapters.map(c =>
        `<div class="chapline"><span class="ci">${c.index + 1}</span>
         <span class="ct">${T2A.esc(c.title)}</span><span class="cc">${c.chars.toLocaleString()} chars</span></div>`).join("");
      return T2A.state.ingestReady;
    } catch (e) {
      if (version === T2A.state.ingestVersion) {
        T2A.state.bookText = ""; T2A.state.chapters = []; T2A.state.ingestReady = false;
        document.getElementById("gen").disabled = true; T2A.toast("Ingest failed: " + e.message);
      }
      return false;
    }
  },

  async preview() {
    const btn = document.getElementById("f-prev"); btn.textContent = "…";
    try {
      const r = await fetch("/api/voice-preview", { method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ voice: T2A.state.voice }) });
      if (!r.ok) throw new Error(await r.text());
      const blob = await r.blob(); const url = URL.createObjectURL(blob); const audio = new Audio(url);
      audio.onended = audio.onerror = () => URL.revokeObjectURL(url); await audio.play();
    } catch (e) { T2A.toast("Preview failed"); }
    btn.textContent = "▶ Preview";
  },

  async generate() {
    if (!T2A.state.ingestReady && !await this.refreshChapters()) return;
    const gen = document.getElementById("gen"); gen.disabled = true;
    const prog = document.getElementById("prog"); prog.hidden = false;
    const body = {
      bookText: T2A.state.bookText, voice: T2A.state.voice, speed: T2A.state.speed,
      title: document.getElementById("f-title").value, author: document.getElementById("f-author").value };
    let jobId;
    try {
      const res = await T2A.api("/api/render", { method: "POST",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      jobId = res.jobId;
    } catch (e) { T2A.toast("Could not start render"); gen.disabled = false; return; }

    const t0 = Date.now();
    const src = new EventSource(`/api/render/${jobId}/stream`);
    src.onmessage = ev => {
      const e = JSON.parse(ev.data);
      if (e.type === "progress") {
        document.getElementById("barf").style.width = e.percent + "%";
        document.getElementById("ppct").textContent = e.percent + "%";
        const el = (Date.now() - t0) / 1000;
        const eta = e.percent > 0 ? Math.round(el / e.percent * (100 - e.percent)) : 0;
        document.getElementById("pmsg").textContent =
          `Chapter ${e.chapterIndex + 1} of ${e.chapterCount} · ${e.chapterTitle} — ETA ${eta}s`;
      } else if (e.type === "done") {
        document.getElementById("barf").style.width = "100%";
        document.getElementById("ppct").textContent = "100%";
        document.getElementById("pmsg").textContent = "Done ✓";
        src.close(); gen.disabled = false; T2A.toast("Audiobook ready"); T2A.showTab("library");
      } else if (e.type === "error") {
        document.getElementById("pmsg").textContent = "Error: " + (e.message || "render failed");
        src.close(); gen.disabled = false;
      }
    };
    src.onerror = () => {
      if (src.readyState === EventSource.CLOSED) {
        gen.disabled = false; document.getElementById("pmsg").textContent = "Connection lost";
      } else {
        document.getElementById("pmsg").textContent = "Reconnecting to render…";
      }
    };
  },
};
