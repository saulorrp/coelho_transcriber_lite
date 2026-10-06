@echo off

:: ─── Safety Net ───────────────────────────────────────────────────
if /i "%~1"=="GO" goto :MAIN
cmd /c "%~f0" GO || pause
exit /b

:MAIN
cd /d "%~dp0"
setlocal enabledelayedexpansion

:: ─── Header ───────────────────────────────────────────────────────
echo.
echo                                                80  000                      
echo                                                800  008008                   
echo                                                0000 80   0000                
echo                                                80 00  80    000              
echo                                                808  00  01    800            
echo                                                 08    00 10     00            
echo                                                 000     00 08   808          
echo                                                  000      0000   00          
echo                                                   0008     00   808          
echo                                                     80000        8800        
echo                                                          8008         808      
echo                                                           001          801      
echo                                                          801            001    
echo                 008000    888                      00000                801    
echo               1108   8000088808000000888800000000001                     801    
echo                 00008                 88888                      00088 001    
echo                    80                                         00 88801      
echo                    00                                         001          
echo                  800                                         001            
echo             000008                                            0081          
echo         8000                    800000000000008088080008         80008      
echo     80000                      008              888   8008          80008  
echo  80000      000000008       080008                   800000000088    001 
echo  08    00008        800000008                                   80008  0011
echo  0000008                                                            8000001
echo.
echo ===================================================
echo              Coelho95 Transcriber - Setup
echo ===================================================
echo.

:: ─── Admin Check ──────────────────────────────────────────────────
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] This script must be run as Administrator.
    echo Right-click the file and select "Run as administrator".
    echo.
    pause
    exit /b 1
)

:: ─── File Generation ──────────────────────────────────────────────
echo [1/8] Generating project files...

if not exist "components" mkdir "components"

powershell -NoProfile -Command "$c = [System.IO.File]::ReadAllText('%~f0'); $m = [regex]::Match($c, '(?s)\[BEGIN_TRANSCRIBER\]\r?\n(.*?)\r?\n\[END_TRANSCRIBER\]'); if ($m.Success) { [System.IO.File]::WriteAllText('components\transcriber.py', $m.Groups[1].Value, [System.Text.Encoding]::UTF8) }"
if %errorlevel% neq 0 (echo [ERROR] Failed to extract transcriber.py. & pause & exit /b 1)

powershell -NoProfile -Command "$c = [System.IO.File]::ReadAllText('%~f0'); $m = [regex]::Match($c, '(?s)\[BEGIN_REQUIREMENTS\]\r?\n(.*?)\r?\n\[END_REQUIREMENTS\]'); if ($m.Success) { [System.IO.File]::WriteAllText('components\requirements.txt', $m.Groups[1].Value, [System.Text.Encoding]::UTF8) }"
if %errorlevel% neq 0 (echo [ERROR] Failed to extract requirements.txt. & pause & exit /b 1)

powershell -NoProfile -Command "$c = [System.IO.File]::ReadAllText('%~f0'); $m = [regex]::Match($c, '(?s)\[BEGIN_UNINSTALLER\]\r?\n(.*?)\r?\n\[END_UNINSTALLER\]'); if ($m.Success) { [System.IO.File]::WriteAllText('components\desinstalar.bat', $m.Groups[1].Value, [System.Text.Encoding]::UTF8) }"
if %errorlevel% neq 0 (echo [ERROR] Failed to extract desinstalar.bat. & pause & exit /b 1)

echo  [SUCCESS] All files generated successfully in 'components' folder.

:: ─── FFmpeg Check ─────────────────────────────────────────────────
echo [2/8] Checking system prerequisites ^(FFmpeg^)...
ffmpeg -version >nul 2>&1
if %errorlevel% equ 0 goto :FFMPEG_OK

echo [!] FFmpeg not found. Installing via winget...
winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
call :REFRESH_PATH
ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Failed to verify FFmpeg.
    pause
    exit /b 1
)
echo  [SUCCESS] FFmpeg installed.
:FFMPEG_OK

:: ─── Git Check ────────────────────────────────────────────────────
echo [3/8] Checking system prerequisites ^(Git^)...
git --version >nul 2>&1
if %errorlevel% equ 0 goto :GIT_OK

echo [!] Git not found. Installing via winget...
winget install -e --id Git.Git --accept-source-agreements --accept-package-agreements
call :REFRESH_PATH
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Failed to verify Git.
    pause
    exit /b 1
)
echo  [SUCCESS] Git installed.
:GIT_OK

