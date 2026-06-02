// Shared state, API helpers, tab routing.
const T2A = {
  state: { voices: [], files: [], bookText: "", chapters: [], voice: "af_heart", speed: 0.9 },
  async api(path, opts) {
    const r = await fetch(path, opts);
    if (!r.ok) throw new Error((await r.text()) || r.status);
    return r.headers.get("content-type")?.includes("application/json") ? r.json() : r;
  },
  toast(msg) {
    let t = document.querySelector(".toast");
    if (!t) { t = document.createElement("div"); t.className = "toast"; document.body.appendChild(t); }
    t.textContent = msg; t.classList.add("show");
    clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove("show"), 2200);
  },
  showTab(name) {
    document.querySelectorAll(".tab").forEach(b => b.classList.toggle("active", b.dataset.tab === name));
    document.querySelectorAll(".tabpane").forEach(p => p.classList.toggle("active", p.id === "tab-" + name));
    if (name === "voices") Voices.render();
    if (name === "library") Library.render();
    if (name === "create") Create.render();
  },
};

window.addEventListener("DOMContentLoaded", async () => {
  document.querySelectorAll(".tab").forEach(b => b.onclick = () => T2A.showTab(b.dataset.tab));
  try {
    const health = await T2A.api("/api/health");
    if (!health.ffmpeg) document.getElementById("ffmpeg-warn").hidden = false;
    T2A.state.voices = await T2A.api("/api/voices");
  } catch (e) { T2A.toast("Backend not reachable"); }
  Create.render();
});
