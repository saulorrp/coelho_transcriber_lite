"""
TranscriptionWorker — QThread-based worker for cloud audio transcription.

Supports two cloud modes:
  • DEEPGRAM – Deepgram Nova-3 with diarization, ultrafast cloud processing
  • CLOUD   – AssemblyAI Universal-3.5 Pro with optional LLM academic formatting

All console output is routed through pyqtSignal(str) so the GUI can
display live logs in a QTextBrowser without freezing.
"""

import os
import sys
import gc
import time
import json
import threading
from typing import List, Dict, Optional, Tuple

from PyQt6.QtCore import QThread, pyqtSignal

# Ensure widgets directory is available
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIDGETS_DIR = os.path.join(BASE_DIR, "widgets")
if WIDGETS_DIR not in sys.path:
    sys.path.insert(0, WIDGETS_DIR)

try:
    from speaker_manager import save_speaker_metadata
except ImportError:
    save_speaker_metadata = None

# ── Constants (shared across both modes) ─────────────────────────────────────
AUDIO_EXTENSIONS = (
    '.mp4', '.wav', '.m4a', '.mp3', '.mkv', '.ogg',
    '.aac', '.flac', '.opus', '.webm', '.wma', '.mov'
)

SHORT_SEGMENT_THRESHOLD = 1.5
PROMPT_FILLERS = {"uhum", "hum", "ahn", "tá", "né", "pois", "então", "capaz"}
LOW_CONFIDENCE_THRESHOLD = 0.70

# ── AssemblyAI cloud-specific constants ──────────────────────────────────────
MAX_RETRIES = 3
RETRY_BASE_DELAY = 10

LLM_GATEWAY_URL = "https://llm-gateway.assemblyai.com/v1/chat/completions"
LLM_MODEL = "gemini-1-5-flash"
LLM_CHUNK_SIZE = 50

