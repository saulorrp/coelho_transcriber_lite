"""
coelho_cli — non-interactive command line for Coelho Transcriber Lite.

Runs the same pipeline as the GUI (components/transcription_worker.py) without
opening a window, so agents and scripts can call it from a terminal:
arguments in, transcript or JSON out, a clear exit status.

The GUI files are not changed. The worker is a QThread, but its run() is called
directly on this thread; every signal it emits reaches a plain Python callable
here, so the speaker choice and the "continue?" prompt are answered at once.

Both engines are cloud services (Deepgram, AssemblyAI). Nothing is uploaded
unless --confirmo-nuvem is given; without it, `transcrever` only shows the plan.

Exit status:
  0  ok
  1  bad option or argument
  2  configuration: API key missing
  3  engine or network failure (at least one file failed)
  4  upload not confirmed (--confirmo-nuvem missing); nothing was sent
  5  audio or transcript not found, or unsupported format
  6  output already exists (use --sobrescrever)
"""

import argparse
import json
import os
import sys
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
for sub in ("components", "widgets"):
    path = os.path.join(BASE_DIR, sub)
    if path not in sys.path:
        sys.path.insert(0, path)

# Same places the GUI uses (main_gui.py, MainWindow.__init__)
DOCS_DIR = os.path.join(os.path.expanduser("~"), "Documents", "Coelho95 Transcriber")
CONFIG_PATH = os.path.join(DOCS_DIR, "config.json")
DEFAULT_OUTPUT_DIR = os.path.join(DOCS_DIR, "output da transcricao")

AUDIO_EXTENSIONS = (
    '.mp4', '.wav', '.m4a', '.mp3', '.mkv', '.ogg',
    '.aac', '.flac', '.opus', '.webm', '.wma', '.mov'
)

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_CONFIG = 2
EXIT_ENGINE = 3
EXIT_NOT_CONFIRMED = 4
EXIT_NOT_FOUND = 5
EXIT_EXISTS = 6

# Config mode strings (GUI) -> CLI engine names -> worker modes
MODE_TO_ENGINE = {"cloud_deepgram": "deepgram", "cloud_assemblyai": "assemblyai"}
ENGINE_TO_WORKER = {"deepgram": "deepgram", "assemblyai": "cloud"}


class CliError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


# ── Output helpers ───────────────────────────────────────────────────────────

def _setup_streams():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def log(msg: str, quiet: bool = False):
    if not quiet:
        print(msg, file=sys.stderr, flush=True)


def emit_json(data):
    print(json.dumps(data, ensure_ascii=False, indent=2))


# ── Configuration ────────────────────────────────────────────────────────────

def load_config(path: str = CONFIG_PATH) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        raise CliError(EXIT_CONFIG, f"config.json ilegível ({path}): {exc}")


def resolve_keys(config: dict) -> dict:
    """Environment variables win over the GUI's config.json. Keys are never printed."""
    dg = os.environ.get("DEEPGRAM_API_KEY") or config.get("deepgram_api_key") or ""
    aai = os.environ.get("ASSEMBLYAI_API_KEY") or config.get("api_key") or ""
    return {
        "deepgram": dg.strip(),
        "assemblyai": aai.strip(),
        "deepgram_source": "env" if os.environ.get("DEEPGRAM_API_KEY") else ("config" if dg else None),
        "assemblyai_source": "env" if os.environ.get("ASSEMBLYAI_API_KEY") else ("config" if aai else None),
    }


def default_engine(config: dict) -> str:
    return MODE_TO_ENGINE.get(config.get("transcription_mode", "cloud_deepgram"), "deepgram")


# ── Files ────────────────────────────────────────────────────────────────────

def collect_audio(inputs: list) -> list:
    files = []
    for item in inputs:
        path = os.path.abspath(item)
        if os.path.isdir(path):
            found = sorted(
                os.path.join(path, f) for f in os.listdir(path)
                if f.lower().endswith(AUDIO_EXTENSIONS)
            )
            if not found:
                raise CliError(EXIT_NOT_FOUND, f"Nenhum áudio suportado na pasta: {path}")
            files.extend(found)
        elif os.path.isfile(path):
            if not path.lower().endswith(AUDIO_EXTENSIONS):
                raise CliError(EXIT_NOT_FOUND,
                               f"Formato não suportado: {path} (aceitos: {', '.join(AUDIO_EXTENSIONS)})")
            files.append(path)
        else:
            raise CliError(EXIT_NOT_FOUND, f"Arquivo ou pasta não encontrado: {path}")
    return files


def output_paths(audio: str, output_dir: str, academic: bool) -> dict:
    base = os.path.splitext(os.path.basename(audio))[0]
    final_txt = os.path.join(output_dir, base + ".txt")
    raw_txt = os.path.join(output_dir, base + "_raw.txt") if academic else final_txt
    return {
        "txt": final_txt,
        "raw_txt": raw_txt,
        "meta": os.path.join(output_dir, base + ".speaker_meta.json"),
    }