:: ─── Visual C++ Redistributable Check ─────────────────────────────
echo [4/8] Checking system prerequisites ^(C++ Redistributable^)...
winget list --id Microsoft.VCRedist.2015+.x64 --exact 2>nul | findstr /i "Microsoft.VCRedist" >nul 2>&1
if %errorlevel% equ 0 goto :VCREDIST_OK

echo [!] Visual C++ Redistributable not found. Installing via winget...
winget install -e --id Microsoft.VCRedist.2015+.x64 --accept-source-agreements --accept-package-agreements
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install C++ Redistributable.
    pause
    exit /b 1
)
echo  [SUCCESS] C++ Redistributable installed.
:VCREDIST_OK

:: ─── Python 3.10–3.13 Detection ─────────────────────────────────
echo [5/8] Checking Python 3.10-3.13 installation...
set "PYTHON_EXE="
set "PY_MINOR="

:: 1. Registry (via PowerShell)
for %%v in (13 12 11 10) do (
    for /f "delims=" %%p in ('powershell -NoProfile -Command "try { (Get-ItemProperty -Path 'HKLM:\SOFTWARE\Python\PythonCore\3.%%v\InstallPath' -Name '(Default)').'(Default)' } catch { try { (Get-ItemProperty -Path 'HKCU:\SOFTWARE\Python\PythonCore\3.%%v\InstallPath' -Name '(Default)').'(Default)' } catch { } }" 2^>nul') do (
        if exist "%%p\python.exe" (
            set "PYTHON_EXE=%%p\python.exe"
            set "PY_MINOR=%%v"
            echo [INFO] Found Python 3.!PY_MINOR! via registry at "!PYTHON_EXE!"
            goto :PYTHON_OKAY
        )
    )
)

:: 2. Hardcoded paths
for %%v in (313 312 311 310) do (
    if exist "C:\Program Files\Python%%v\python.exe" (
        "C:\Program Files\Python%%v\python.exe" -c "import sys; print(sys.version_info.minor)" >nul 2>&1
        if !errorlevel! equ 0 (
            set "PYTHON_EXE=C:\Program Files\Python%%v\python.exe"
            set "PY_MINOR=%%v"
            set "PY_MINOR=!PY_MINOR:~1!"
            goto :PYTHON_OKAY
        )
    )
    if exist "%LocalAppData%\Programs\Python\Python%%v\python.exe" (
        "%LocalAppData%\Programs\Python\Python%%v\python.exe" -c "import sys; print(sys.version_info.minor)" >nul 2>&1
        if !errorlevel! equ 0 (
            set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python%%v\python.exe"
            set "PY_MINOR=%%v"
            set "PY_MINOR=!PY_MINOR:~1!"
            goto :PYTHON_OKAY
        )
    )
)

:: 3. PATH commands
python -c "import sys; print(sys.version_info.minor)" >nul 2>&1
if !errorlevel! equ 0 (
    for /f "delims=" %%m in ('python -c "import sys; print(sys.version_info.minor)"') do set "PY_MINOR=%%m"
    if !PY_MINOR! geq 10 if !PY_MINOR! leq 13 (
        set "PYTHON_EXE=python"
        echo [INFO] Found Python 3.!PY_MINOR! via PATH command.
        goto :PYTHON_OKAY
    )
)

for %%v in (3.13 3.12 3.11 3.10) do (
    py -%%v -c "import sys; print(sys.version_info.minor)" >nul 2>&1
    if !errorlevel! equ 0 (
        for /f "delims=" %%m in ('py -%%v -c "import sys; print(sys.version_info.minor)"') do set "PY_MINOR=%%m"
        set "PYTHON_EXE=py -%%v"
        echo [INFO] Found Python 3.!PY_MINOR! via py launcher.
        goto :PYTHON_OKAY
    )
)

:: 4. None found → download
echo [!] No compatible Python (3.10-3.13) found.
echo [!] Downloading Python 3.12.8 (all-users install)...
set "PY_URL=https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe"
set "PY_INSTALLER=python_installer.exe"

powershell -NoProfile -Command "try { Invoke-WebRequest -Uri '%PY_URL%' -OutFile '%PY_INSTALLER%' -UseBasicParsing; exit 0 } catch { exit 1 }"
if !errorlevel! neq 0 (
    echo [ERROR] Download failed. Check internet.
    pause & exit /b 1
)
if not exist %PY_INSTALLER% (
    echo [ERROR] Installer file was not created.
    pause & exit /b 1
)
for %%A in (%PY_INSTALLER%) do if %%~zA LEQ 1024 (
    echo [ERROR] Downloaded file is too small [%%~zA bytes] - download failed.
    del %PY_INSTALLER% 2>nul
    pause & exit /b 1
)

