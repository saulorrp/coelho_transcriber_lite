# Publishing Guide

## Commit the source
The `release/` folder is git-ignored on purpose (binaries are large).

```bash
git init
git add .
git commit -m "Initial public release"
git branch -M main
git remote add origin https://github.com/saulorrp/coelho_transcriber_lite.git
git push -u origin main
```

## Publish the binary
1. On GitHub: **Releases → Draft a new release**, tag `v1.0.0`.
2. Attach `release/Coelho_Lite_Release.zip`.
3. Paste the release notes (suggested below).

### Suggested release notes
> **Coelho Transcriber Lite v1.0.0** – a small vibe-coded Windows tool for
> audio transcription via AssemblyAI / Deepgram.
> Extract the zip, run `Instalar_Coelho_Lite.bat` (or the `.exe` directly) and
> paste your own API key in the app. No keys are bundled.

## Pre-publish checklist
- [x] No API keys in source, release, or git-ignored files
- [x] `config.json` not bundled in the executable
- [ ] Only commit/upload from this folder; never from the old project folder
- [ ] Replace `saulorrp/coelho_transcriber_lite` placeholders and the LICENSE name
