const Pronounce = {
  async render() {
    const el = document.getElementById("tab-pronounce");
    el.innerHTML = `
      <h2>Pronounce</h2>
      <p class="subtitle">Fix how names and words are read. Rules apply to new renders.</p>
      <div class="panel" style="max-width:680px">
        <div class="label">Add a rule</div>
        <div style="display:flex;gap:8px">
          <input class="pinput" id="pw" placeholder="word (e.g. Carrigaline)">
          <input class="pinput" id="ps" placeholder="say as (e.g. Carrig a line)">
          <button class="btn" id="padd">Add</button>
        </div>
        <div class="label" style="margin-top:16px">Test how text will be read</div>
        <div style="display:flex;gap:8px">
          <input class="pinput" id="pt" placeholder="type a word or sentence">
          <button class="btn" id="ptbtn">Preview</button>
        </div>
        <div id="ptout" class="muted" style="margin-top:8px"></div>
      </div>
      <div class="panel" style="max-width:680px;margin-top:16px">
        <div class="label">Your rules</div>
        <div id="pcustom"></div>
        <div class="label" style="margin-top:16px">Built-in (read-only)</div>
        <div id="pbuiltin" class="muted" style="font-size:12px;line-height:1.8"></div>
      </div>`;
    el.querySelectorAll(".pinput").forEach(i => {
      i.style.cssText = "flex:1;background:var(--panel2);border:1px solid var(--bd);color:var(--tx);border-radius:8px;padding:9px 10px;font-size:14px";
    });
    document.getElementById("padd").onclick = () => this.add();
    document.getElementById("ptbtn").onclick = () => this.test();
    this.refresh();
  },

  async refresh() {
    let d;
    try { d = await T2A.api("/api/pronunciations"); }
    catch (e) { T2A.toast("Could not load rules"); return; }
    const cwrap = document.getElementById("pcustom");
    const entries = Object.entries(d.custom);
    cwrap.innerHTML = entries.length ? entries.map(([w, s]) =>
      `<div class="filerow"><span class="nm">${T2A.esc(w)} → ${T2A.esc(s)}</span><button class="x" data-w="${T2A.esc(w)}">✕</button></div>`).join("")
      : `<span class="muted">No custom rules yet — add one above.</span>`;
    cwrap.querySelectorAll(".x").forEach(b => b.onclick = async () => {
      try {
        await T2A.api(`/api/pronunciations/${encodeURIComponent(b.dataset.w)}`, { method: "DELETE" });
        this.refresh();
      } catch (e) { T2A.toast("Delete failed: " + e.message); }
    });
    document.getElementById("pbuiltin").textContent =
      Object.entries(d.builtin).map(([w, s]) => `${w} → ${s}`).join("   ·   ");
  },

  async add() {
    const w = document.getElementById("pw").value.trim();
    const s = document.getElementById("ps").value.trim();
    if (!w || !s) { T2A.toast("Enter both a word and how to say it"); return; }
    try {
      await T2A.api(`/api/pronunciations/${encodeURIComponent(w)}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sayAs: s }) });
      document.getElementById("pw").value = "";
      document.getElementById("ps").value = "";
      T2A.toast("Rule added"); this.refresh();
    } catch (e) { T2A.toast("Could not add rule: " + e.message); }
  },

  async test() {
    const text = document.getElementById("pt").value;
    try {
      const d = await T2A.api("/api/normalize-preview", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }) });
      document.getElementById("ptout").textContent = "→ " + d.normalized;
    } catch (e) { T2A.toast("Preview failed"); }
  },
};