echo [!] Installing Python 3.12.8 silently (this may take a minute)...
start /wait %PY_INSTALLER% /quiet InstallAllUsers=1 PrependPath=1 Include_test=0 DisablePathLengthLimit=1
set "INST_ERR=!errorlevel!"
del %PY_INSTALLER% 2>nul
call :REFRESH_PATH

if !INST_ERR! neq 0 (
    echo [ERROR] Python installer returned error code !INST_ERR!.
    pause & exit /b 1
)

:: Re-check
for %%v in (12) do (
    for /f "delims=" %%p in ('powershell -NoProfile -Command "try { (Get-ItemProperty -Path 'HKLM:\SOFTWARE\Python\PythonCore\3.%%v\InstallPath' -Name '(Default)').'(Default)' } catch { try { (Get-ItemProperty -Path 'HKCU:\SOFTWARE\Python\PythonCore\3.%%v\InstallPath' -Name '(Default)').'(Default)' } catch { } }" 2^>nul') do (
        if exist "%%p\python.exe" (
            set "PYTHON_EXE=%%p\python.exe"
            set "PY_MINOR=%%v"
            echo [INFO] Python 3.12 installed and found.
            goto :PYTHON_OKAY
        )
    )
)
if exist "C:\Program Files\Python312\python.exe" (
    set "PYTHON_EXE=C:\Program Files\Python312\python.exe"
    set "PY_MINOR=12"
) else if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
    set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python312\python.exe"
    set "PY_MINOR=12"
) else (
    py -3.12 -c "import sys; print(sys.version_info.minor)" >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON_EXE=py -3.12"
        set "PY_MINOR=12"
    ) else (
        echo [ERROR] Python 3.12 was installed but could not be located. Restart PC and try again.
        pause & exit /b 1
    )
)

:PYTHON_OKAY
if not defined PY_MINOR (
    echo [WARNING] PY_MINOR was not set. Detecting from Python...
    for /f "usebackq delims=" %%m in (`"!PYTHON_EXE!" -c "import sys; print(sys.version_info.minor)"`) do set "PY_MINOR=%%m"
    echo [INFO] Detected PY_MINOR=!PY_MINOR!
)
echo [INFO] Using Python 3.!PY_MINOR! at "!PYTHON_EXE!"

:: ─── Virtual Environment ──────────────────────────────────────────
if exist venv\ (
    venv\Scripts\python.exe -c "import sys; print(sys.version_info.minor)" 2>&1 | findstr /x "!PY_MINOR!" >nul
    if !errorlevel! neq 0 (
        echo [!] Existing virtual environment is incompatible. Rebuilding...
        rmdir /s /q venv
    ) else (
        echo [INFO] Valid virtual environment found. Skipping creation.
        goto :VENV_OK
    )
)

echo [6/8] Creating virtual environment...
"!PYTHON_EXE!" -m venv venv
if !errorlevel! neq 0 (
    echo [ERROR] Failed to create virtual environment.
    pause & exit /b 1
)

:VENV_OK
echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat
if !errorlevel! neq 0 (
    echo [ERROR] Failed to activate virtual environment.
    pause & exit /b 1
)

echo [INFO] Upgrading pip...
python -m pip install --upgrade pip --retries 3
if !errorlevel! neq 0 (
    echo [WARNING] pip upgrade failed. Continuing with existing pip.
)

:: ─── Dependencies & WhisperX ──────────────────────────────────────
echo [7/8] Installing WhisperX and dependencies...
echo [INFO] Upgrading/Installing WhisperX from GitHub...
pip install --upgrade git+https://github.com/m-bain/whisperx.git --retries 3
if !errorlevel! neq 0 (
    echo [ERROR] WhisperX installation failed.
    pause & exit /b 1
)

if exist "components\requirements.txt" (
    pip install -r components\requirements.txt --retries 3
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to install from requirements.txt.
        pause & exit /b 1
    )
)

:: ─── GPU / CPU Detection & PyTorch Override ───────────────────────
echo [8/8] Detecting GPU support and finalizing PyTorch...

set "FORCE_TORCH_REINSTALL=0"
nvidia-smi >nul 2>&1
if !errorlevel! equ 0 (set "GPU_PRESENT=1") else (set "GPU_PRESENT=0")

