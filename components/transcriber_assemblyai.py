import os, sys, time, json
import httpx
import assemblyai as aai
from typing import List, Tuple, Dict

# ── AssemblyAI API Key ───────────────────────────────────────────────────────
# Never hardcode credentials. The key is provided by the GUI (config.json in the
# user's Documents folder) or via the ASSEMBLYAI_API_KEY environment variable.
aai.settings.api_key = os.environ.get("ASSEMBLYAI_API_KEY", "")

# ── HTTP Timeout ─────────────────────────────────────────────────────────────
aai.settings.http_timeout = httpx.Timeout(connect=300.0, read=300.0, write=300.0, pool=600.0)

# ── Constants ────────────────────────────────────────────────────────────────
AUDIO_EXTENSIONS = (
    '.mp4', '.wav', '.m4a', '.mp3', '.mkv', '.ogg',
    '.aac', '.flac', '.opus', '.webm', '.wma', '.mov'
)

SHORT_SEGMENT_THRESHOLD = 1.5
PROMPT_FILLERS = {"uhum", "hum", "ahn", "tá", "né", "pois", "então", "capaz"}
LOW_CONFIDENCE_THRESHOLD = 0.70

# ── AssemblyAI Transcription Config (Gold Standard) ──────────────────────────
TRANSCRIPTION_CONFIG = aai.TranscriptionConfig(
    speech_models=["universal-3-5-pro", "universal-2"],
    language_code="pt",
    speaker_labels=True,
    disfluencies=True,
    prompt="Entrevista sociolinguística em português brasileiro, projeto VARSUL/FLP, Santa Catarina.",
    keyterms_prompt=[
        "Florianópolis", "Santa Catarina", "VARSUL", "FLP",
        "uhum", "né", "tá", "então", "capaz", "pois é",
        "bah", "tchê", "tri", "guri", "guria",
    ],
)

MAX_RETRIES = 3
RETRY_BASE_DELAY = 10  # seconds

# ── LLM Formatting Settings ──────────────────────────────────────────────────
# Using Gemini 1.5 Flash via AssemblyAI LLM Gateway for low latency and low cost
LLM_GATEWAY_URL = "https://llm-gateway.assemblyai.com/v1/chat/completions"
LLM_MODEL = "gemini-1-5-flash"
LLM_CHUNK_SIZE = 50  # Number of utterances per LLM request
LLM_SYSTEM_PROMPT = """You are an expert sociolinguistic typist specializing in Brazilian Portuguese oral history corpora. Your task is to convert raw ASR speaker blocks into a standardized academic transcription format while preserving the requested time-coded block structure.

### TRANSCRIPTION RULES:

1. **Speaker Tags:**
   - Preserve the speaker tags exactly as they appear in the input (e.g., `F.`, `E.`, `O.`, `O1.`).
   - Output Format: `[MM:SS - MM:SS] Speaker. Text...`

2. **Sociolinguistic Annotations:**
   - Convert vocal hesitations ("eh", "uh", "hum", pauses) into `(hes)`.
   - Convert unintelligible or low-confidence audio markers (`[?]` or `[??]`) into `(inint)`.
   - Convert throat clearing, clicks, or hesitation noises into `(est)`.
   - Convert ambient background sounds into `(ruído)`, `(vozes)`, `(toss)`, or `(risos E)`.

3. **Disfluencies and Self-Corrections:**
   - Mark false starts and restarted phrases using brackets and dashes: `[phrase]- repeated phrase`.
   - Mark truncated words: `[<truncated->]- complete_word`.
   - Enclose low-confidence or uncertain words in parentheses and quotes: `("word")`.

4. **Contextual Semantic Correction:**
   - Correct phonetic ASR errors based on semantic context.
   - Preserve regional Portuguese dialect terms (`vergamota`, `guri`, `cruzeiros`, `tanso`).

5. **Output Constraints:**
   - Maintain the exact timestamp block ranges provided in the input.
   - Do NOT add introductory or concluding explanatory text. Output ONLY the formatted transcript lines.
   - Every line in your response must start with a timestamp block `[MM:SS - MM:SS]`.
"""


# ── Utility Functions ────────────────────────────────────────────────────────

def format_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"


def format_elapsed(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m}m {s}s"


def get_first_utterance(speaker_id: str, utterances: list) -> tuple:
    for utt in utterances:
        if utt.speaker == speaker_id:
            start_sec = utt.start / 1000.0
            return format_time(start_sec), utt.text.strip()
    return "??:??", ""


