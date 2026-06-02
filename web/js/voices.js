const Voices = {
  render() {
    const el = document.getElementById("tab-voices");
    el.innerHTML = `
      <h2>Voices</h2>
      <p class="subtitle">Click a voice to hear a sample, then "Use" it in Create.</p>
      <div class="cards" id="vcards">${T2A.state.voices.map(v => `
        <div class="vcard ${v.id === T2A.state.voice ? "sel" : ""}" data-v="${v.id}">
          <div class="dot"></div>
          <div class="vn">${v.label}</div>
          <div class="vm">${v.accent} · ${v.gender}</div>
          <div class="row">
            <button class="btn play" data-v="${v.id}">▶ Sample</button>
            <button class="btn use" data-v="${v.id}">Use</button>
          </div>
        </div>`).join("")}</div>`;
    el.querySelectorAll(".play").forEach(b => b.onclick = e => { e.stopPropagation(); this.sample(b.dataset.v, b); });
    el.querySelectorAll(".use").forEach(b => b.onclick = e => {
      e.stopPropagation(); T2A.state.voice = b.dataset.v; T2A.toast("Voice set: " + b.dataset.v);
      this.render(); });
  },
  async sample(voice, btn) {
    const old = btn.textContent; btn.textContent = "…";
    try {
      const r = await fetch("/api/voice-preview", { method: "POST",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify({ voice }) });
      const blob = await r.blob(); new Audio(URL.createObjectURL(blob)).play();
    } catch (e) { T2A.toast("Sample failed"); }
    btn.textContent = old;
  },
};
