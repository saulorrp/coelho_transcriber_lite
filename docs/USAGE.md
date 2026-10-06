# Usage Guide

## 1. Get an API key
- AssemblyAI: https://www.assemblyai.com/ (dashboard → API key)
- Deepgram: https://deepgram.com/ (console → API keys)

## 2. Configure
Open the app and enter your key(s) in the settings. They are saved to
`%USERPROFILE%\Documents\Coelho95 Transcriber\config.json`
(example structure below – keep this file private):

```json
{
  "api_key": "<assemblyai key>",
  "deepgram_api_key": "<deepgram key>",
  "transcription_mode": "cloud_deepgram",
  "theme": "dark",
  "font_size": 13
}
```

## 3. Transcribe
1. Add one or more audio/video files.
2. Choose the transcription mode (AssemblyAI or Deepgram).
3. Start. Results are written to
   `Documents\Coelho95 Transcriber\output da transcricao`.

## Notes
- Audio is processed in background threads; large files may take a while.
- Cloud APIs are billed by your provider according to audio duration.
- See `components/CHANGELOG.txt` for the project history.
