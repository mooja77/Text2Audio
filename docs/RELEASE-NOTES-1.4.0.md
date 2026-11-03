# Text2Audio 1.4.0

Text2Audio is a free audiobook studio that runs on your own computer. This
release makes it clearer what you can and can't do with cloned voices. It also
keeps it fully offline once the voice model is downloaded, and makes it easier
to use with a keyboard, a screen reader or a magnifier.

## What's new

**Voice cloning tells you its licence.** Cloning uses the F5-TTS model, whose
weights are licensed CC-BY-NC-4.0: non-commercial use only. The clone panel now
says so, and asks you to tick a box once before you clone a voice or narrate with
one. Books made with a cloned voice are marked "do not sell" in your Library.
The built-in Kokoro narrators have no such limit (Apache-2.0).

**Really offline after the first download.** Once the voice model is on your
computer, Text2Audio stops contacting the internet. On a computer with no
connection, starting a render took about 3.5 minutes in 1.3.0 while it retried
the download server. It now takes about 25 seconds. If you pick a narrator you
haven't used before while online, that one voice is still downloaded.

**Easier to use.** You can do everything with the keyboard. Focus is always
visible. Progress and errors are announced to screen readers. Links and buttons
meet WCAG 2.2 AA contrast. Checked with axe-core across every tab: 0 issues.

**Help when something's missing.** A short checklist at the top shows whether the
audio tool, the pronunciation tool, the voice model and enough disk space are in
place, with one next step for anything that isn't. Error messages are now
written in plain English.

**Licences in the app.** Help now lists every model and library Text2Audio uses,
with its licence and a link to the source. The full record, checked against each
project's own licence file on 3 November 2026, is in `docs/LICENSES.md`.

**Safer by default.** The app only ever listens on your own computer
(`127.0.0.1`), and the health check reports this.

## For developers

- An unknown narrator voice now returns **HTTP 422** (was 400) on `/api/render`,
  `/api/render-upload` and `/api/voice-preview`. The body keeps `detail` and adds
  `error` and `voice`.
- New: `GET/POST /api/clone-consent`, `GET /api/licenses`, and `bind`, `checklist`
  and `ready` in `GET /api/health`.
- Test suite: 168 passed, 2 skipped (1.3.0: 135).

See `CHANGELOG.md` for the full list.

## Thanks

Kokoro-82M by hexgrad (Apache-2.0); F5-TTS by Yushen Chen et al. (code MIT,
weights CC-BY-NC-4.0); Vocos by Charactr (MIT); eSpeak NG (GPL-3.0); ffmpeg.