# ── Running the GUI's worker headless ────────────────────────────────────────

def run_one(audio: str, engine: str, keys: dict, output_dir: str, academic: bool,
            f_choice: str, quiet: bool) -> dict:
    from transcription_worker import TranscriptionWorker

    paths = output_paths(audio, output_dir, academic)
    result = {
        "audio": audio,
        "status": "erro",
        "motor": engine,
        "academico": academic,
        "txt": None,
        "raw_txt": None,
        "meta": None,
        "f": None,
        "f_confirmado": False,
        "mapa_falantes": None,
        "falantes": [],
        "erros": [],
        "avisos": [],
        "segundos": None,
    }

    worker = TranscriptionWorker(
        file_paths=[audio],
        output_dir=output_dir,
        mode=ENGINE_TO_WORKER[engine],
        api_key=keys["assemblyai"],
        academic_mode=academic,
        deepgram_api_key=keys["deepgram"],
    )

    def on_log(msg):
        log(msg, quiet)
        if "⚠️" in msg:
            result["avisos"].append(msg.strip())

    def on_error(msg):
        log(f"ERRO: {msg}")
        result["erros"].append(msg)

    def on_speakers(info):
        result["falantes"] = [
            {k: s.get(k) for k in ("id", "first_time", "first_text", "duration", "pct", "suggested")}
            for s in info
        ]
        ids = [s["id"] for s in info]
        if f_choice == "auto":
            worker.set_selected_speaker(None, is_confirmed=False)  # the worker falls back to the suggested one
        elif f_choice == "primeiro":
            worker.set_selected_speaker(ids[0], is_confirmed=True)
        elif f_choice in ids:
            worker.set_selected_speaker(f_choice, is_confirmed=True)
        else:
            result["avisos"].append(
                f"Falante '{f_choice}' não existe neste áudio ({', '.join(ids)}); usado o sugerido.")
            worker.set_selected_speaker(None, is_confirmed=False)

    worker.log_signal.connect(on_log)
    worker.error_signal.connect(on_error)
    worker.request_speaker_signal.connect(on_speakers)
    worker.request_continue_signal.connect(lambda _name: worker.set_continue_response(True))

    t0 = time.monotonic()
    started = time.time()
    worker.run()  # synchronous: no event loop, no thread
    result["segundos"] = round(time.monotonic() - t0, 1)

    def fresh(path):
        return path if os.path.exists(path) and os.path.getmtime(path) >= started - 1 else None

    result["raw_txt"] = fresh(paths["raw_txt"])
    result["txt"] = fresh(paths["txt"])
    result["meta"] = fresh(paths["meta"])

    if result["meta"]:
        try:
            with open(result["meta"], "r", encoding="utf-8") as f:
                meta = json.load(f)
            result["f"] = meta.get("f_speaker_id")
            result["f_confirmado"] = bool(meta.get("is_confirmed"))
            result["mapa_falantes"] = meta.get("speaker_map")
            utts = meta.get("utterances", [])
            result["segmentos"] = len(utts)
            result["segmentos_baixa_confianca"] = sum(1 for u in utts if u.get("flag"))
        except Exception as exc:
            result["avisos"].append(f"Metadados ilegíveis: {exc}")

    if result["raw_txt"] and not result["erros"]:
        result["status"] = "ok"
        if academic and not result["txt"]:
            result["status"] = "parcial"
            result["avisos"].append("Formatação acadêmica não gerada; só a transcrição bruta existe.")
    elif not result["erros"]:
        result["erros"].append("Nenhuma transcrição foi gerada (o áudio não tem fala reconhecida?).")
    return result


# ── Commands ─────────────────────────────────────────────────────────────────

