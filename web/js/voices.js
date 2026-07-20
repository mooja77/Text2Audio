const Voices = {
  render() {
    const el = document.getElementById("tab-voices");
    el.innerHTML = `
      <h2>Voices</h2>
      <p class="subtitle">Click a voice to hear a sample, then "Use" it in Create.</p>
      <div class="panel" style="max-width:680px;margin-bottom:18px">
        <div class="label">Clone a voice</div>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          <input class="cinput" id="cv-name" placeholder="Voice name (e.g. My Narrator)">
          <input class="cinput" id="cv-file" type="file" accept="audio/*">
        </div>
        <textarea class="cinput" id="cv-text" rows="2" placeholder="(optional) type what's said in the clip — improves quality; leave blank to auto-detect"></textarea>
        <button class="btn" id="cv-add" style="margin-top:8px">Create voice</button>
        <div class="muted" style="font-size:12px;margin-top:6px">Upload ~10–30s of clean speech. Cloned renders are higher quality but much slower.</div>
      </div>
      <div class="cards" id="vcards"></div>`;
    el.querySelectorAll(".cinput").forEach(i => {
      i.style.cssText = "background:var(--panel2);border:1px solid var(--bd);color:var(--tx);border-radius:8px;padding:9px 10px;font-size:14px;width:100%;margin-top:8px";
    });
    document.getElementById("cv-add").onclick = () => this.clone();
    this.refresh();
  },

  async refresh() {
    try { T2A.state.voices = await T2A.api("/api/voices"); } catch (e) {}
    const cards = document.getElementById("vcards");
    cards.innerHTML = T2A.state.voices.map(v => `
      <div class="vcard ${v.id === T2A.state.voice ? "sel" : ""}" data-v="${T2A.esc(v.id)}">
        <div class="dot"></div>
        <div class="vn">${T2A.esc(v.label)} ${v.kind === "cloned" ? '<span style="font-size:10px;color:var(--ac2)">● cloned</span>' : ""}</div>
        <div class="vm">${T2A.esc(v.accent)}${v.gender ? " · " + T2A.esc(v.gender) : ""}</div>
        <div class="row">
          <button class="btn play" data-v="${T2A.esc(v.id)}">▶ Sample</button>
          <button class="btn use" data-v="${T2A.esc(v.id)}">Use</button>
          ${v.kind === "cloned" ? `<button class="btn del" data-v="${T2A.esc(v.id)}">✕</button>` : ""}
        </div>
      </div>`).join("");
    cards.querySelectorAll(".play").forEach(b => b.onclick = e => { e.stopPropagation(); this.sample(b.dataset.v, b); });
    cards.querySelectorAll(".use").forEach(b => b.onclick = e => {
      e.stopPropagation(); T2A.state.voice = b.dataset.v; T2A.toast("Voice set: " + b.dataset.v); this.refresh(); });
    cards.querySelectorAll(".del").forEach(b => b.onclick = async e => {
      e.stopPropagation();
      if (!confirm("Delete this cloned voice?")) return;
      try {
        await T2A.api(`/api/voices/${encodeURIComponent(b.dataset.v)}`, { method: "DELETE" });
        T2A.toast("Deleted"); this.refresh();
      } catch (err) { T2A.toast("Delete failed: " + err.message); }
    });
  },

  async clone() {
    const name = document.getElementById("cv-name").value.trim();
    const file = document.getElementById("cv-file").files[0];
    const refText = document.getElementById("cv-text").value;
    if (!name || !file) { T2A.toast("Enter a name and choose an audio file"); return; }
    const fd = new FormData();
    fd.append("name", name); fd.append("audio", file); fd.append("refText", refText);
    T2A.toast("Creating voice…");
    try {
      await T2A.api("/api/voices/clone", { method: "POST", body: fd });
      document.getElementById("cv-name").value = ""; document.getElementById("cv-text").value = "";
      T2A.toast("Voice created"); this.refresh();
    } catch (e) { T2A.toast("Clone failed — check the audio file"); }
  },

  async sample(voice, btn) {
    const old = btn.textContent; btn.textContent = "…";
    try {
      const r = await fetch("/api/voice-preview", { method: "POST",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify({ voice }) });
      if (!r.ok) throw new Error(await r.text());
      const blob = await r.blob(); const url = URL.createObjectURL(blob); const audio = new Audio(url);
      audio.onended = audio.onerror = () => URL.revokeObjectURL(url); await audio.play();
    } catch (e) { T2A.toast("Sample failed"); }
    btn.textContent = old;
  },
};