def build_speaker_map(utterances: list, f_speaker_id: str, academic_mode: bool = False) -> dict:
    seen = []
    for utt in utterances:
        spk = utt.speaker
        if spk and spk not in seen:
            seen.append(spk)
    others = [spk for spk in seen if spk != f_speaker_id]
    mapping = {f_speaker_id: "F."}

    # In academic mode, secondary speaker is E. (Entrevistador)
    other_prefix = "E" if academic_mode else "O"

    for i, spk_id in enumerate(others):
        mapping[spk_id] = f"{other_prefix}." if i == 0 else f"{other_prefix}{i}."
    return mapping


def flag_low_confidence(utterance) -> str:
    start_sec = utterance.start / 1000.0
    end_sec = utterance.end / 1000.0
    duration = end_sec - start_sec
    text = utterance.text.strip().lower()
    words_set = {w.strip("?.,!") for w in text.split()}

    if words_set and words_set.issubset(PROMPT_FILLERS) and duration < SHORT_SEGMENT_THRESHOLD:
        return "  [??]"

    word_objects = utterance.words
    if word_objects:
        confidences = [w.confidence for w in word_objects if w.confidence is not None]
        if confidences and (sum(confidences) / len(confidences)) < LOW_CONFIDENCE_THRESHOLD:
            return "  [?]"

    return ""


def compute_confidence_stats(utterances: list) -> dict:
    all_confidences = []
    for utt in utterances:
        if utt.words:
            for w in utt.words:
                if w.confidence is not None:
                    all_confidences.append(w.confidence)
    if not all_confidences:
        return {"total_words": 0, "avg": 0.0, "min": 0.0, "below_threshold": 0}
    return {
        "total_words": len(all_confidences),
        "avg": sum(all_confidences) / len(all_confidences),
        "min": min(all_confidences),
        "below_threshold": sum(1 for c in all_confidences if c < LOW_CONFIDENCE_THRESHOLD),
    }


def step(n, total, msg):
    print(f"  [{n}/{total}] {msg}")


# ── Advanced Processing Functions ────────────────────────────────────────────

def detect_hallucination_loops(utterances: list) -> list:
    """Detect and collapse repeating n-gram loops within short windows."""
    cleaned = []
    loops_pruned = 0
    
    for utt in utterances:
        words = utt.text.split()
        if len(words) < 6:
            cleaned.append(utt)
            continue
            
        # Very naive n-gram loop detection for hallucination crashes
        # Real implementation would use AAI word-level timestamps to detect static loops
        # But for text-only, we check for massive repetition
        phrase = " ".join(words[:4]).lower()
        count = utt.text.lower().count(phrase)
        
        if count > 3 and len(words) > 15:
            # Likely a hallucination loop, truncate it
            utt.text = " ".join(words[:10]) + " [repetição cortada]"
            loops_pruned += 1
            
        cleaned.append(utt)
        
    if loops_pruned > 0:
        print(f"  ℹ  Pruned {loops_pruned} hallucination loops from transcript.")
        
    return cleaned


def calculate_speaker_durations(utterances: list) -> Dict[str, float]:
    """Calculate total speaking duration per speaker label in seconds."""
    durations = {}
    for utt in utterances:
        if utt.speaker:
            duration = (utt.end - utt.start) / 1000.0
            durations[utt.speaker] = durations.get(utt.speaker, 0.0) + duration
    return durations


def select_f_speaker(utterances: list, non_interactive: bool = False) -> str:
    seen = []
    for utt in utterances:
        spk = utt.speaker
        if spk and spk not in seen:
            seen.append(spk)

    if not seen:
        raise RuntimeError("No speakers detected.")

    if len(seen) == 1 or non_interactive:
        chosen = seen[0]
        if len(seen) == 1:
            print(f"\n  Only one speaker detected – assigning as F automatically.\n")
        else:
            print(f"\n  Non-interactive mode – assigning first speaker {chosen} as F.\n")
        return chosen

    # Calculate likely F speaker based on total speaking duration
    durations = calculate_speaker_durations(utterances)
    likely_f = max(durations.items(), key=lambda x: x[1])[0]
    total_time = sum(durations.values())
    likely_f_pct = (durations[likely_f] / total_time) * 100 if total_time > 0 else 0

    print(f"\n  {'─'*54}")
    print("  Speakers detected:\n")
    for i, spk_id in enumerate(seen):
        ts, text = get_first_utterance(spk_id, utterances)
        dur = durations.get(spk_id, 0.0)
        dur_pct = (dur / total_time) * 100 if total_time > 0 else 0
        
        preview = (text[:60] + "…") if len(text) > 60 else text
        is_suggested = " ⬅ SUGERIDO (Falante Principal)" if spk_id == likely_f else ""
        
        print(f"    [{i}] {spk_id}  —  {dur_pct:.1f}% do tempo ({format_time(dur)}){is_suggested}")
        print(f'        "{preview}" (início em {ts})')
        print()

    print(f"  O palpite do sistema é que [{seen.index(likely_f)}] {likely_f} é o F. ({likely_f_pct:.1f}% de fala).")
    
    while True:
        choice = input(f"  Which speaker is F? (0–{len(seen)-1}) [default={seen.index(likely_f)}] → ").strip()
        
        if choice == "":
            chosen = likely_f
            print(f"\n  ✓  F assigned to {chosen} (default)\n")
            return chosen
            
        if choice.isdigit() and int(choice) in range(len(seen)):
            chosen = seen[int(choice)]
            print(f"\n  ✓  F assigned to {chosen}\n")
            return chosen
            
        print("  Invalid. Enter a number between 0 and", len(seen) - 1)


