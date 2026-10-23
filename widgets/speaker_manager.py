"""
SpeakerManager — Manages speaker metadata persistence, mapping, and transcript updates.

Allows assigning or changing the primary speaker (F.) after transcription has completed,
both for standard and academic transcripts.
"""

import os
import re
import json
from typing import Optional, Dict, List, Tuple


def get_meta_base_name(filename: str) -> str:
    """Extract canonical base name without extension or suffixes like _raw, _revisada."""
    name, _ = os.path.splitext(os.path.basename(filename))
    if name.endswith("_raw"):
        name = name[:-4]
    elif name.endswith("_revisada"):
        name = name[:-9]
    return name


def get_meta_path(output_dir: str, filename: str) -> str:
    """Return path to .speaker_meta.json for a given audio or transcript filename."""
    base = get_meta_base_name(filename)
    return os.path.join(output_dir, f"{base}.speaker_meta.json")


def save_speaker_metadata(output_dir: str, meta: dict) -> Optional[str]:
    """Save speaker metadata dict to JSON file in output_dir."""
    try:
        os.makedirs(output_dir, exist_ok=True)
        filename = meta.get("filename") or os.path.basename(meta.get("audio_filepath", "transcript"))
        meta_path = get_meta_path(output_dir, filename)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
        return meta_path
    except Exception as exc:
        print(f"[SpeakerManager] Erro ao salvar metadados: {exc}")
        return None


def load_speaker_metadata(output_dir: str, filename: str) -> Optional[dict]:
    """Load speaker metadata from output_dir for the given filename."""
    try:
        meta_path = get_meta_path(output_dir, filename)
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as exc:
        print(f"[SpeakerManager] Erro ao carregar metadados: {exc}")
    return None


def build_speaker_mapping(
    speaker_order: List[str],
    f_speaker_id: str,
    academic_mode: bool = False
) -> Dict[str, str]:
    """
    Build mapping from raw speaker ID to label.
    f_speaker_id -> 'F.'
    Others -> 'E.', 'E1.', 'E2.' (academic) or 'O.', 'O1.', 'O2.' (standard).
    """
    mapping = {f_speaker_id: "F."}
    others = [spk for spk in speaker_order if spk != f_speaker_id]
    prefix = "E" if academic_mode else "O"
    for i, spk_id in enumerate(others):
        mapping[spk_id] = f"{prefix}." if i == 0 else f"{prefix}{i}."
    return mapping