def cmd_transcrever(args) -> int:
    config = load_config()
    keys = resolve_keys(config)
    engine = args.motor or default_engine(config)
    output_dir = os.path.abspath(args.saida or DEFAULT_OUTPUT_DIR)
    files = collect_audio(args.audios)

    needed = ["deepgram"] if engine == "deepgram" else ["assemblyai"]
    if args.academico:
        needed.append("assemblyai")  # the LLM formatting goes through AssemblyAI's gateway
    missing = sorted({n for n in needed if not keys[n]})

    clashes = []
    for audio in files:
        p = output_paths(audio, output_dir, args.academico)
        clashes += [x for x in {p["txt"], p["raw_txt"]} if os.path.exists(x)]

    services = ["Deepgram" if engine == "deepgram" else "AssemblyAI"]
    if args.academico:
        services.append("AssemblyAI LLM Gateway (texto da transcrição)")

    plan = {
        "motor": engine,
        "academico": args.academico,
        "f": args.f,
        "saida": output_dir,
        "audios": [{"audio": a, "bytes": os.path.getsize(a)} for a in files],
        "enviado_para": services,
        "chaves_faltando": missing,
        "ja_existem": clashes,
    }

    if args.so_plano or not args.confirmo_nuvem:
        if args.json:
            emit_json({"pronto": not missing, "enviado": False, **plan})
        else:
            log(f"Plano: {len(files)} áudio(s) → {', '.join(services)}; saída em {output_dir}")
            for a in plan["audios"]:
                log(f"  {a['audio']}  ({a['bytes'] / 1e6:.1f} MB)")
            if missing:
                log(f"  Faltam chaves: {', '.join(missing)}")
            if clashes:
                log(f"  Já existem ({len(clashes)}): use --sobrescrever para substituir")
        if args.so_plano:
            return EXIT_OK
        log("Nada foi enviado. A transcrição sobe o áudio para a nuvem; "
            "repita com --confirmo-nuvem depois de o dono autorizar.")
        return EXIT_NOT_CONFIRMED

    if missing:
        raise CliError(EXIT_CONFIG,
                       f"Chave de API ausente: {', '.join(missing)}. Configure na interface "
                       f"(aba Configurações) ou em DEEPGRAM_API_KEY / ASSEMBLYAI_API_KEY.")
    if clashes and not args.sobrescrever:
        raise CliError(EXIT_EXISTS,
                       "Já existe transcrição: " + "; ".join(clashes) + ". Use --sobrescrever.")

    os.makedirs(output_dir, exist_ok=True)
    quiet = args.silencioso or args.json
    results = []
    for audio in files:
        log(f"→ {os.path.basename(audio)}", args.silencioso)
        results.append(run_one(audio, engine, keys, output_dir, args.academico, args.f, quiet))

    failed = [r for r in results if r["status"] == "erro"]
    if args.json:
        if args.com_texto:
            for r in results:
                target = r["txt"] or r["raw_txt"]
                if target:
                    with open(target, "r", encoding="utf-8") as f:
                        r["texto"] = f.read()
        emit_json({"resultados": results, "ok": len(results) - len(failed), "falhas": len(failed)})
    else:
        for r in results:
            target = r["txt"] or r["raw_txt"]
            if target:
                if len(results) > 1:
                    print(f"===== {os.path.basename(r['audio'])} =====")
                with open(target, "r", encoding="utf-8") as f:
                    sys.stdout.write(f.read())
    for r in results:
        log(f"{os.path.basename(r['audio'])}: {r['status']}"
            + (f" → {r['txt'] or r['raw_txt']}" if r["raw_txt"] else "")
            + (f" ({'; '.join(r['erros'])})" if r["erros"] else ""), args.silencioso)
    return EXIT_ENGINE if failed else EXIT_OK


def _find_meta(target: str, output_dir: str):
    from speaker_manager import load_speaker_metadata, get_meta_path
    output_dir = os.path.abspath(output_dir)
    if target.endswith(".speaker_meta.json") and os.path.exists(target):
        output_dir = os.path.dirname(os.path.abspath(target))
        target = os.path.basename(target)[: -len(".speaker_meta.json")]
    elif os.path.isfile(target) and target.lower().endswith(".txt"):
        output_dir = os.path.dirname(os.path.abspath(target))
    meta = load_speaker_metadata(output_dir, os.path.basename(target))
    if meta is None:
        raise CliError(EXIT_NOT_FOUND,
                       f"Sem metadados de falantes para '{target}' em {output_dir} "
                       f"(procurado: {get_meta_path(output_dir, os.path.basename(target))})")
    return meta, output_dir


def cmd_falantes(args) -> int:
    meta, output_dir = _find_meta(args.alvo, args.saida or DEFAULT_OUTPUT_DIR)
    data = {
        "audio": meta.get("audio_filepath"),
        "txt": meta.get("academic_txt_filepath") or meta.get("txt_filepath"),
        "f": meta.get("f_speaker_id"),
        "f_confirmado": bool(meta.get("is_confirmed")),
        "mapa_falantes": meta.get("speaker_map"),
        "falantes": [
            {k: s.get(k) for k in ("id", "first_time", "first_text", "duration", "pct", "suggested")}
            for s in meta.get("speaker_info", [])
        ],
    }
    if args.json:
        emit_json(data)
    else:
        print(f"F atual: {data['f']} ({'confirmado' if data['f_confirmado'] else 'provisório'})")
        for s in data["falantes"]:
            mark = "  ← sugerido" if s.get("suggested") else ""
            print(f"  [{s['id']}] {s.get('pct', 0):.1f}% da fala, primeira em {s.get('first_time')}: "
                  f"\"{(s.get('first_text') or '')[:60]}\"{mark}")
    return EXIT_OK


