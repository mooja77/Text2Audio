# Text2Audio help

Use your browser's page search (`Ctrl+F` or `Cmd+F`) here, or open the searchable **Help** tab in Text2Audio Studio.

## Start in five steps

1. Add `.txt`, Markdown, DOCX, EPUB or text-based PDF files. **Use safe example** is available in the Create tab.
2. Check the detected chapters and their order.
3. Choose and preview a narrator.
4. Generate, leaving the Text2Audio process open.
5. Listen to the finished `.m4b` in Library.

Experienced users can skip the guide and install with `pip`; the [README](../README.md) has the fast path.

## Recovery

An active render continues if only the browser page is refreshed. The page stores the non-sensitive job ID and reconnects to the server's event history. If the Text2Audio process itself stops, start that render again. Finished books remain in `library/` with durable manifests.

Text2Audio remembers title, author, voice, speed and guide progress in local browser storage. It deliberately does not store manuscript text there.

## Common problems

- **Browser did not open:** visit <http://127.0.0.1:8765> while Text2Audio is running.
- **ffmpeg or espeak-ng missing:** rerun the installer, or install both and restart.
- **Slow generation:** CPU works slowly; try the short safe example or an NVIDIA GPU.
- **Wrong device selected:** set `T2A_DEVICE` to `cuda`, `mps`, or `cpu` before starting.
- **Need to stop:** use **Cancel render**; completed books and prior remasters remain intact.
- **Publishing:** use the quality report and chapter export in Library. Distribution
  presets still require editorial listening and the distributor's own validation.
- **"Unknown voice" when generating:** the chosen narrator is no longer available (for example a cloned voice was deleted). Pick another narrator and generate again; nothing was added to your library.
- **Wrong pronunciation:** add a rule in the Pronounce tab, preview, and regenerate.
- **First model download:** the first narration downloads model files; later runs use the local cache. Once the model is cached, restart Text2Audio and it runs in offline mode: rendering makes no network connections.

## Accessibility

Studio can be used with the keyboard alone: Tab / Shift+Tab move between controls, Enter or Space activates them, and the arrow keys switch tabs. A **Skip to main content** link appears on the first Tab. The five-step beginner guide, file dropzone, library cards and chapter rows are all keyboard-operable, and the focused control always has a visible outline. Render progress is announced politely and errors are announced immediately to screen readers. Colours are chosen to meet WCAG 2.2 AA contrast.

## Licences

The Help tab lists every model and library Text2Audio uses, with its licence and a link to the source. Kokoro narration is Apache-2.0; the optional F5-TTS cloning weights are CC-BY-NC-4.0 (non-commercial). The list is served locally at `GET /api/licenses` and is read from the verified table in [LICENSES.md](LICENSES.md).

## Privacy and safe support

The server binds to `127.0.0.1`. Manuscripts, generated audio, cloned voices, and manifests stay on this computer. Text2Audio has no account system, telemetry, lifecycle email, or hosted processing.

GitHub issues are public. Do not attach private manuscripts, cloned voices, copyrighted source text, or logs containing private text. Use the synthetic example or another tiny synthetic reproduction.

- [Ask for help](https://github.com/mooja77/Text2Audio/issues/new?template=bug_report.yml)
- [Request a feature](https://github.com/mooja77/Text2Audio/issues/new?template=feature_request.yml)