# ── LLM Gateway Processing ───────────────────────────────────────────────────

def format_academic_llm(raw_lines: List[str]) -> List[str]:
    """Run transcript lines through AssemblyAI's LLM Gateway for academic formatting."""
    formatted = []
    total_chunks = (len(raw_lines) + LLM_CHUNK_SIZE - 1) // LLM_CHUNK_SIZE
    
    print()
    for i in range(0, len(raw_lines), LLM_CHUNK_SIZE):
        chunk = raw_lines[i:i + LLM_CHUNK_SIZE]
        chunk_text = "".join(chunk)
        chunk_num = (i // LLM_CHUNK_SIZE) + 1
        
        print(f"    - Processando chunk {chunk_num}/{total_chunks} via LLM Gateway...")
        
        payload = {
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": LLM_SYSTEM_PROMPT},
                {"role": "user", "content": chunk_text}
            ],
            "temperature": 0.2
        }
        
        headers = {
            "authorization": aai.settings.api_key,
            "content-type": "application/json",
        }
        
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                # Use httpx for a unified timeout experience
                with httpx.Client(timeout=120.0) as client:
                    resp = client.post(LLM_GATEWAY_URL, json=payload, headers=headers)
                    resp.raise_for_status()
                    
                    data = resp.json()
                    result_text = data["choices"][0]["message"]["content"]
                    
                    # Ensure lines end with newline
                    if not result_text.endswith("\n"):
                        result_text += "\n"
                        
                    formatted.append(result_text)
                    break
                    
            except Exception as exc:
                if attempt < MAX_RETRIES:
                    time.sleep(2 ** attempt)
                else:
                    print(f"  ❌  LLM Gateway failed on chunk {chunk_num}: {exc}")
                    # Fallback: keep original raw chunk if LLM fails
                    formatted.append(chunk_text)
                    
    return formatted


# ── File Processing ──────────────────────────────────────────────────────────

def transcribe_with_retry(filepath: str) -> aai.Transcript:
    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            transcript = aai.Transcriber().transcribe(filepath, config=TRANSCRIPTION_CONFIG)
            return transcript
        except Exception as exc:
            last_exc = exc
            if attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                print(f"  ⚠️   Attempt {attempt}/{MAX_RETRIES} failed: {exc}")
                print(f"       Retrying in {delay}s…")
                time.sleep(delay)
            else:
                raise last_exc