def update_transcript_speakers(
    meta: dict,
    new_f_speaker_id: str,
    output_dir: str
) -> Tuple[bool, str]:
    """
    Update the primary speaker (F.) for a completed transcription.
    Re-maps speaker tags in raw transcript and academic transcript,
    and updates the saved metadata file.
    """
    try:
        old_f_speaker_id = meta.get("f_speaker_id")
        old_speaker_map = meta.get("speaker_map", {})
        academic_mode = meta.get("academic_mode", False)

        # Get speaker order (preserving original appearance order)
        speaker_info = meta.get("speaker_info", [])
        speaker_order = [s["id"] for s in speaker_info]
        if not speaker_order:
            speaker_order = list(old_speaker_map.keys())

        if new_f_speaker_id not in speaker_order:
            speaker_order.append(new_f_speaker_id)

        # Build new mapping
        new_speaker_map = build_speaker_mapping(speaker_order, new_f_speaker_id, academic_mode)

        # Build label substitution map from old labels to temporary tokens, then to new labels
        # e.g. old_label -> new_label
        raw_to_old_label = old_speaker_map
        old_label_to_new_label: Dict[str, str] = {}
        for spk_id, new_label in new_speaker_map.items():
            old_label = raw_to_old_label.get(spk_id)
            if old_label:
                old_label_to_new_label[old_label] = new_label

        base_name = get_meta_base_name(meta.get("filename", ""))
        
        # 1. Update raw transcript file if utterances are preserved
        raw_out_name = f"{base_name}_raw.txt" if academic_mode else f"{base_name}.txt"
        raw_out_path = os.path.join(output_dir, raw_out_name)

        utterances = meta.get("utterances", [])
        if utterances and os.path.exists(raw_out_path):
            # Reconstruct exact raw lines with updated speaker map
            raw_lines = []
            for utt in utterances:
                start = utt.get("start_str")
                end = utt.get("end_str")
                if not start or not end:
                    # Fallback to formatting from ms/sec
                    st_sec = utt.get("start", 0) / 1000.0 if utt.get("start", 0) > 1000 else utt.get("start", 0)
                    en_sec = utt.get("end", 0) / 1000.0 if utt.get("end", 0) > 1000 else utt.get("end", 0)
                    h_s = int(st_sec // 3600)
                    m_s = int((st_sec % 3600) // 60)
                    s_s = int(st_sec % 60)
                    start = f"{h_s:02d}:{m_s:02d}:{s_s:02d}" if h_s > 0 else f"{m_s:02d}:{s_s:02d}"
                    h_e = int(en_sec // 3600)
                    m_e = int((en_sec % 3600) // 60)
                    s_e = int(en_sec % 60)
                    end = f"{h_e:02d}:{m_e:02d}:{s_e:02d}" if h_e > 0 else f"{m_e:02d}:{s_e:02d}"

                raw_id = utt.get("speaker", "UNKNOWN")
                label = new_speaker_map.get(raw_id, "?.")
                text = utt.get("text", "").strip()
                flag = utt.get("flag", "")
                raw_lines.append(f"[{start} - {end}] {label} {text}{flag}\n")

            with open(raw_out_path, "w", encoding="utf-8") as rf:
                rf.writelines(raw_lines)
        elif os.path.exists(raw_out_path):
            # Swap labels directly in raw file lines
            _swap_labels_in_file(raw_out_path, old_label_to_new_label)

        # 2. Update academic transcript file if present
        if academic_mode:
            academic_out_name = f"{base_name}.txt"
            academic_out_path = os.path.join(output_dir, academic_out_name)
            if os.path.exists(academic_out_path):
                _swap_labels_in_file(academic_out_path, old_label_to_new_label)

        # 3. Update metadata object and save
        meta["f_speaker_id"] = new_f_speaker_id
        meta["speaker_map"] = new_speaker_map
        meta["is_confirmed"] = True
        save_speaker_metadata(output_dir, meta)

        return True, f"Falante principal atualizado para '{new_f_speaker_id}' (F.)."

    except Exception as exc:
        return False, f"Erro ao atualizar falante: {exc}"


def _swap_labels_in_file(filepath: str, old_to_new: Dict[str, str]):
    """
    Safely swap speaker labels in a formatted transcript file.
    Lines typically match: ^\\[\\d{2}:\\d{2}(?::\\d{2})? - \\d{2}:\\d{2}(?::\\d{2})?\\] (F\\.|E\\.|E\\d+\\.|O\\.|O\\d+\\.)
    """
    if not os.path.exists(filepath):
        return

    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Two-pass replacement using temporary placeholders to avoid accidental collisions
    # e.g., F. -> __TEMP_0__, E. -> __TEMP_1__
    temp_tokens: Dict[str, str] = {}
    for idx, (old_lbl, _) in enumerate(old_to_new.items()):
        temp_tokens[old_lbl] = f"__SPK_TEMP_{idx}__"

    pattern = re.compile(r"^(\[\d{2}:\d{2}(?::\d{2})? - \d{2}:\d{2}(?::\d{2})?\]\s+)(\S+)")

    new_lines = []
    for line in lines:
        m = pattern.match(line)
        if m:
            prefix = m.group(1)
            label = m.group(2)
            if label in old_to_new:
                # Replace with target label
                target = old_to_new[label]
                line = prefix + target + line[m.end():]
        new_lines.append(line)

    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