if !GPU_PRESENT! equ 1 (
    echo [INFO] NVIDIA GPU detected.
    python -c "import torch; print(torch.cuda.is_available())" 2>nul | findstr /i "True" >nul
    if !errorlevel! equ 0 (
        python -c "import torch; exit(0 if torch.version.cuda else 1)" >nul 2>&1
        if !errorlevel! neq 0 (
            echo [INFO] Existing PyTorch is CPU-only, reinstalling with CUDA...
            set "FORCE_TORCH_REINSTALL=1"
        ) else (
            echo [INFO] Existing PyTorch already supports CUDA. Skipping reinstall.
        )
    ) else (
        echo [INFO] PyTorch CUDA unavailable. Installing CUDA version...
        set "FORCE_TORCH_REINSTALL=1"
    )
) else (
    powershell -NoProfile -Command "(Get-CimInstance Win32_VideoController).Name" | findstr /i "AMD Radeon" >nul 2>&1
    if !errorlevel! equ 0 (echo [INFO] AMD GPU detected. PyTorch will use CPU on Windows.) else (echo [INFO] No NVIDIA GPU detected.)
    echo [INFO] Checking CPU-only PyTorch...
    python -c "import torch" >nul 2>&1
    if !errorlevel! equ 0 (
        echo [INFO] PyTorch already installed. Skipping.
        goto :TORCH_OK
    ) else (
        set "FORCE_TORCH_REINSTALL=1"
    )
)

if !FORCE_TORCH_REINSTALL! equ 1 (
    echo [INFO] Purging incompatible PyTorch...
    pip uninstall -y torch torchvision torchaudio >nul 2>&1
    
	if !GPU_PRESENT! equ 1 (
        if !PY_MINOR! geq 13 (
            echo [INFO] Python 3.13 detected - forcing PyTorch with CUDA 12.4 from official index
            pip install --upgrade torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124 --retries 3
        ) else (
            echo [INFO] Forcing PyTorch with CUDA 12.1 from official index
            pip install --upgrade torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 --retries 3
        )
    ) else (
        echo [DEBUG] Starting PyTorch install for CPU-only...
        pip install --upgrade torch torchvision torchaudio --retries 3
    )
    if !errorlevel! neq 0 (
        echo [ERROR] PyTorch installation failed.
        pause & exit /b 1
    )
)
:TORCH_OK

:: ─── Security Exceptions (venv only) ─────────────────────────────
echo.
echo [INFO] Applying Windows security exceptions to the virtual environment...
powershell -Command "Add-MpPreference -ExclusionPath '%~dp0venv'" >nul 2>&1
powershell -Command "Get-ChildItem -Path '%~dp0' -Recurse -File | Unblock-File" >nul 2>&1
echo [SUCCESS] Virtual environment folder whitelisted.

:: ─── Environment Setup ────────────────────────────────────────────
echo.
if exist .env goto :ENV_OK

echo ===================================================
echo                  API Key Setup
echo ===================================================
echo A Hugging Face token is required for the
echo Pyannote diarization model.
echo.
set /p "HF_TOKEN=Enter your Hugging Face token ^(hf_...^): "

echo TOKEN_HF=!HF_TOKEN!> .env
echo LOGPROB_THRESHOLD=-1.0>> .env

echo [SUCCESS] Token and config saved to .env

:ENV_OK

:: ─── Workspace Setup ──────────────────────────────────────────────
echo.
echo [INFO] Creating project folders...
if not exist "audios para transcricao" mkdir "audios para transcricao"
if not exist "output da transcricao"  mkdir "output da transcricao"

echo [INFO] Creating runner shortcut...
(
    echo @echo off
    echo cd /d "%%~dp0"
    echo echo Iniciando Transcritor...
    echo call venv\Scripts\activate.bat
    echo if errorlevel 1 ^(
    echo     echo [ERROR] Failed to activate virtual environment.
    echo     pause
    echo     exit /b 1
    echo ^)
    echo python components\transcriber.py
    echo if errorlevel 1 ^(
    echo     echo [ERROR] Transcriber exited with an error.
    echo ^)
    echo pause
) > "clique para transcrever.bat"

echo.
echo ===================================================
echo   [SUCCESS] Setup Complete!
echo.
echo   Place audio files in: "audios para transcricao"
echo   Then run: "clique para transcrever.bat"
echo ===================================================
pause
goto :EOF

:: ─── Subroutines ──────────────────────────────────────────────────
:REFRESH_PATH
    setlocal disabledelayedexpansion
    set "SYS_PATH="
    set "USER_PATH="
    for /F "tokens=1,2*" %%a in ('%SystemRoot%\System32\reg.exe query "HKLM\System\CurrentControlSet\Control\Session Manager\Environment" /v PATH 2^>nul ^| findstr /i "PATH"') do (
        if /I "%%a"=="PATH" set "SYS_PATH=%%c"
    )
    for /F "tokens=1,2*" %%a in ('%SystemRoot%\System32\reg.exe query "HKCU\Environment" /v PATH 2^>nul ^| findstr /i "PATH"') do (
        if /I "%%a"=="PATH" set "USER_PATH=%%c"
    )
    endlocal & (
        if defined SYS_PATH (set "SYS_PATH=%SYS_PATH%") else (set "SYS_PATH=")
        if defined USER_PATH (set "USER_PATH=%USER_PATH%") else (set "USER_PATH=")
        set "PATH=%SYS_PATH%;%USER_PATH%;%PATH%"
    )
