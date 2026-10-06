import os, sys, torch, whisperx, gc
from whisperx.diarize import DiarizationPipeline
from dotenv import load_dotenv

load_dotenv()
TOKEN_HF = os.getenv("TOKEN_HF")
LOW_CONFIDENCE_THRESHOLD = float(os.getenv("LOGPROB_THRESHOLD", "-1.0"))

AUDIO_EXTENSIONS = (
    '.mp4', '.wav', '.m4a', '.mp3', '.mkv', '.ogg',
    '.aac', '.flac', '.opus', '.webm', '.wma', '.mov'
)

force_cpu = "--cpu" in sys.argv
device = "cpu" if force_cpu else ("cuda" if torch.cuda.is_available() else "cpu")
compute_type = "int8" # Compressed to fit into 6GB VRAM

def format_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"

def get_first_utterance(speaker_id: str, segments: list) -> tuple:
    for seg in segments:
        if seg.get("speaker") == speaker_id:
            return format_time(seg["start"]), seg["text"].strip()
    return "??:??", ""

def build_speaker_map(segments: list, f_speaker_id: str) -> dict:
    seen = []
    for seg in segments:
        spk = seg.get("speaker")
        if spk and spk not in seen:
            seen.append(spk)
    others = [spk for spk in seen if spk != f_speaker_id]
    mapping = {f_speaker_id: "F."}
    
    for i, spk_id in enumerate(others):
        mapping[spk_id] = "O." if i == 0 else f"O{i}."
    return mapping

def resolve_unknown_segments(segments: list) -> None:
    known = [(seg["start"], seg["end"], seg["speaker"]) for seg in segments if seg.get("speaker")]
    for seg in segments:
        if seg.get("speaker"): continue
        if not known:
            seg["speaker"] = "UNKNOWN"
            continue
        mid = (seg["start"] + seg["end"]) / 2
        seg["speaker"] = min(known, key=lambda x: min(abs(x[0]-mid), abs(x[1]-mid)))[2]

SHORT_SEGMENT_THRESHOLD = 1.5
PROMPT_FILLERS = {"uhum", "hum", "ahn", "tá", "né", "pois", "então", "capaz"}

def flag_low_confidence(seg: dict) -> str:
    logprob = seg.get("avg_logprob")
    duration = seg.get("end", 0) - seg.get("start", 0)
    text = seg.get("text", "").strip().lower()
    words = {w.strip("?.,!") for w in text.split()}
    if words and words.issubset(PROMPT_FILLERS) and duration < SHORT_SEGMENT_THRESHOLD:
        return "  [??]"
    
    # Check avg_logprob first (if available from whisper)
    if logprob is not None and logprob < LOW_CONFIDENCE_THRESHOLD:
        return "  [?]"
    
    # If avg_logprob is lost after alignment, check word scores from whisperx
    seg_words = seg.get("words", [])
    if seg_words:
        scores = [w["score"] for w in seg_words if "score" in w]
        if scores and (sum(scores) / len(scores)) < 0.4:
            return "  [?]"
            
    return ""

def step(n, total, msg):
    print(f"  [{n}/{total}] {msg}")

