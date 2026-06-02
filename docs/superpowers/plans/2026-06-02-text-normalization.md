# Text Normalization & Pronunciation Implementation Plan (Phase 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the narrator read text correctly — expand numbers/abbreviations and fix proper-noun pronunciations — via a `normalize_text` engine and a global, user-editable pronunciation dictionary with a "Pronounce" UI tab.

**Architecture:** A new `pipeline/normalize.py` transforms each chapter's text before chunking. A `PronunciationStore` persists user rules as JSON; `normalize_text` merges them over built-in defaults. New API endpoints + a Pronounce tab manage rules and preview transformations. Render threads the custom rules through; nothing else in the pipeline changes.

**Tech Stack:** Python 3.11, `num2words` (new), the existing kokoro/FastAPI pipeline, pytest (GPU-free), vanilla JS frontend.

---

## Environment notes (already done — do NOT redo)

- venv at `.venv`; use `./.venv/Scripts/python.exe`. `num2words` is already installed (Task 1 only records it in requirements). ffmpeg on PATH.
- Branch: create `text-normalization` off `audio-mastering` (Task 0). Git identity fallback: `git -c user.name="Text2Audio" -c user.email="mooja77@gmail.com" commit ...`.
- Existing files to integrate with (don't break public APIs): `backend/render.py` (`render_audiobook`, `_render_into`), `server.py`, `web/index.html`, `web/js/app.js`. Render currently does `synth.synth_paragraphs(chunk_paragraphs(ch.text))`.
- Full suite green before starting (`./.venv/Scripts/python.exe -m pytest -q` → 63 passed, 1 skipped).

## Locked interfaces

- `pipeline/normalize.py`: `ABBREVIATIONS: dict`, `BUILTIN_PRONUNCIATIONS: dict`, `expand_numbers(text)->str`, `expand_abbreviations(text)->str`, `apply_pronunciations(text, rules)->str`, `normalize_text(text, custom_rules=None)->str`.
- `backend/pronunciations.py`: `class PronunciationStore(path)` → `get_all()->dict`, `set_rule(word, say_as)->None`, `remove(word)->None`.
- `backend/render.py`: `render_audiobook(..., custom_rules=None)` and `_render_into(..., custom_rules=None)`.
- `server.py`: global `pron`; `GET /api/pronunciations`, `PUT /api/pronunciations/{word}`, `DELETE /api/pronunciations/{word}`, `POST /api/normalize-preview`.
- `web/js/pronounce.js`: `Pronounce.render()`.

---

## Task 0: Branch

- [ ] **Step 1: Create the feature branch**

```bash
git checkout audio-mastering
git checkout -b text-normalization
git branch --show-current
```
Expected: `text-normalization`.

---

## Task 1: Record the num2words dependency

**Files:** Modify `requirements.txt`

- [ ] **Step 1: Append to `requirements.txt`** a new line:

```
num2words>=0.5.13
```

- [ ] **Step 2: Verify it imports** — `./.venv/Scripts/python.exe -c "from num2words import num2words; print(num2words(1801, to='year'))"` → prints `eighteen oh-one`.

- [ ] **Step 3: Commit** — `git add requirements.txt && git commit -m "chore: add num2words dependency"`

---

## Task 2: Normalization engine (`pipeline/normalize.py`)

**Files:** Create `pipeline/normalize.py`, `tests/test_normalize.py`

- [ ] **Step 1: Write the failing tests** — create `tests/test_normalize.py`:

```python
from pipeline.normalize import (
    expand_numbers, expand_abbreviations, apply_pronunciations, normalize_text,
    BUILTIN_PRONUNCIATIONS,
)


def test_expand_year():
    assert "eighteen oh-one" in expand_numbers("It was 1801 then.")


def test_expand_cardinal():
    assert "forty-two" in expand_numbers("There were 42 men.")


def test_expand_ordinal():
    assert "third" in expand_numbers("the 3rd of May")


def test_numbers_skip_currency_time_decimal():
    assert expand_numbers("$5 at 3:30 costs 3.5") == "$5 at 3:30 costs 3.5"


def test_abbreviations_basic():
    assert expand_abbreviations("Mr. Smith and Dr Jones") == "Mister Smith and Doctor Jones"


def test_abbreviations_case_insensitive():
    assert expand_abbreviations("mrs Murphy") == "Missus Murphy"


def test_ampersand():
    assert expand_abbreviations("Smith & Co") == "Smith and Co"


def test_pronunciations_whole_word_only():
    rules = {"foo": "bar"}
    # replaces the standalone word, not the substring inside "foofighter"
    assert apply_pronunciations("FOO foofighter", rules) == "bar foofighter"


def test_pronunciations_empty_rules_noop():
    assert apply_pronunciations("hello", {}) == "hello"


def test_normalize_text_custom_overrides_builtin():
    # pick any built-in key and override it
    key = next(iter(BUILTIN_PRONUNCIATIONS))
    out = normalize_text(key.capitalize(), custom_rules={key: "OVERRIDDEN"})
    assert "OVERRIDDEN" in out


def test_normalize_text_runs_all_layers():
    rules = {"smith": "Smyth"}
    out = normalize_text("Mr Smith owed 42 pounds in 1801.", custom_rules=rules)
    assert "Mister" in out and "Smyth" in out and "forty-two" in out and "eighteen oh-one" in out
```

- [ ] **Step 2: Run to verify fail** — `./.venv/Scripts/python.exe -m pytest tests/test_normalize.py -v` → FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement `pipeline/normalize.py`:**

```python
"""Normalize text before TTS: numbers, abbreviations, and pronunciations."""
import re

from num2words import num2words

# Unambiguous abbreviations only (skip "St" — Saint vs Street).
ABBREVIATIONS = {
    "mr": "Mister", "mrs": "Missus", "ms": "Miss", "dr": "Doctor",
    "capt": "Captain", "lt": "Lieutenant", "col": "Colonel", "sgt": "Sergeant",
    "gen": "General", "rev": "Reverend", "hon": "Honourable",
}

# Starter respellings for the Cork novel's tricky names/places. Plain phonetic
# spellings (no IPA); the user overrides via the Pronounce tab. Keys lowercase.
BUILTIN_PRONUNCIATIONS = {
    "carrigaline": "Carrig a line",
    "owenabue": "Owen a boo",
    "shanbally": "Shan bally",
    "mardyke": "Mar dyke",
    "fitzgibbon": "Fitz gibbon",
    "zubieta": "Zoo bee eta",
    "hegarty": "Heg arty",
    "hanratty": "Han ratty",
    "danaher": "Dan a her",
}

_NUM_RE = re.compile(r"(?<![\$\d.:])\b(\d+)(st|nd|rd|th)?\b(?![\d.:%])", re.IGNORECASE)


def expand_numbers(text: str) -> str:
    def repl(m):
        digits, ordinal = m.group(1), m.group(2)
        n = int(digits)
        try:
            if ordinal:
                return num2words(n, to="ordinal")
            if len(digits) == 4 and 1500 <= n <= 2099:
                return num2words(n, to="year")
            return num2words(n)
        except Exception:
            return m.group(0)
    return _NUM_RE.sub(repl, text)


_ABBR_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in ABBREVIATIONS) + r")\b\.?",
    re.IGNORECASE,
)


def expand_abbreviations(text: str) -> str:
    text = re.sub(r"(?<=\s)&(?=\s)", "and", text)  # standalone ampersand
    return _ABBR_RE.sub(lambda m: ABBREVIATIONS[m.group(1).lower()], text)


def apply_pronunciations(text: str, rules: dict) -> str:
    if not rules:
        return text
    keys = sorted(rules.keys(), key=len, reverse=True)  # longest-first
    pattern = re.compile(r"\b(" + "|".join(re.escape(k) for k in keys) + r")\b",
                         re.IGNORECASE)
    return pattern.sub(lambda m: rules[m.group(1).lower()], text)


def normalize_text(text: str, custom_rules: dict | None = None) -> str:
    merged = {**BUILTIN_PRONUNCIATIONS,
              **{k.lower(): v for k, v in (custom_rules or {}).items()}}
    text = expand_numbers(text)
    text = expand_abbreviations(text)
    text = apply_pronunciations(text, merged)
    return text
```

- [ ] **Step 4: Run to verify pass** — `./.venv/Scripts/python.exe -m pytest tests/test_normalize.py -v` → all pass (11).

- [ ] **Step 5: Commit** — `git add pipeline/normalize.py tests/test_normalize.py && git commit -m "feat: text normalization engine (numbers, abbreviations, pronunciations)"`

---

## Task 3: Pronunciation store (`backend/pronunciations.py`)

**Files:** Create `backend/pronunciations.py`, `tests/test_pronunciations.py`

- [ ] **Step 1: Write the failing tests** — create `tests/test_pronunciations.py`:

```python
from backend.pronunciations import PronunciationStore


def test_set_get_remove(tmp_path):
    store = PronunciationStore(str(tmp_path / "p.json"))
    assert store.get_all() == {}
    store.set_rule("Carrigaline", "Carrig a line")
    assert store.get_all() == {"carrigaline": "Carrig a line"}  # key lowercased
    store.set_rule("carrigaline", "Carrig-a-leen")  # overwrite
    assert store.get_all()["carrigaline"] == "Carrig-a-leen"
    store.remove("CARRIGALINE")
    assert store.get_all() == {}


def test_remove_missing_is_idempotent(tmp_path):
    store = PronunciationStore(str(tmp_path / "p.json"))
    store.remove("nope")  # no error
    assert store.get_all() == {}


def test_persists_across_instances(tmp_path):
    p = str(tmp_path / "p.json")
    PronunciationStore(p).set_rule("Foo", "Bar")
    assert PronunciationStore(p).get_all() == {"foo": "Bar"}
```

- [ ] **Step 2: Run to verify fail** — `./.venv/Scripts/python.exe -m pytest tests/test_pronunciations.py -v` → FAIL.

- [ ] **Step 3: Implement `backend/pronunciations.py`:**

```python
"""Persistent global custom pronunciation rules (word -> say-as)."""
import json
import os


class PronunciationStore:
    def __init__(self, path: str):
        self.path = path

    def get_all(self) -> dict:
        if not os.path.isfile(self.path):
            return {}
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save(self, data: dict) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def set_rule(self, word: str, say_as: str) -> None:
        data = self.get_all()
        data[word.lower()] = say_as
        self._save(data)

    def remove(self, word: str) -> None:
        data = self.get_all()
        if data.pop(word.lower(), None) is not None:
            self._save(data)
```

- [ ] **Step 4: Run to verify pass** — `./.venv/Scripts/python.exe -m pytest tests/test_pronunciations.py -v` → all pass (3).

- [ ] **Step 5: Commit** — `git add backend/pronunciations.py tests/test_pronunciations.py && git commit -m "feat: pronunciation store persistence"`

---

## Task 4: Wire normalization into render

**Files:** Modify `backend/render.py`; modify `tests/test_render.py`

- [ ] **Step 1: Add the failing test** — append to `tests/test_render.py`:

```python
def test_render_applies_custom_pronunciations(tmp_path):
    lib = Library(str(tmp_path))
    seen = []

    class SpySynth(FakeSynth):
        def synth_paragraphs(self, paragraphs, progress=None):
            for para in paragraphs:
                seen.extend(para)
            return super().synth_paragraphs(paragraphs)

    book = "## Chapter 1 - One\nThe foo sailed in 1801."
    render_audiobook(book_text=book, voice="af_heart", speed=1.0, title="T", author="",
                     cover_path=None, library=lib, job_id="jn", emit=lambda e: None,
                     synth_factory=SpySynth, custom_rules={"foo": "bar"})
    joined = " ".join(seen)
    assert "bar" in joined and "foo" not in joined
    assert "eighteen oh-one" in joined  # built-in number expansion also ran
```

- [ ] **Step 2: Run to verify fail** — `./.venv/Scripts/python.exe -m pytest tests/test_render.py::test_render_applies_custom_pronunciations -v` → FAIL (unexpected keyword `custom_rules`).

- [ ] **Step 3: Edit `backend/render.py`.**

(a) Add the import after the existing pipeline imports:
```python
from pipeline.normalize import normalize_text
```

(b) Change `render_audiobook`'s signature. Find:
```python
def render_audiobook(*, book_text, voice, speed, title, author, cover_path,
                     library, job_id, emit, synth_factory=Synthesizer) -> dict:
```
Replace with:
```python
def render_audiobook(*, book_text, voice, speed, title, author, cover_path,
                     library, job_id, emit, synth_factory=Synthesizer,
                     custom_rules=None) -> dict:
```

(c) Pass it through to `_render_into`. Find:
```python
        return _render_into(workdir, chapters, voice=voice, speed=speed, title=title,
                            author=author, cover_path=cover_path, library=library,
                            job_id=job_id, emit=emit, synth_factory=synth_factory)
```
Replace with:
```python
        return _render_into(workdir, chapters, voice=voice, speed=speed, title=title,
                            author=author, cover_path=cover_path, library=library,
                            job_id=job_id, emit=emit, synth_factory=synth_factory,
                            custom_rules=custom_rules)
```

(d) Change `_render_into`'s signature. Find:
```python
def _render_into(workdir, chapters, *, voice, speed, title, author, cover_path,
                 library, job_id, emit, synth_factory) -> dict:
```
Replace with:
```python
def _render_into(workdir, chapters, *, voice, speed, title, author, cover_path,
                 library, job_id, emit, synth_factory, custom_rules=None) -> dict:
```

(e) Normalize each chapter. Find:
```python
        audio = synth.synth_paragraphs(chunk_paragraphs(ch.text))
```
Replace with:
```python
        audio = synth.synth_paragraphs(chunk_paragraphs(normalize_text(ch.text, custom_rules)))
```

- [ ] **Step 4: Run to verify pass** — `./.venv/Scripts/python.exe -m pytest tests/test_render.py -v` → all pass.

- [ ] **Step 5: Commit** — `git add backend/render.py tests/test_render.py && git commit -m "feat: apply normalization + custom pronunciations in render"`

---

## Task 5: Pronunciation + normalize-preview endpoints

**Files:** Modify `server.py`; modify `tests/test_api.py`

- [ ] **Step 1: Add the failing tests** — append to `tests/test_api.py`:

```python
def test_pronunciations_crud(client):
    base = client.get("/api/pronunciations").json()
    assert "builtin" in base and "custom" in base
    assert base["custom"] == {}
    r = client.put("/api/pronunciations/Carrigaline", json={"sayAs": "Carrig a line"})
    assert r.status_code == 200 and r.json()["custom"]["carrigaline"] == "Carrig a line"
    d = client.request("DELETE", "/api/pronunciations/carrigaline")
    assert d.status_code == 200 and d.json()["custom"] == {}


def test_pronunciation_put_rejects_empty(client):
    assert client.put("/api/pronunciations/x", json={"sayAs": "  "}).status_code == 400


def test_normalize_preview(client):
    r = client.post("/api/normalize-preview", json={"text": "Mr Smith in 1801"})
    assert r.status_code == 200
    out = r.json()["normalized"]
    assert "Mister" in out and "eighteen oh-one" in out


def test_render_uses_custom_pronunciations(client, monkeypatch):
    import server
    monkeypatch.setattr(server, "SYNTH_FACTORY", _FakeSynth)
    server.pron.set_rule("foo", "bar")  # persisted into the per-test library dir's data file
    # render path threads pron.get_all() into render; just confirm the request succeeds
    r = client.post("/api/render", json={"bookText": "## A\n\nThe foo.", "voice": "af_heart", "title": "P"})
    assert r.status_code == 200
```

NOTE: the `client` fixture sets `T2A_LIBRARY_DIR` to a tmp path and reloads `server`. For pronunciations isolation, the test relies on `server.pron` writing to its configured path (see Step 3 — point `T2A_PRON_PATH` at the tmp dir by default-deriving it; here we just call `server.pron.set_rule` directly so it uses whatever path the reloaded module configured).

- [ ] **Step 2: Run to verify fail** — `./.venv/Scripts/python.exe -m pytest tests/test_api.py -k "pronunc or normalize" -v` → FAIL.

- [ ] **Step 3: Edit `server.py`.**

(a) Add imports near the other backend imports:
```python
from backend.pronunciations import PronunciationStore
from pipeline.normalize import normalize_text, BUILTIN_PRONUNCIATIONS
```

(b) Add a module global next to `library`/`jobs` (derive the pron path from the library dir so tests are isolated per-tmp-dir):
```python
PRON_PATH = os.environ.get("T2A_PRON_PATH", os.path.join(os.path.dirname(LIBRARY_DIR), "data", "pronunciations.json"))
pron = PronunciationStore(PRON_PATH)
```

(c) Add request models near the others:
```python
class PronRule(BaseModel):
    sayAs: str


class NormalizePreviewRequest(BaseModel):
    text: str
```

(d) Thread custom rules into the render target. Find, inside `start_render`'s `target`:
```python
            render_audiobook(book_text=req.bookText, voice=req.voice, speed=req.speed,
                             title=req.title, author=req.author, cover_path=None,
                             library=library, job_id=job_id, emit=emit,
                             synth_factory=SYNTH_FACTORY)
```
Replace with:
```python
            render_audiobook(book_text=req.bookText, voice=req.voice, speed=req.speed,
                             title=req.title, author=req.author, cover_path=None,
                             library=library, job_id=job_id, emit=emit,
                             synth_factory=SYNTH_FACTORY, custom_rules=pron.get_all())
```

(e) Add these routes immediately BEFORE the `# IMPORTANT: keep this static mount` comment:
```python
@app.get("/api/pronunciations")
def pronunciations_list():
    return {"builtin": BUILTIN_PRONUNCIATIONS, "custom": pron.get_all()}


@app.put("/api/pronunciations/{word}")
def pronunciations_set(word: str, rule: PronRule):
    if not rule.sayAs.strip():
        raise HTTPException(status_code=400, detail="sayAs is required")
    pron.set_rule(word, rule.sayAs.strip())
    return {"custom": pron.get_all()}


@app.delete("/api/pronunciations/{word}")
def pronunciations_remove(word: str):
    pron.remove(word)
    return {"custom": pron.get_all()}


@app.post("/api/normalize-preview")
def normalize_preview(req: NormalizePreviewRequest):
    return {"normalized": normalize_text(req.text, pron.get_all())}
```

- [ ] **Step 4: Run to verify pass** — `./.venv/Scripts/python.exe -m pytest tests/test_api.py -v` → all pass.

- [ ] **Step 5: Run the FULL suite** — `./.venv/Scripts/python.exe -m pytest -q` → all pass (1 skipped GPU smoke). Report the count.

- [ ] **Step 6: Commit** — `git add server.py tests/test_api.py && git commit -m "feat: pronunciation + normalize-preview endpoints"`

---

## Task 6: Pronounce tab UI

**Files:** Modify `web/index.html`, `web/js/app.js`; create `web/js/pronounce.js`. Verified by serving + the controller's browser pass.

- [ ] **Step 1: Edit `web/index.html`.**

(a) Add a `Pronounce` tab button. Find:
```html
      <button class="tab" data-tab="voices">Voices</button>
```
and add immediately after it (still inside the `<nav class="tabs">`):
```html
      <button class="tab" data-tab="pronounce">Pronounce</button>
```

(b) Add the tab pane. Find:
```html
    <section id="tab-library" class="tabpane"></section>
```
and add immediately after it:
```html
    <section id="tab-pronounce" class="tabpane"></section>
```

(c) Add the script. Find:
```html
  <script src="/js/library.js"></script>
```
and add immediately after it:
```html
  <script src="/js/pronounce.js"></script>
```

- [ ] **Step 2: Edit `web/js/app.js`** — in `showTab`, add routing for the pronounce tab. Find:
```javascript
    if (name === "library") Library.render();
    if (name === "create") Create.render();
```
Replace with:
```javascript
    if (name === "library") Library.render();
    if (name === "create") Create.render();
    if (name === "pronounce") Pronounce.render();
```

- [ ] **Step 3: Create `web/js/pronounce.js`:**

```javascript
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
    // minimal inline styling so .pinput matches the dark theme fields
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
      `<div class="filerow"><span class="nm">${w} → ${s}</span><button class="x" data-w="${w}">✕</button></div>`).join("")
      : `<span class="muted">No custom rules yet — add one above.</span>`;
    cwrap.querySelectorAll(".x").forEach(b => b.onclick = async () => {
      await T2A.api(`/api/pronunciations/${encodeURIComponent(b.dataset.w)}`, { method: "DELETE" });
      this.refresh();
    });
    document.getElementById("pbuiltin").textContent =
      Object.entries(d.builtin).map(([w, s]) => `${w} → ${s}`).join("   ·   ");
  },

  async add() {
    const w = document.getElementById("pw").value.trim();
    const s = document.getElementById("ps").value.trim();
    if (!w || !s) { T2A.toast("Enter both a word and how to say it"); return; }
    await T2A.api(`/api/pronunciations/${encodeURIComponent(w)}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sayAs: s }) });
    document.getElementById("pw").value = "";
    document.getElementById("ps").value = "";
    T2A.toast("Rule added"); this.refresh();
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
```

- [ ] **Step 4: Verify it serves** — start the server (no browser) and confirm the new files load:

Run (PowerShell): `$env:T2A_NO_BROWSER=1; Start-Process -NoNewWindow ./.venv/Scripts/python.exe server.py; Start-Sleep 3; (Invoke-WebRequest http://127.0.0.1:8765/js/pronounce.js).StatusCode; (Invoke-WebRequest http://127.0.0.1:8765/).Content.Contains("Pronounce"); Get-Process python | Stop-Process`
Expected: `200` and `True`.

- [ ] **Step 5: Commit** — `git add web/index.html web/js/app.js web/js/pronounce.js && git commit -m "feat: Pronounce tab UI"`

---

## Task 7: End-to-end verification

**Files:** none (verification only).

- [ ] **Step 1: Full suite** — `./.venv/Scripts/python.exe -m pytest -q` → all pass (1 skipped GPU smoke).

- [ ] **Step 2: Live check (controller, via the running server + Playwright MCP or API).** Start the server (with espeak env), then:
- `POST /api/normalize-preview {"text":"Mr O'Brien sailed from Carrigaline in 1801."}` → confirm `Mister`, `Carrig a line`, `eighteen oh-one` in the result.
- Add a custom rule via `PUT /api/pronunciations/Owenabue {"sayAs":"Oona boo"}`, then `GET /api/pronunciations` shows it under `custom`; normalize-preview of "Owenabue" now returns "Oona boo".
- Render a tiny book containing "1801" and a built-in name; confirm it completes (the text reaching synthesis is normalized — already covered by the render unit test).
Stop the server when done.

- [ ] **Step 3: No commit** (verification only).

---

## Self-review notes (addressed)

- **Spec coverage:** num2words dep (T1), normalize engine with all three layers + built-ins (T2), store (T3), render wiring via `custom_rules` (T4), endpoints incl. normalize-preview + render threading + empty-sayAs 400 (T5), Pronounce tab with add/remove/test (T6), e2e (T7). All spec sections map to a task.
- **Type/interface consistency:** `normalize_text(text, custom_rules)`, `ABBREVIATIONS`/`BUILTIN_PRONUNCIATIONS`, `PronunciationStore.get_all/set_rule/remove`, `render_audiobook(..., custom_rules=None)`, endpoint shapes (`{builtin,custom}`, `{normalized}`, `{custom}`), and `Pronounce.render()` are used identically across tasks and the UI reads exactly those response keys.
- **Isolation:** the per-test `client` fixture sets `T2A_LIBRARY_DIR` to a tmp dir and reloads `server`; `PRON_PATH` derives from `LIBRARY_DIR`'s parent so each test gets its own `data/pronunciations.json` — no cross-test bleed.
- **No placeholders:** every code/test step is complete and runnable.
- **Out of scope (per spec):** per-book rules, auto-detect, audio test, IPA, re-normalizing old renders.
```