LLM_SYSTEM_PROMPT = """\
You are an expert sociolinguistic typist specializing in Brazilian Portuguese oral history corpora. \
Your task is to convert raw ASR speaker blocks into a standardized academic transcription format while \
preserving the requested time-coded block structure.

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


# ═══════════════════════════════════════════════════════════════════════════════
#  Utility helpers (signal-aware replacements for the original print helpers)
# ═══════════════════════════════════════════════════════════════════════════════

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





def get_first_utterance_cloud(speaker_id: str, utterances: list) -> tuple:
    """For cloud mode (AssemblyAI utterance objects)."""
    for utt in utterances:
        if utt.speaker == speaker_id:
            start_sec = utt.start / 1000.0
            return format_time(start_sec), utt.text.strip()
    return "??:??", ""


# ── Speaker mapping ─────────────────────────────────────────────────────────


def build_speaker_map_cloud(utterances: list, f_speaker_id: str, academic_mode: bool = False) -> dict:
    seen = []
    for utt in utterances:
        spk = utt.speaker
        if spk and spk not in seen:
            seen.append(spk)
    others = [spk for spk in seen if spk != f_speaker_id]
    mapping = {f_speaker_id: "F."}
    other_prefix = "E" if academic_mode else "O"
    for i, spk_id in enumerate(others):
        mapping[spk_id] = f"{other_prefix}." if i == 0 else f"{other_prefix}{i}."
    return mapping


# ── Confidence flagging ──────────────────────────────────────────────────────


def flag_low_confidence_cloud(utterance) -> str:
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




# ── Cloud-mode helpers ───────────────────────────────────────────────────────

def detect_hallucination_loops(utterances: list) -> tuple:
    cleaned = []
    loops_pruned = 0
    for utt in utterances:
        words = utt.text.split()
        if len(words) < 6:
            cleaned.append(utt)
            continue
        phrase = " ".join(words[:4]).lower()
        count = utt.text.lower().count(phrase)
        if count > 3 and len(words) > 15:
            utt.text = " ".join(words[:10]) + " [repetição cortada]"
            loops_pruned += 1
        cleaned.append(utt)
    return cleaned, loops_pruned


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


def calculate_speaker_durations(utterances: list) -> Dict[str, float]:
    durations: Dict[str, float] = {}
    for utt in utterances:
        if utt.speaker:
            duration = (utt.end - utt.start) / 1000.0
            durations[utt.speaker] = durations.get(utt.speaker, 0.0) + duration
    return durations


# ═══════════════════════════════════════════════════════════════════════════════
#  TranscriptionWorker
# ═══════════════════════════════════════════════════════════════════════════════

class TranscriptionWorker(QThread):
    """
    Runs the full transcription pipeline in a background thread.

    Signals
    -------
    log_signal(str)              – Every status/progress message (replaces print/step).
    error_signal(str)            – Fatal or per-file errors.
    finished_signal()            – Emitted once when the entire queue is done.
    request_speaker_signal(list) – Emitted when speakers are detected; carries a
                                   list of dicts with speaker info so the GUI can
                                   show a selection dialog.  The worker then blocks
                                   on a threading.Event until the GUI calls
                                   set_selected_speaker().
    """

    log_signal              = pyqtSignal(str)
    error_signal            = pyqtSignal(str)
    finished_signal         = pyqtSignal()
    request_speaker_signal  = pyqtSignal(list)
    file_finished_signal    = pyqtSignal(str)       # basename of completed file
    request_continue_signal = pyqtSignal(str)       # basename of next file

    def __init__(
        self,
        file_paths: List[str],
        output_dir: str,
        mode: str = "deepgram",             # "cloud" or "deepgram"
        api_key: str = "",                  # AssemblyAI key  (cloud)
        academic_mode: bool = False,        # LLM post-processing (cloud/deepgram)
        deepgram_api_key: str = "",         # Deepgram API key
        parent=None,
    ):
        super().__init__(parent)
        self.file_paths = file_paths
        self.output_dir = output_dir
        self.mode = mode
        self.api_key = api_key
        self.academic_mode = academic_mode
        self.deepgram_api_key = deepgram_api_key

        self._abort = False

        # ── Speaker-selection synchronisation ────────────────────────────
        self._speaker_event = threading.Event()
        self._selected_speaker_id: Optional[str] = None
        self._selected_speaker_confirmed: bool = False

        # ── Continue-confirmation synchronisation ────────────────────────
        self._continue_event = threading.Event()
        self._continue_approved = True

    # ── Public control ───────────────────────────────────────────────────
    def request_abort(self):
        """Thread-safe abort flag – checked between pipeline stages."""
        self._abort = True
        # Also unblock any pending waits
        self._speaker_event.set()
        self._continue_event.set()

    def set_selected_speaker(self, speaker_id: Optional[str], is_confirmed: bool = True):
        """Called from the GUI (main thread) after the user picks a speaker or accepts suggested."""
        self._selected_speaker_id = speaker_id
        self._selected_speaker_confirmed = is_confirmed
        self._speaker_event.set()

    def set_continue_response(self, should_continue: bool):
        """Called from the GUI after the user responds to the continue prompt."""
        self._continue_approved = should_continue
        self._continue_event.set()

    # ── Convenience logging wrappers ─────────────────────────────────────
    def _log(self, msg: str):
        self.log_signal.emit(msg)

    def _step(self, n: int, total: int, msg: str):
        self.log_signal.emit(f"  [{n}/{total}] {msg}")

    # ══════════════════════════════════════════════════════════════════════
    #  run()  — entry point executed by QThread
    # ══════════════════════════════════════════════════════════════════════
    def run(self):
        try:
            if self.mode == "deepgram":
                self._run_deepgram_pipeline()
            else:
                self._run_cloud_pipeline()
        except Exception as exc:
            self.error_signal.emit(f"Pipeline fatal error: {exc}")
        finally:
            self.finished_signal.emit()


    # ══════════════════════════════════════════════════════════════════════
    #  CLOUD pipeline  (AssemblyAI)
    # ══════════════════════════════════════════════════════════════════════
    def _run_cloud_pipeline(self):
        import httpx
        import assemblyai as aai

        # ── Apply API key from GUI ───────────────────────────────────────
        if not self.api_key:
            self.error_signal.emit("Chave de API do AssemblyAI não fornecida.")
            return

        aai.settings.api_key = self.api_key
        aai.settings.http_timeout = httpx.Timeout(
            connect=300.0, read=300.0, write=300.0, pool=600.0,
        )

        config = aai.TranscriptionConfig(
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

        self._log(f"{'═' * 60}")
        self._log(f"  Coelho95 Transcriber  (AssemblyAI Cloud Edition)")
        self._log(f"{'═' * 60}")
        self._log(f"  Engine   : AssemblyAI Universal-3.5 Pro  (+ U2 fallback)")
        self._log(f"  Language : Portuguese (BR)  ·  Disfluencies ON")
        self._log(f"  Features : Speaker diarization · Contextual prompt")
        if self.academic_mode:
            self._log(f"  Pipeline : ACADEMIC (Hallucination Pruning + LLM Formatting)")
        self._log(f"  Files    : {len(self.file_paths)} audio file(s)")
        self._log(f"{'═' * 60}")

        for idx, filepath in enumerate(self.file_paths):
            if self._abort:
                self._log("> Transcrição abortada pelo usuário.")
                break

            self._log(f"\n{'─' * 60}")
            self._log(f"  Arquivo: {os.path.basename(filepath)}")
            self._process_file_cloud(filepath, aai, config)

            if not self._abort:
                self.file_finished_signal.emit(os.path.basename(filepath))

            # Ask user before continuing to the next file
            if not self._abort and idx < len(self.file_paths) - 1:
                next_basename = os.path.basename(self.file_paths[idx + 1])
                self._continue_event.clear()
                self._continue_approved = True
                self.request_continue_signal.emit(next_basename)
                self._continue_event.wait()
                if self._abort or not self._continue_approved:
                    self._log("> Fila interrompida pelo usuário.")
                    break

        self._log(f"\n{'═' * 60}")
        self._log("  Todos os arquivos processados. Pronto.")
        self._log(f"{'═' * 60}")

    def _transcribe_with_retry(self, filepath: str, aai, config):
        last_exc = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                transcript = aai.Transcriber().transcribe(filepath, config=config)
                return transcript
            except Exception as exc:
                last_exc = exc
                if attempt < MAX_RETRIES:
                    delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                    self._log(f"  ⚠️  Tentativa {attempt}/{MAX_RETRIES} falhou: {exc}")
                    self._log(f"       Tentando novamente em {delay}s…")
                    time.sleep(delay)
                else:
                    raise last_exc

    def _format_academic_llm(self, raw_lines: List[str], aai) -> List[str]:
        import httpx

        formatted = []
        total_chunks = (len(raw_lines) + LLM_CHUNK_SIZE - 1) // LLM_CHUNK_SIZE

        for i in range(0, len(raw_lines), LLM_CHUNK_SIZE):
            chunk = raw_lines[i:i + LLM_CHUNK_SIZE]
            chunk_text = "".join(chunk)
            chunk_num = (i // LLM_CHUNK_SIZE) + 1

            self._log(f"    - Processando chunk {chunk_num}/{total_chunks} via LLM Gateway…")

            payload = {
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": LLM_SYSTEM_PROMPT},
                    {"role": "user", "content": chunk_text},
                ],
                "temperature": 0.2,
            }
            headers = {
                "authorization": aai.settings.api_key,
                "content-type": "application/json",
            }

            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    with httpx.Client(timeout=120.0) as client:
                        resp = client.post(LLM_GATEWAY_URL, json=payload, headers=headers)
                        resp.raise_for_status()
                        data = resp.json()
                        result_text = data["choices"][0]["message"]["content"]
                        if not result_text.endswith("\n"):
                            result_text += "\n"
                        formatted.append(result_text)
                        break
                except Exception as exc:
                    if attempt < MAX_RETRIES:
                        time.sleep(2 ** attempt)
                    else:
                        self._log(f"  ❌  LLM Gateway falhou no chunk {chunk_num}: {exc}")
                        formatted.append(chunk_text)

        return formatted

    def _process_file_cloud(self, filepath: str, aai, config):
        total_steps = 4 if self.academic_mode else 3
        transcript = None

        try:
            self._step(1, total_steps, "Fazendo upload e transcrevendo via AssemblyAI…")
            t0 = time.monotonic()
            transcript = self._transcribe_with_retry(filepath, aai, config)
            elapsed = time.monotonic() - t0

            if transcript.status == aai.TranscriptStatus.error:
                self.error_signal.emit(f"Erro AssemblyAI: {transcript.error}")
                return

            utterances = transcript.utterances
            if not utterances:
                self._log("  ⚠️  Nenhuma fala retornada pelo AssemblyAI.")
                return

            if self.academic_mode:
                utterances, loops_pruned = detect_hallucination_loops(utterances)
                if loops_pruned > 0:
                    self._log(f"  ℹ  Removidos {loops_pruned} loops de alucinação da transcrição.")

            self._log(f"  ✓  Transcrição completa em {format_elapsed(elapsed)}")

            # ── Confidence statistics ────────────────────────────────────
            stats = compute_confidence_stats(utterances)
            if stats["total_words"] > 0:
                self._log(
                    f"  ℹ  Palavras: {stats['total_words']}  |  "
                    f"Confiança média: {stats['avg']:.1%}  |  "
                    f"Mínima: {stats['min']:.1%}  |  "
                    f"Abaixo de {LOW_CONFIDENCE_THRESHOLD:.0%}: {stats['below_threshold']}"
                )

            if self._abort:
                return

            self._step(2, total_steps, "Atribuindo falantes…")
            f_speaker_id, speaker_info = self._request_speaker_selection_cloud(utterances, filepath)
            if f_speaker_id is None:   # aborted
                return
            speaker_map = build_speaker_map_cloud(utterances, f_speaker_id, self.academic_mode)

            self._log("  Mapeamento final:")
            for raw, label in speaker_map.items():
                ts, _ = get_first_utterance_cloud(raw, utterances)
                self._log(f"    {raw} → {label}  (primeira fala em {ts})")

            if self._abort:
                return

            self._step(3, total_steps, "Gerando linhas de transcrição…")
            base_name = os.path.basename(filepath)
            out_name = os.path.splitext(base_name)[0] + ".txt"

            if self.academic_mode:
                raw_out_name = os.path.splitext(base_name)[0] + "_raw.txt"
            else:
                raw_out_name = out_name

            raw_out_path = os.path.join(self.output_dir, raw_out_name)

            raw_lines = []
            flagged = 0
            for utt in utterances:
                start = format_time(utt.start / 1000.0)
                end = format_time(utt.end / 1000.0)
                raw_id = utt.speaker if utt.speaker else "UNKNOWN"
                label = speaker_map.get(raw_id, "?.")
                text = utt.text.strip()
                flag = flag_low_confidence_cloud(utt)
                if flag:
                    flagged += 1
                raw_lines.append(f"[{start} - {end}] {label} {text}{flag}\n")

            with open(raw_out_path, "w", encoding="utf-8") as f:
                f.writelines(raw_lines)

            if flagged:
                self._log(f"  ⚠️  {flagged} segmento(s) com baixa confiança.")

            # Save speaker metadata so F can be changed later
            academic_out_path = os.path.join(self.output_dir, out_name) if self.academic_mode else None
            if save_speaker_metadata:
                meta = {
                    "audio_filepath": filepath,
                    "filename": os.path.basename(filepath),
                    "txt_filepath": raw_out_path,
                    "academic_txt_filepath": academic_out_path,
                    "academic_mode": self.academic_mode,
                    "f_speaker_id": f_speaker_id,
                    "is_confirmed": getattr(self, "_selected_speaker_confirmed", False),
                    "speaker_info": speaker_info,
                    "speaker_map": speaker_map,
                    "utterances": [
                        {
                            "speaker": utt.speaker if utt.speaker else "UNKNOWN",
                            "start": utt.start,
                            "end": utt.end,
                            "start_str": format_time(utt.start / 1000.0),
                            "end_str": format_time(utt.end / 1000.0),
                            "text": utt.text.strip(),
                            "flag": flag_low_confidence_cloud(utt),
                        }
                        for utt in utterances
                    ]
                }
                save_speaker_metadata(self.output_dir, meta)

            if not self.academic_mode:
                self._log(f"  ✅  Salvo → {raw_out_path}")
                return

            self._log(f"  ✅  Transcrição bruta salva → {raw_out_path}")

            if self._abort:
                return

            # ── LLM academic formatting ──────────────────────────────────
            self._step(4, total_steps, "Aplicando formatação acadêmica via LLM Gateway…")
            academic_lines = self._format_academic_llm(raw_lines, aai)

            with open(academic_out_path, "w", encoding="utf-8") as f:
                for block in academic_lines:
                    f.write(block)

            self._log(f"  ✅  Transcrição acadêmica salva → {academic_out_path}")

        except Exception as exc:
            self.error_signal.emit(f"Erro ao processar '{os.path.basename(filepath)}': {exc}")
        finally:
            if transcript is not None and getattr(transcript, "id", None):
                try:
                    aai.Transcript.delete_by_id(transcript.id)
                    self._log("  🔒  Transcrição removida dos servidores da AssemblyAI (Zero Retention).")
                except Exception as del_exc:
                    self._log(f"  ⚠️  Não foi possível excluir transcrição remota na AssemblyAI: {del_exc}")

    def _request_speaker_selection_cloud(self, utterances: list, filepath: str = "") -> Tuple[Optional[str], List[dict]]:
        """Emit speaker info to the GUI and wait or fallback to suggested so queue continues."""
        # Gather unique speakers in order of appearance
        seen: List[str] = []
        for utt in utterances:
            spk = utt.speaker
            if spk and spk not in seen:
                seen.append(spk)
        if not seen:
            raise RuntimeError("Nenhum falante detectado.")

        durations = calculate_speaker_durations(utterances)
        total_time = sum(durations.values())

        speaker_info: List[dict] = []
        for spk_id in seen:
            ts, text = get_first_utterance_cloud(spk_id, utterances)
            dur = durations.get(spk_id, 0.0)
            pct = (dur / total_time) * 100 if total_time > 0 else 0
            speaker_info.append({
                "id": spk_id,
                "first_time": ts,
                "first_text": text,
                "duration": dur,
                "pct": pct,
                "filepath": filepath,
                "filename": os.path.basename(filepath) if filepath else "",
            })

        suggested = max(durations, key=durations.get)
        for info in speaker_info:
            info["suggested"] = (info["id"] == suggested)

        self._speaker_event.clear()
        self._selected_speaker_id = None
        self._selected_speaker_confirmed = False
        self._log("  ⏸  Aguardando seleção do falante principal (F.)…")
        self.request_speaker_signal.emit(speaker_info)
        self._speaker_event.wait()

        if self._abort:
            return None, speaker_info

        chosen = self._selected_speaker_id or suggested
        pct = (durations.get(chosen, 0) / total_time) * 100 if total_time > 0 else 0
        if getattr(self, "_selected_speaker_confirmed", False):
            self._log(f"  ✓  F atribuído a {chosen} ({pct:.1f}% do tempo de fala)")
        else:
            self._log(f"  ✓  F atribuído provisoriamente a {chosen} ({pct:.1f}% do tempo) – você pode alterar depois")
        return chosen, speaker_info

    # ══════════════════════════════════════════════════════════════════════
    #  DEEPGRAM pipeline  (Nova-3)
    # ══════════════════════════════════════════════════════════════════════
    @staticmethod
    def _group_deepgram_words(words_list: list) -> list:
        """
        Group consecutive words from the same Deepgram speaker into
        DeepgramUtterance objects compatible with the cloud speaker
        selection pipeline.

        Each word dict from Deepgram has: word, punctuated_word, start,
        end, confidence, speaker (int).
        """
        if not words_list:
            return []

        utterances = []
        current_speaker = None
        current_words = []
        current_start_ms = 0
        current_end_ms = 0

        for w in words_list:
            spk = str(w.get("speaker", 0))
            start_ms = int(w.get("start", 0) * 1000)
            end_ms = int(w.get("end", 0) * 1000)

            if spk != current_speaker and current_words:
                # Emit previous utterance
                text = " ".join(
                    wd.get("punctuated_word", wd.get("word", ""))
                    for wd in current_words
                )
                adapter_words = [DeepgramWordAdapter(wd) for wd in current_words]
                utterances.append(DeepgramUtterance(
                    speaker=current_speaker,
                    start_ms=current_start_ms,
                    end_ms=current_end_ms,
                    text=text,
                    words=adapter_words,
                ))
                current_words = []

            if not current_words:
                current_speaker = spk
                current_start_ms = start_ms

            current_words.append(w)
            current_end_ms = end_ms

        # Emit last utterance
        if current_words:
            text = " ".join(
                wd.get("punctuated_word", wd.get("word", ""))
                for wd in current_words
            )
            adapter_words = [DeepgramWordAdapter(wd) for wd in current_words]
            utterances.append(DeepgramUtterance(
                speaker=current_speaker,
                start_ms=current_start_ms,
                end_ms=current_end_ms,
                text=text,
                words=adapter_words,
            ))

        return utterances

    def _run_deepgram_pipeline(self):
        """Full Deepgram Nova-3 transcription pipeline with diarization via REST API."""
        if not self.deepgram_api_key:
            self.error_signal.emit("Chave de API do Deepgram não fornecida. Configure na aba 'Configurações'.")
            return

        self._log(f"{'═' * 60}")
        self._log(f"  Coelho95 Transcriber  (Deepgram Cloud Edition)")
        self._log(f"{'═' * 60}")
        self._log(f"  Engine   : Deepgram Nova-3 (REST API)")
        self._log(f"  Language : Portuguese (BR)  ·  Smart Format ON")
        self._log(f"  Features : Speaker diarization · Punctuation · MIP Opt-Out ON")
        if self.academic_mode:
            self._log(f"  Pipeline : ACADEMIC (LLM Formatting via AssemblyAI Gateway)")
        self._log(f"  Files    : {len(self.file_paths)} audio file(s)")
        self._log(f"{'═' * 60}")

        for idx, filepath in enumerate(self.file_paths):
            if self._abort:
                self._log("> Transcrição abortada pelo usuário.")
                break

            self._log(f"\n{'─' * 60}")
            self._log(f"  Arquivo: {os.path.basename(filepath)}")
            self._process_file_deepgram(filepath)

            if not self._abort:
                self.file_finished_signal.emit(os.path.basename(filepath))

            # Ask user before continuing to the next file
            if not self._abort and idx < len(self.file_paths) - 1:
                next_basename = os.path.basename(self.file_paths[idx + 1])
                self._continue_event.clear()
                self._continue_approved = True
                self.request_continue_signal.emit(next_basename)
                self._continue_event.wait()
                if self._abort or not self._continue_approved:
                    self._log("> Fila interrompida pelo usuário.")
                    break

        self._log(f"\n{'═' * 60}")
        self._log("  Todos os arquivos processados. Pronto.")
        self._log(f"{'═' * 60}")

    def _process_file_deepgram(self, filepath: str):
        """Process a single audio file through the Deepgram REST API."""
        import httpx
        total_steps = 4 if self.academic_mode else 3

        try:
            self._step(1, total_steps, "Fazendo upload e transcrevendo via Deepgram Nova-3…")
            t0 = time.monotonic()

            with open(filepath, "rb") as audio_file:
                audio_bytes = audio_file.read()

            headers = {
                "Authorization": f"Token {self.deepgram_api_key}",
                "Content-Type": "audio/*",
            }
            params = {
                "model": "nova-3",
                "language": "pt-BR",
                "diarize": "true",
                "punctuate": "true",
                "smart_format": "true",
                "mip_opt_out": "true",
            }

            with httpx.Client(timeout=httpx.Timeout(connect=60.0, read=600.0, write=600.0, pool=60.0)) as http_client:
                response = http_client.post(
                    "https://api.deepgram.com/v1/listen",
                    headers=headers,
                    params=params,
                    content=audio_bytes,
                )

                if response.status_code == 401:
                    self.error_signal.emit("Erro Deepgram: Chave de API inválida ou expirada. Verifique na aba 'Configurações'.")
                    return
                elif response.status_code == 403:
                    self.error_signal.emit("Erro Deepgram: Acesso negado (403). Verifique as permissões da chave.")
                    return
                elif response.status_code != 200:
                    self.error_signal.emit(f"Erro Deepgram ({response.status_code}): {response.text}")
                    return

                data = response.json()

            elapsed = time.monotonic() - t0

            # Extract words from the first channel/alternative
            try:
                channel = data["results"]["channels"][0]
                alternative = channel["alternatives"][0]
                words_list = alternative.get("words", [])
            except (KeyError, IndexError, TypeError):
                self._log("  ⚠️  Nenhuma fala retornada pelo Deepgram.")
                return

            if not words_list:
                self._log("  ⚠️  Nenhuma palavra detectada no áudio.")
                return

            self._log(f"  ✓  Transcrição completa em {format_elapsed(elapsed)}  ({len(words_list)} palavras)")

            if self._abort:
                return

            # Group words into utterances by speaker
            utterances = self._group_deepgram_words(words_list)
            if not utterances:
                self._log("  ⚠️  Nenhuma utterance agrupada.")
                return

            # Hallucination pruning for academic mode
            if self.academic_mode:
                utterances, loops_pruned = detect_hallucination_loops(utterances)
                if loops_pruned > 0:
                    self._log(f"  ℹ  Removidos {loops_pruned} loops de alucinação da transcrição.")

            # Confidence statistics
            stats = compute_confidence_stats(utterances)
            if stats["total_words"] > 0:
                self._log(
                    f"  ℹ  Palavras: {stats['total_words']}  |  "
                    f"Confiança média: {stats['avg']:.1%}  |  "
                    f"Mínima: {stats['min']:.1%}  |  "
                    f"Abaixo de {LOW_CONFIDENCE_THRESHOLD:.0%}: {stats['below_threshold']}"
                )

            if self._abort:
                return

            self._step(2, total_steps, "Atribuindo falantes…")
            f_speaker_id, speaker_info = self._request_speaker_selection_cloud(utterances, filepath)
            if f_speaker_id is None:   # aborted
                return
            speaker_map = build_speaker_map_cloud(utterances, f_speaker_id, self.academic_mode)

            self._log("  Mapeamento final:")
            for raw, label in speaker_map.items():
                ts, _ = get_first_utterance_cloud(raw, utterances)
                self._log(f"    {raw} → {label}  (primeira fala em {ts})")

            if self._abort:
                return

            self._step(3, total_steps, "Gerando linhas de transcrição…")
            base_name = os.path.basename(filepath)
            out_name = os.path.splitext(base_name)[0] + ".txt"

            if self.academic_mode:
                raw_out_name = os.path.splitext(base_name)[0] + "_raw.txt"
            else:
                raw_out_name = out_name

            raw_out_path = os.path.join(self.output_dir, raw_out_name)

            raw_lines = []
            flagged = 0
            for utt in utterances:
                start = format_time(utt.start / 1000.0)
                end = format_time(utt.end / 1000.0)
                raw_id = utt.speaker if utt.speaker else "UNKNOWN"
                label = speaker_map.get(raw_id, "?.")
                text = utt.text.strip()
                flag = flag_low_confidence_cloud(utt)
                if flag:
                    flagged += 1
                raw_lines.append(f"[{start} - {end}] {label} {text}{flag}\n")

            with open(raw_out_path, "w", encoding="utf-8") as f:
                f.writelines(raw_lines)

            if flagged:
                self._log(f"  ⚠️  {flagged} segmento(s) com baixa confiança.")

            # Save speaker metadata so F can be changed later
            academic_out_path = os.path.join(self.output_dir, out_name) if self.academic_mode else None
            if save_speaker_metadata:
                meta = {
                    "audio_filepath": filepath,
                    "filename": os.path.basename(filepath),
                    "txt_filepath": raw_out_path,
                    "academic_txt_filepath": academic_out_path,
                    "academic_mode": self.academic_mode,
                    "f_speaker_id": f_speaker_id,
                    "is_confirmed": getattr(self, "_selected_speaker_confirmed", False),
                    "speaker_info": speaker_info,
                    "speaker_map": speaker_map,
                    "utterances": [
                        {
                            "speaker": utt.speaker if utt.speaker else "UNKNOWN",
                            "start": utt.start,
                            "end": utt.end,
                            "start_str": format_time(utt.start / 1000.0),
                            "end_str": format_time(utt.end / 1000.0),
                            "text": utt.text.strip(),
                            "flag": flag_low_confidence_cloud(utt),
                        }
                        for utt in utterances
                    ]
                }
                save_speaker_metadata(self.output_dir, meta)

            if not self.academic_mode:
                self._log(f"  ✅  Salvo → {raw_out_path}")
                return

            self._log(f"  ✅  Transcrição bruta salva → {raw_out_path}")

            if self._abort:
                return

            # ── LLM academic formatting (reuses AssemblyAI LLM Gateway) ──
            if not self.api_key:
                self._log("  ⚠️  Chave AssemblyAI necessária para formatação acadêmica via LLM Gateway. Pulando etapa.")
                return

            import assemblyai as aai
            aai.settings.api_key = self.api_key

            self._step(4, total_steps, "Aplicando formatação acadêmica via LLM Gateway…")
            academic_out_path = os.path.join(self.output_dir, out_name)
            academic_lines = self._format_academic_llm(raw_lines, aai)

            with open(academic_out_path, "w", encoding="utf-8") as f:
                for block in academic_lines:
                    f.write(block)

            self._log(f"  ✅  Transcrição acadêmica salva → {academic_out_path}")

        except Exception as exc:
            self.error_signal.emit(f"Erro ao processar '{os.path.basename(filepath)}': {exc}")
#  Deepgram adapter classes — make Deepgram word-level results compatible
#  with the existing cloud speaker selection and formatting pipeline.
# ═══════════════════════════════════════════════════════════════════════════════

class DeepgramWordAdapter:
    """Adapter for a single Deepgram word to match the AssemblyAI word interface."""
    __slots__ = ("confidence", "text")

    def __init__(self, word_dict: dict):
        self.confidence = word_dict.get("confidence", 0.0)
        self.text = word_dict.get("punctuated_word", word_dict.get("word", ""))


class DeepgramUtterance:
    """
    Adapter that groups consecutive Deepgram words from the same speaker
    into a single utterance object, compatible with:
      - _request_speaker_selection_cloud()
      - build_speaker_map_cloud()
      - flag_low_confidence_cloud()
      - calculate_speaker_durations()
    """
    __slots__ = ("speaker", "start", "end", "text", "words")

    def __init__(self, speaker: str, start_ms: int, end_ms: int, text: str,
                 words: list):
        self.speaker = speaker     # str: "0", "1", …
        self.start = start_ms      # int: milliseconds
        self.end = end_ms          # int: milliseconds
        self.text = text           # str: concatenated punctuated words
        self.words = words         # list[DeepgramWordAdapter]