exit /b

:: ──────────────────────────────────────────────────────────────────
:: PAYLOAD SECTION
:: ──────────────────────────────────────────────────────────────────

[BEGIN_REQUIREMENTS]
transformers>=4.48.0
python-dotenv>=1.0.0
[END_REQUIREMENTS]

[BEGIN_UNINSTALLER]
@echo off
setlocal enabledelayedexpansion
for %%I in ("%~dp0..") do cd /d "%%~fI"
echo.
echo ===================================================
echo         Coelho95 Transcriber - Uninstaller
echo ===================================================
echo WARNING: This will remove the virtual environment
echo and can delete the heavy AI models from your PC.
echo.
set /p CONFIRM="Are you sure you want to proceed? [y/N]: "
if /i "%CONFIRM%" neq "y" (echo Uninstallation cancelled. & pause & exit /b)

echo.
echo [1/4] Removing Virtual Environment (venv)...
if exist venv\ (
    rmdir /s /q venv
    if exist venv\ (echo  [!] Could not delete 'venv'; it may be locked.) else (echo  [+] 'venv' folder deleted.)
) else (echo  [-] 'venv' not found.)

echo.
echo [2/4] Removing Configuration Files...
if exist .env (del /q .env & echo  [+] '.env' deleted.)
if exist "clique para transcrever.bat" (del /q "clique para transcrever.bat" & echo  [+] Runner shortcut deleted.)
if exist "components\transcriber.py" (del /q "components\transcriber.py" & echo  [+] transcriber.py deleted.)
if exist "components\requirements.txt" (del /q "components\requirements.txt" & echo  [+] requirements.txt deleted.)
if exist "components\" (rmdir "components" 2>nul & echo  [+] components folder deleted.)

echo.
echo [3/4] Heavy AI Models (Cache)
echo The AI models (Whisper, Pyannote) are stored in your user cache.
echo WARNING: Other AI tools may share this cache.
set /p DEL_MODELS="Delete downloaded AI models from system cache? [y/N]: "
if /i "%DEL_MODELS%"=="y" (
    if exist "%USERPROFILE%\.cache\whisper" rmdir /s /q "%USERPROFILE%\.cache\whisper"
    if exist "%USERPROFILE%\.cache\huggingface\hub" rmdir /s /q "%USERPROFILE%\.cache\huggingface\hub"
    if exist "%USERPROFILE%\.cache\torch\hub\checkpoints" rmdir /s /q "%USERPROFILE%\.cache\torch\hub\checkpoints"
    echo  [+] Heavy models deleted.
) else (echo  [-] Kept AI models in system cache.)

echo.
echo [4/4] User Files
set /p DEL_FILES="Delete your 'audios' and 'output' folders? [y/N]: "
if /i "%DEL_FILES%"=="y" (
    if exist "audios para transcricao" rmdir /s /q "audios para transcricao"
    if exist "output da transcricao" rmdir /s /q "output da transcricao"
    echo  [+] Media and transcriptions deleted.
) else (echo  [-] Kept media and transcriptions.)

echo.
echo ===================================================
echo   Uninstallation Complete!
echo   You can now delete the Coelho95 folder.
echo ===================================================
pause
[END_UNINSTALLER]

[BEGIN_TRANSCRIBER]
import os, sys, torch, whisperx
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

REGIONAL_PROMPT = (
    "Uhum, hum, ahn, tá, né? Pois é, então, capaz, ah bom. "
    "Mas olha, quando tu vens aqui tu achas que é diferente? "
    "Se tu falasse com o pessoal, tu vias como é. "
    "Tu tens que quando moravas lá. "
    "Se chegasse cedo ou fosse lá, tu ias ver. "
    "Tu sabes, tu tinhas razão. "
    "No frigir dos ovos, é assim mesmo."
)

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
    if logprob is not None and logprob < LOW_CONFIDENCE_THRESHOLD:
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
        vad_options={"vad_onset": 0.300, "vad_offset": 0.800},
        asr_options={"initial_prompt": REGIONAL_PROMPT, "beam_size": 5})

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
[END_TRANSCRIBER]