def get_dynamic_batch_size() -> int:
    env_batch = os.getenv("BATCH_SIZE")
    if env_batch:
        try:
            bs = int(env_batch)
            print(f"  Using batch size {bs} (from .env)")
            return bs
        except ValueError: pass
    if device != "cuda":
        print("  Auto batch size: 2 (CPU mode)")
        return 2
    try:
        free_mem, _ = torch.cuda.mem_get_info()
        free_gb = free_mem / (1024**3)
        usable = max(0, free_gb - 0.5)
        batch_size = max(2, int(usable // 0.8))
        batch_size = min(batch_size, 32)
        print(f"  Auto batch size: {batch_size} (≈{free_gb:.1f} GB free VRAM)")
        return batch_size
    except Exception:
        print("  Could not query VRAM – using batch size 4")
        return 4

def select_f_speaker(segments: list, non_interactive: bool = False) -> str:
    seen = []
    for seg in segments:
        spk = seg.get("speaker")
        if spk and spk not in seen: seen.append(spk)
    if not seen: raise RuntimeError("No speakers detected.")
    if len(seen) == 1 or non_interactive:
        chosen = seen[0]
        print(f"\n  Only one speaker detected – assigning as F automatically.\n" if len(seen)==1
              else f"\n  Non-interactive mode – assigning first speaker {chosen} as F.\n")
        return chosen
    print(f"\n  {'─'*54}")
    print("  Speakers detected:\n")
    for i, spk_id in enumerate(seen):
        ts, text = get_first_utterance(spk_id, segments)
        preview = (text[:60] + "…") if len(text) > 60 else text
        print(f"    [{i}] {spk_id}  —  first heard at {ts}")
        print(f'        "{preview}"')
        print()
    while True:
        choice = input(f"  Which speaker is F? (0–{len(seen)-1}) → ").strip()
        if choice.isdigit() and int(choice) in range(len(seen)):
            chosen = seen[int(choice)]
            print(f"\n  ✓  F assigned to {chosen}\n")
            return chosen
        print("  Invalid. Enter a number between 0 and", len(seen)-1)

def load_transcription_model():
    print("  Loading Whisper large-v2 transcription model…")
    return whisperx.load_model("large-v2", device, compute_type=compute_type, language="pt",
        vad_options={"vad_onset": 0.500, "vad_offset": 0.500},
        asr_options={"beam_size": 1, "condition_on_previous_text": False})

def load_align_model():
    print("  Loading phonetic alignment model…")
    return whisperx.load_align_model(language_code="pt", device=device)

def load_diarization_model():
    print("  Loading Pyannote 3.1 diarization engine…")
    for kwarg in ("use_auth_token", "token", "auth_token"):
        try:
            return DiarizationPipeline("pyannote/speaker-diarization-3.1", device=device, **{kwarg: TOKEN_HF})
        except TypeError: continue
    raise RuntimeError("Could not init DiarizationPipeline – check TOKEN_HF and pyannote version.")

def process_file(filepath, output_dir, transcript_model, align_model, align_meta, diar_model, non_interactive=False):
    total_steps = 5
    print()
    try:
        batch_sz = get_dynamic_batch_size()
        step(1, total_steps, f"Transcribing audio (batch size {batch_sz})…")
        audio = whisperx.load_audio(filepath)
        result = transcript_model.transcribe(audio, batch_size=batch_sz)
        step(2, total_steps, "Running phonetic alignment…")
        result = whisperx.align(result["segments"], align_model, align_meta, audio, device, return_char_alignments=False)
        step(3, total_steps, "Running speaker diarization…")
        diarized = diar_model(audio, min_speakers=2, max_speakers=2)
        step(4, total_steps, "Assigning speakers…")
        final = whisperx.assign_word_speakers(diarized, result, fill_nearest=True)
        segments = final["segments"]
        resolve_unknown_segments(segments)
        f_speaker_id = select_f_speaker(segments, non_interactive)
        speaker_map = build_speaker_map(segments, f_speaker_id)
        print("  Final mapping:")
        for raw, label in speaker_map.items():
            ts, _ = get_first_utterance(raw, segments)
            print(f"    {raw} → {label}  (first heard at {ts})")
        print()
        step(5, total_steps, "Writing output file…")
        base_name = os.path.basename(filepath)
        out_name = os.path.splitext(base_name)[0] + ".txt"
        out_path = os.path.join(output_dir, out_name)
        if os.path.exists(out_path) and not non_interactive:
            overwrite = input(f"  Output file '{out_name}' already exists. Overwrite? [y/n]: ").strip().lower()
            if overwrite != "y":
                print("  Skipped.\n")
                return
        flagged = 0
        with open(out_path, "w", encoding="utf-8") as f:
            for seg in segments:
                start = format_time(seg["start"])
                end = format_time(seg["end"])
                raw_id = seg.get("speaker", "UNKNOWN")
                label = speaker_map.get(raw_id, "?.")
                text = seg["text"].strip()
                flag = flag_low_confidence(seg)
                if flag: flagged += 1
                f.write(f"[{start} - {end}] {label} {text}{flag}\n")
        if flagged:
            print(f"  ⚠️   {flagged} segment(s) flagged as low-confidence — review [?] / [??] markers in output.")
        print(f"  ✅  Saved → {out_path}\n")
        
    except Exception as exc:
        print(f"  ❌  Error processing '{filepath}': {exc}\n", file=sys.stderr)
        
    finally:
        # === MEMORY FLUSH LOGIC ===
        # Forcefully delete the heavy audio tensors from this specific loop
        try:
            del audio, result, diarized, final, segments
        except NameError:
            pass # Skips if the script crashed before these were created
            
        # Call the Python Garbage Collector to clear RAM
        gc.collect()
        
        # Tell the NVIDIA GPU to instantly dump the deleted files from VRAM
        if device == "cuda" or str(device) == "cuda":
            torch.cuda.empty_cache()

def main():
    if not TOKEN_HF or not TOKEN_HF.startswith("hf_"):
        print("\n" + "="*60)
        print("  ❌ ERROR: Invalid or missing Hugging Face Token.")
        print("  Please check your .env file and ensure TOKEN_HF is set correctly.")
        print("="*60 + "\n")
        sys.exit(1)
    input_dir = "audios para transcricao"
    output_dir = "output da transcricao"
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    audio_files = sorted(os.path.join(input_dir, f) for f in os.listdir(input_dir) if f.lower().endswith(AUDIO_EXTENSIONS))
    if not audio_files:
        print(f"No audio files found in the '{input_dir}' directory.")
        sys.exit(0)
    try:
        hw = torch.cuda.get_device_name(0) if device == "cuda" else ("CPU (Forced)" if force_cpu else "CPU")
    except Exception:
        hw = "CUDA (device name unavailable)" if device == "cuda" else "CPU"
    non_interactive = "--non-interactive" in sys.argv or "--auto-f" in sys.argv
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
    print(f"  Coelho95 Transcriber")
    print(f"{'='*60}")
    print(f"  Hardware : {hw}")
    print(f"  Files    : {len(audio_files)} audio file(s) found")
    if non_interactive:
        print(f"  Mode     : Non‑interactive (auto‑assign first speaker as F)")
    print(f"{'='*60}\n")
    transcript_model = load_transcription_model()
    align_model, align_meta = load_align_model()
    diar_model = load_diarization_model()
    for filepath in audio_files:
        print(f"\n{'─'*60}")
        print(f"  File: {filepath}")
        choice = "y" if non_interactive else input("  Transcribe this file? [y/n]: ").strip().lower()
        if choice != "y":
            print("  Skipped.\n")
            continue
        process_file(filepath, output_dir, transcript_model, align_model, align_meta, diar_model, non_interactive)
    print(f"\n{'='*60}")
    print("  All files processed. Done.")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()