def process_file(filepath, output_dir, non_interactive=False, academic_mode=False):
    total_steps = 4 if academic_mode else 3
    print()

    try:
        step(1, total_steps, "Uploading & transcribing via AssemblyAI (this may take a few minutes)…")
        t0 = time.monotonic()
        transcript = transcribe_with_retry(filepath)
        elapsed = time.monotonic() - t0

        if transcript.status == aai.TranscriptStatus.error:
            print(f"  ❌  AssemblyAI error: {transcript.error}")
            return

        utterances = transcript.utterances
        if not utterances:
            print("  ⚠️   No utterances returned by AssemblyAI.")
            return
            
        if academic_mode:
            utterances = detect_hallucination_loops(utterances)

        print(f"  ✓  Transcription complete in {format_elapsed(elapsed)}")

        # ── Confidence Statistics ────────────────────────────────────────
        stats = compute_confidence_stats(utterances)
        if stats["total_words"] > 0:
            print(f"  ℹ  Words: {stats['total_words']}  |  "
                  f"Avg confidence: {stats['avg']:.1%}  |  "
                  f"Min: {stats['min']:.1%}  |  "
                  f"Below {LOW_CONFIDENCE_THRESHOLD:.0%}: {stats['below_threshold']}")

        step(2, total_steps, "Assigning speakers…")
        f_speaker_id = select_f_speaker(utterances, non_interactive)
        speaker_map = build_speaker_map(utterances, f_speaker_id, academic_mode)

        print("  Final mapping:")
        for raw, label in speaker_map.items():
            ts, _ = get_first_utterance(raw, utterances)
            print(f"    {raw} → {label}  (first heard at {ts})")
        print()

        step(3, total_steps, "Generating raw transcript lines…")
        base_name = os.path.basename(filepath)
        out_name = os.path.splitext(base_name)[0] + ".txt"
        
        # If academic mode, save the raw one with a suffix
        if academic_mode:
            raw_out_name = os.path.splitext(base_name)[0] + "_raw.txt"
        else:
            raw_out_name = out_name
            
        raw_out_path = os.path.join(output_dir, raw_out_name)

        if os.path.exists(raw_out_path) and not non_interactive:
            overwrite = input(f"  Output file '{raw_out_name}' already exists. Overwrite? [y/n]: ").strip().lower()
            if overwrite != "y":
                print("  Skipped.\n")
                return

        raw_lines = []
        flagged = 0
        for utt in utterances:
            start = format_time(utt.start / 1000.0)
            end = format_time(utt.end / 1000.0)
            raw_id = utt.speaker if utt.speaker else "UNKNOWN"
            label = speaker_map.get(raw_id, "?.")
            text = utt.text.strip()
            flag = flag_low_confidence(utt)
            if flag:
                flagged += 1
            raw_lines.append(f"[{start} - {end}] {label} {text}{flag}\n")

        with open(raw_out_path, "w", encoding="utf-8") as f:
            f.writelines(raw_lines)

        if flagged:
            print(f"  ⚠️   {flagged} segment(s) flagged as low-confidence.")
        
        if not academic_mode:
            print(f"  ✅  Saved → {raw_out_path}\n")
            return
            
        print(f"  ✅  Saved raw transcript → {raw_out_path}")
        
        # ── LLM Formatting ──────────────────────────────────────────────
        step(4, total_steps, "Applying academic formatting via LLM Gateway…")
        
        academic_out_path = os.path.join(output_dir, out_name)
        academic_lines = format_academic_llm(raw_lines)
        
        with open(academic_out_path, "w", encoding="utf-8") as f:
            for block in academic_lines:
                f.write(block)
                
        print(f"  ✅  Saved academic transcript → {academic_out_path}\n")

    except Exception as exc:
        print(f"  ❌  Error processing '{filepath}': {exc}\n", file=sys.stderr)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    input_dir = "audios para transcricao"
    output_dir = "output da transcricao"
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    audio_files = sorted(
        os.path.join(input_dir, f)
        for f in os.listdir(input_dir)
        if f.lower().endswith(AUDIO_EXTENSIONS)
    )

    if not audio_files:
        print(f"No audio files found in the '{input_dir}' directory.")
        sys.exit(0)

    non_interactive = "--non-interactive" in sys.argv or "--auto-f" in sys.argv
    academic_mode = "--academic" in sys.argv

    print(r"""
                                                80  000                      
                                                800  008008                   
                                                0000 80   0000                
                                                80 00  80    000              
                                                808  00  01    800            
                                                 08    00 10     00            
                                                 000     00 08   808          
                                                  000      0000   00          
                                                   0008     00   808          
                                                     80000        8800        
                                                          8008         808      
                                                           001          801      
                                                          801            001    
                 008000    888                      00000                801    
               1108   8000088808000000888800000000001                     801    
                 00008                 88888                      00088 001    
                    80                                         00 88801      
                    00                                         001          
                  800                                         001            
             000008                                            0081          
         8000                    800000000000008088080008         80008      
     80000                      008              888   8008          80008  
  80000      000000008       080008                   800000000088    001 
  08    00008        800000008                                   80008  0011
  0000008                                                            8000001
    """)
    print(f"{'='*60}")
    print(f"  Coelho95 Transcriber  (AssemblyAI Cloud Edition)")
    print(f"{'='*60}")
    print(f"  Engine   : AssemblyAI Universal-3.5 Pro  (+ U2 fallback)")
    print(f"  Language : Portuguese (BR)  ·  Disfluencies ON")
    print(f"  Features : Speaker diarization · Contextual prompt")
    
    if academic_mode:
        print(f"  Pipeline : ACADEMIC (Hallucination Pruning + LLM Formatting)")
    
    print(f"  Files    : {len(audio_files)} audio file(s) found")
    if non_interactive:
        print(f"  Mode     : Non‑interactive (auto‑assign first speaker as F)")
    print(f"{'='*60}\n")

    for filepath in audio_files:
        print(f"\n{'─'*60}")
        print(f"  File: {filepath}")
        choice = "y" if non_interactive else input("  Transcribe this file? [y/n]: ").strip().lower()
        if choice != "y":
            print("  Skipped.\n")
            continue
        process_file(filepath, output_dir, non_interactive, academic_mode)

    print(f"\n{'='*60}")
    print("  All files processed. Done.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