def cmd_trocar_f(args) -> int:
    from speaker_manager import update_transcript_speakers
    meta, output_dir = _find_meta(args.alvo, args.saida or DEFAULT_OUTPUT_DIR)
    ids = [s["id"] for s in meta.get("speaker_info", [])] or list(meta.get("speaker_map", {}))
    if args.falante not in ids:
        raise CliError(EXIT_USAGE, f"Falante '{args.falante}' não existe. Disponíveis: {', '.join(ids)}")
    ok, msg = update_transcript_speakers(meta, args.falante, output_dir)
    if args.json:
        emit_json({"ok": ok, "mensagem": msg, "f": args.falante})
    else:
        print(msg)
    return EXIT_OK if ok else EXIT_ENGINE


def cmd_config(args) -> int:
    config = load_config()
    keys = resolve_keys(config)
    data = {
        "config": CONFIG_PATH,
        "config_existe": os.path.exists(CONFIG_PATH),
        "saida_padrao": DEFAULT_OUTPUT_DIR,
        "motor_padrao": default_engine(config),
        "academico_na_interface": bool(config.get("academic_mode", False)),
        "chave_deepgram": keys["deepgram_source"],
        "chave_assemblyai": keys["assemblyai_source"],
        "extensoes": list(AUDIO_EXTENSIONS),
    }
    if args.json:
        emit_json(data)
    else:
        for k, v in data.items():
            print(f"{k}: {v if v is not None else '(ausente)'}")
    return EXIT_OK


# ── Parser ───────────────────────────────────────────────────────────────────

class _Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        log(f"erro: {message}")
        sys.exit(EXIT_USAGE)


def build_parser() -> argparse.ArgumentParser:
    p = _Parser(prog="coelho-cli",
                description="Coelho Transcriber Lite sem janela: transcreve entrevistas (Deepgram ou AssemblyAI).")
    sub = p.add_subparsers(dest="cmd", required=True, parser_class=_Parser)

    t = sub.add_parser("transcrever", help="transcreve áudios (sobe o áudio para a nuvem)")
    t.add_argument("audios", nargs="+", help="arquivos de áudio ou pastas")
    t.add_argument("--motor", choices=["deepgram", "assemblyai"],
                   help="padrão: o modo salvo na interface")
    t.add_argument("--academico", action="store_true",
                   help="formatação acadêmica por LLM (precisa da chave AssemblyAI); gera também *_raw.txt")
    t.add_argument("--f", default="auto",
                   help="falante principal: auto (quem fala mais, provisório), primeiro, ou o id (ex.: 0, A)")
    t.add_argument("--saida", help=f"pasta de saída (padrão: {DEFAULT_OUTPUT_DIR})")
    t.add_argument("--sobrescrever", action="store_true", help="substitui transcrições já existentes")
    t.add_argument("--confirmo-nuvem", action="store_true",
                   help="autoriza o envio do áudio ao serviço; sem isto nada é enviado (saída 4)")
    t.add_argument("--so-plano", action="store_true", help="só mostra o que seria enviado; grátis")
    t.add_argument("--json", action="store_true", help="resumo em JSON no stdout")
    t.add_argument("--com-texto", action="store_true", help="com --json, inclui o texto da transcrição")
    t.add_argument("--silencioso", action="store_true", help="sem log de progresso no stderr")
    t.set_defaults(func=cmd_transcrever)

    f = sub.add_parser("falantes", help="lista os falantes de uma transcrição feita")
    f.add_argument("alvo", help="nome do áudio, a .txt, ou o .speaker_meta.json")
    f.add_argument("--saida", help="pasta das transcrições (padrão: a da interface)")
    f.add_argument("--json", action="store_true")
    f.set_defaults(func=cmd_falantes)

    r = sub.add_parser("trocar-f", help="muda quem é F. numa transcrição feita (sem nova chamada à nuvem)")
    r.add_argument("alvo", help="nome do áudio, a .txt, ou o .speaker_meta.json")
    r.add_argument("--falante", required=True, help="id do falante que passa a ser F.")
    r.add_argument("--saida", help="pasta das transcrições (padrão: a da interface)")
    r.add_argument("--json", action="store_true")
    r.set_defaults(func=cmd_trocar_f)

    c = sub.add_parser("config", help="mostra configuração e de onde vêm as chaves (nunca as chaves)")
    c.add_argument("--json", action="store_true")
    c.set_defaults(func=cmd_config)
    return p


def main(argv=None) -> int:
    _setup_streams()
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except CliError as exc:
        if getattr(args, "json", False):
            emit_json({"erro": str(exc), "codigo": exc.code})
        log(f"erro: {exc}")
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
