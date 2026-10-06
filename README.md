# Coelho Transcriber – Lite

> A small, **vibe-coded** tool for transcribing audio through cloud APIs
> (AssemblyAI / Deepgram), built with Python and PyQt6.

Coelho Transcriber Lite is a desktop GUI (Windows) that sends interview-style
audio files to a speech-to-text API and gives you back a speaker-labelled
transcript. It was written for sociolinguistic interview work (Brazilian
Portuguese by default), but works for any audio the APIs support.

> ⚠️ **Disclaimer:** this project was built "by vibes" with AI assistance. It is
> a personal utility, provided as-is, with no warranty. Review the code before
> relying on it for anything important.

## Features

- Transcription via **AssemblyAI** and **Deepgram** (bring your own API key)
- Speaker diarization (speaker labels)
- Dark / light theme and adjustable font size
- Runs transcription in background threads (the UI never freezes)
- Supports `.mp3 .wav .m4a .mp4 .mkv .ogg .aac .flac .opus .webm .wma .mov`

## Quick start (Windows release)

1. Download the release zip from the **Releases** page and extract it.
2. Run `Instalar_Coelho_Lite.bat` (asks for admin rights; installs to
   `C:\Program Files\Coelho Lite` and creates a desktop shortcut), **or** run
   `CoelhoTranscriber\CoelhoTranscriber.exe` directly.
3. Open the app and paste your API key(s) in the settings.
   Keys are stored **locally** in
   `Documents\Coelho95 Transcriber\config.json` – never inside the app folder.

Use `Desinstalar_Coelho_Lite.bat` to uninstall.

## Run from source

```bash
git clone https://github.com/saulorrp/coelho_transcriber_lite.git
cd coelho_transcriber_lite
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main_gui.py
```

Optionally, set `ASSEMBLYAI_API_KEY` as an environment variable (or use a local
`.env` file, see `.env.example`).

## Build the executable

```bash
pip install pyinstaller
pyinstaller --noconfirm CoelhoTranscriber.spec
```

The output is created in `dist/CoelhoTranscriber/`.

## API keys & security

- **No API keys are included in this repository or in the release.**
- You need your own keys from [AssemblyAI](https://www.assemblyai.com/) and/or
  [Deepgram](https://deepgram.com/).
- Keys you enter in the app are saved only on your machine
  (`Documents\Coelho95 Transcriber\config.json`).
- `config.json` and `.env` are git-ignored. Never commit them.

## Project layout

```
main_gui.py                  Main window (legacy, large)
components/                  Transcription workers, API clients, icons
CoelhoTranscriber.spec       PyInstaller build spec
requirements.txt             Python dependencies
docs/                        Extra documentation
```

## License

MIT – see [LICENSE](LICENSE).
