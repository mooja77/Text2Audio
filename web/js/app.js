// Shared state, API helpers, tab routing.
const T2A = {
  state: { voices: [], files: [], bookText: "", chapters: [], voice: "af_heart", speed: 0.9,
    ingestVersion: 0, ingestReady: false, firstValue: false,
    activeJob: null, activeSource: null,
    renderProgress: { percent: 0, message: "Starting…" } },
  // Escape user-controlled text before interpolating into innerHTML.
  esc(s) {
    return String(s ?? "").replace(/[&<>"']/g,
      c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  },
  // Plain-language text for any server error; never raw JSON or stack text.
  friendly(text, status) {
    let detail = String(text || "");
    try { const j = JSON.parse(detail); detail = String(j.detail ?? j.error ?? ""); } catch {}
    const rules = [
      [/unknown voice/i, "That narrator voice is no longer available. Pick another voice and try again."],
      [/already in progress/i, "Another audiobook is being made right now. Wait for it to finish, then try again."],
      [/too large/i, "That file is too large."],
      [/could not read that audio/i, "We could not read that audio file. Try a different recording."],
      [/between 1 and 120 seconds/i, "The voice sample must be between 1 and 120 seconds long."],
      [/no readable text|no readable chapters/i, "We could not find any readable text. Check the file and try again."],
      [/could not import|supported manuscript types/i, "That file type is not supported. Use .txt, Markdown, DOCX, EPUB or PDF."],
    ];
    for (const [re, msg] of rules) if (re.test(detail)) return msg;
    if (status === 404) return "We could not find that item. It may have been deleted.";
    if (detail && detail.length < 120 && !/traceback|error|exception|\.py|file "/i.test(detail)) return detail;
    return "Something went wrong. Please try again. If it keeps happening, check the setup checklist at the top of the page.";
  },
  renderChecklist(items) {
    const box = document.getElementById("firstrun");
    if (!box || !Array.isArray(items)) return;
    box.hidden = false;
    if (items.every(i => i.ok)) {
      box.innerHTML = `<p class="fr-ready">✓ Ready: everything Text2Audio needs is set up.</p>`;
      return;
    }
    box.innerHTML = `<h2 class="fr-title">Finish setting up</h2><ul class="fr-list">` + items.map(i =>
      `<li class="${i.ok ? "ok" : "bad"}"><span class="fr-state">${i.ok ? "✓ Ready" : "✗ Needs attention"}</span> <strong>${T2A.esc(i.label)}</strong> — ${T2A.esc(i.detail)}${i.ok ? "" : `<div class="fr-action">What to do: ${T2A.esc(i.action)}</div>`}</li>`).join("") + `</ul>`;
  },
  async api(path, opts) {
    const r = await fetch(path, opts);
    if (!r.ok) throw new Error(T2A.friendly(await r.text(), r.status));
    return r.headers.get("content-type")?.includes("application/json") ? r.json() : r;
  },
  // Assertive announcement for errors (region lives in index.html).
  alert(msg) {
    const a = document.getElementById("t2a-alert");
    if (!a) return this.toast(msg);
    a.textContent = ""; setTimeout(() => { a.textContent = msg; }, 50);
  },
  toast(msg) {
    let t = document.querySelector(".toast");
    if (!t) { t = document.createElement("div"); t.className = "toast";
      t.setAttribute("role", "status"); t.setAttribute("aria-live", "polite"); document.body.appendChild(t); }
    t.textContent = msg; t.classList.add("show");
    clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove("show"), 2200);
  },
  showTab(name) {
    document.querySelectorAll(".tab").forEach(b => {
      const active = b.dataset.tab === name;
      b.classList.toggle("active", active); b.setAttribute("aria-selected", String(active));
    });
    document.querySelectorAll(".tabpane").forEach(p => {
      const active = p.id === "tab-" + name;
      p.classList.toggle("active", active); p.hidden = !active;
    });
    if (name === "voices") Voices.render();
    if (name === "library") Library.render();
    if (name === "create") { Create.render(); Create.resumeActiveRender(); }
    if (name === "pronounce") Pronounce.render();
    if (name === "help") Help.render();
    location.hash = name === "create" ? "" : name;
  },
};

window.addEventListener("DOMContentLoaded", async () => {
  document.querySelectorAll(".tab").forEach(b => b.onclick = () => T2A.showTab(b.dataset.tab));
  document.querySelector(".tabs").onkeydown = e => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return;
    const tabs = [...document.querySelectorAll(".tab")];
    let index = tabs.indexOf(document.activeElement);
    if (e.key === 'Home') index = 0;
    else if (e.key === 'End') index = tabs.length - 1;
    else index = (index + (e.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
    e.preventDefault(); tabs[index].focus(); tabs[index].click();
  };
  try {
    const health = await T2A.api("/api/health");
    T2A.renderChecklist(health.checklist);
    const missing = [!health.ffmpeg && "ffmpeg", !health.espeak && "espeak-ng",
      !health.libraryWritable && "writable library storage"].filter(Boolean);
    if (missing.length) {
      const warn = document.getElementById("ffmpeg-warn");
      warn.textContent = `⚠ ${missing.join(" and ")} not found`; warn.hidden = false;
    }
    T2A.state.voices = await T2A.api("/api/voices");
    let saved = {};
    try { saved = JSON.parse(localStorage.getItem("text2audio.settings") || "{}"); }
    catch { localStorage.removeItem("text2audio.settings"); }
    if (saved.voice && T2A.state.voices.some(v => v.id === saved.voice)) T2A.state.voice = saved.voice;
    if (Number.isFinite(saved.speed)) T2A.state.speed = saved.speed;
    T2A.state.firstValue = (await T2A.api("/api/library")).length > 0;
  } catch (e) { T2A.alert("Backend not reachable"); }
  T2A.state.activeJob = localStorage.getItem("text2audio.activeJob");
  Create.render();
  Create.resumeActiveRender();
  const initialTab = location.hash.replace(/^#/, "");
  if (["library", "create", "voices", "pronounce", "help"].includes(initialTab)) T2A.showTab(initialTab);
});
