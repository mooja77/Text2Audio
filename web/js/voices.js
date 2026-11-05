const Voices = {
  render() {
    const el = document.getElementById("tab-voices");
    el.innerHTML = `
      <h2>Voices</h2>
      <p class="subtitle">Click a voice to hear a sample, then "Use" it in Create.</p>
      <div class="panel" style="max-width:680px;margin-bottom:18px">
        <div class="label">Clone a voice</div>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          <input class="cinput" id="cv-name" aria-label="Voice name" placeholder="Voice name (e.g. My Narrator)">
          <input class="cinput" id="cv-file" aria-label="Reference audio file, about 10 to 30 seconds" type="file" accept="audio/*">
        </div>
        <textarea class="cinput" id="cv-text" aria-label="Transcript of the clip (optional)" rows="2" placeholder="(optional) type what's said in the clip — improves quality; leave blank to auto-detect"></textarea>
        <button class="btn" id="cv-add" style="margin-top:8px">Create voice</button>
        <div class="muted" style="font-size:12px;margin-top:6px">Upload 10–30 s of clean speech from one person. Cloned voices use the studio engine, which needs a graphics card to run at a usable speed.</div>
        <div id="cv-notice" role="note" style="font-size:13px;margin-top:10px">
          <p style="margin:0 0 6px">Only clone your own voice, a voice you have the speaker's permission to use, or a public-domain recording.</p>
          <p style="margin:0 0 6px">Cloning uses <a href="https://github.com/resemble-ai/chatterbox" target="_blank" rel="noreferrer">Chatterbox</a> by Resemble AI (MIT licence), so you may sell audiobooks made with a voice you have the right to use. Its audio carries an inaudible watermark that marks it as AI-generated.</p>
          <label id="cv-ack-wrap"><input type="checkbox" id="cv-ack"> I have the right to clone the voices I upload.</label>
        </div>
      </div>
      <div class="cards" id="vcards"></div>`;
    el.querySelectorAll(".cinput").forEach(i => {
      i.style.cssText = "background:var(--panel2);border:1px solid var(--bd);color:var(--tx);border-radius:8px;padding:9px 10px;font-size:14px;width:100%;margin-top:8px";
    });
    document.getElementById("cv-add").onclick = () => this.clone();
    const cl = T2A.state.health && T2A.state.health.cloning;
    if (cl && !cl.available) {
      document.getElementById("cv-add").disabled = true;
      const p = document.createElement("p");
      p.textContent = "Voice cloning is unavailable: " + cl.reason;
      document.getElementById("cv-notice").prepend(p);
    }
    this.loadConsent();
    this.refresh();
  },

  async loadConsent() {
    try { this.acked = (await T2A.api("/api/clone-consent")).acknowledged === true; }
    catch (e) { this.acked = false; }
    const wrap = document.getElementById("cv-ack-wrap");
    if (wrap) wrap.hidden = this.acked;
  },

  async refresh() {
    try { T2A.state.voices = await T2A.api("/api/voices"); } catch (e) {}
    const cards = document.getElementById("vcards");
    cards.innerHTML = T2A.state.voices.map(v => `
      <div class="vcard ${v.id === T2A.state.voice ? "sel" : ""}" data-v="${T2A.esc(v.id)}">
        <div class="dot"></div>
        <div class="vn">${T2A.esc(v.label)} ${v.kind === "cloned" ? '<span style="font-size:10px;color:var(--ac2)">�� cloned</span>' : v.kind === "studio" ? '<span style="font-size:10px;color:var(--ac2)">● studio</span>' : ""}</div>
        <div class="vm">${T2A.esc(v.accent)}${v.gender ? " · " + T2A.esc(v.gender) : ""}</div>
        ${T2A.voiceBlocked(v) ? `<div class="vm" role="note">Unavailable: ${T2A.esc(T2A.voiceBlocked(v))}</div>` : ""}
        <div class="row">
          <button class="btn play" ${T2A.voiceBlocked(v) ? "disabled" : ""} data-v="${T2A.esc(v.id)}" aria-label="Play sample of ${T2A.esc(v.label)}">▶ Sample</button>
          <button class="btn use" ${T2A.voiceBlocked(v) ? "disabled" : ""} data-v="${T2A.esc(v.id)}" aria-label="Use ${T2A.esc(v.label)} as narrator">Use</button>
          ${v.kind === "cloned" ? `<button class="btn del" data-v="${T2A.esc(v.id)}" aria-label="Delete ${T2A.esc(v.label)}">✕</button>` : ""}
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
    const box = document.getElementById("cv-ack");
    if (!this.acked) {
      if (!box || !box.checked) { T2A.toast("Confirm you have the right to clone this voice first"); return; }
      try {
        await T2A.api("/api/clone-consent", { method: "POST",
          headers: { "Content-Type": "application/json" }, body: JSON.stringify({ acknowledged: true }) });
        this.acked = true;
      } catch (e) { T2A.alert("Could not save your acknowledgement"); return; }
    }
    T2A.toast("Creating voice…");
    try {
      await T2A.api("/api/voices/clone", { method: "POST", body: fd });
      document.getElementById("cv-name").value = ""; document.getElementById("cv-text").value = "";
      T2A.toast("Voice created"); this.refresh();
    } catch (e) { T2A.alert("Clone failed — check the audio file"); }
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
