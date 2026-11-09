"""
updater.py — Auto-update system for Coelho Transcriber Lite.

Handles version checking against GitHub Releases, background asset download,
elevation check, and automated application update and relaunch.
"""

import os
import sys
import time
import re
import tempfile
import zipfile
import subprocess
from typing import Tuple, Optional

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication

APP_VERSION = "1.1.0"
GITHUB_REPO = "saulorrp/coelho_transcriber_lite"


def parse_version(v_str: str) -> Tuple[int, int, int]:
    """Parse a version string (e.g. 'v1.1.0', '1.1') into a comparable tuple of (major, minor, patch)."""
    match = re.search(r'(\d+)(?:\.(\d+))?(?:\.(\d+))?', str(v_str))
    if match:
        major = int(match.group(1)) if match.group(1) is not None else 0
        minor = int(match.group(2)) if match.group(2) is not None else 0
        patch = int(match.group(3)) if match.group(3) is not None else 0
        return (major, minor, patch)
    return (0, 0, 0)


class UpdateCheckWorker(QThread):
    """
    Background worker that queries GitHub Releases API for newer versions.
    Emits update_available if a newer version is found, or no_update if up-to-date.
    """
    update_available = pyqtSignal(str, str, str)  # (new_version_tag, release_notes, download_url)
    no_update = pyqtSignal()
    error_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        import httpx
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": f"CoelhoTranscriberLite/{APP_VERSION}",
            }
            with httpx.Client(timeout=8.0, follow_redirects=True) as client:
                resp = client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    tag_name = data.get("tag_name", "").strip()
                    body = data.get("body", "")
                    assets = data.get("assets", [])

                    # Find download url for the release zip asset
                    download_url = ""
                    for asset in assets:
                        name = asset.get("name", "")
                        if name.endswith(".zip"):
                            download_url = asset.get("browser_download_url", "")
                            if "Release" in name or "Coelho" in name:
                                break

                    # If no zip asset found, fall back to zipball_url or html_url
                    if not download_url:
                        download_url = data.get("html_url", f"https://github.com/{GITHUB_REPO}/releases/latest")

                    remote_ver = parse_version(tag_name)
                    local_ver = parse_version(APP_VERSION)

                    if remote_ver > local_ver:
                        self.update_available.emit(tag_name, body, download_url)
                    else:
                        self.no_update.emit()
                else:
                    self.no_update.emit()
        except Exception as e:
            self.error_signal.emit(str(e))
            self.no_update.emit()


class UpdateDownloadWorker(QThread):
    """
    Background worker that downloads the release zip file with percentage progress reporting.
    """
    progress_signal = pyqtSignal(int)      # percentage 0..100
    finished_signal = pyqtSignal(str)      # path to downloaded zip file
    error_signal = pyqtSignal(str)

    def __init__(self, download_url: str, parent=None):
        super().__init__(parent)
        self.download_url = download_url
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        import httpx
        try:
            temp_dir = tempfile.gettempdir()
            dest_file = os.path.join(temp_dir, f"coelho_update_{int(time.time())}.zip")

            headers = {"User-Agent": f"CoelhoTranscriberLite/{APP_VERSION}"}
            with httpx.stream("GET", self.download_url, headers=headers, follow_redirects=True, timeout=60.0) as resp:
                if resp.status_code != 200:
                    self.error_signal.emit(f"Download falhou (HTTP {resp.status_code})")
                    return

                total_bytes = int(resp.headers.get("Content-Length", 0))
                downloaded_bytes = 0

                with open(dest_file, "wb") as f:
                    for chunk in resp.iter_bytes(chunk_size=65536):
                        if self._is_cancelled:
                            return
                        f.write(chunk)
                        downloaded_bytes += len(chunk)
                        if total_bytes > 0:
                            percent = int((downloaded_bytes / total_bytes) * 100)
                            self.progress_signal.emit(min(percent, 100))

            self.finished_signal.emit(dest_file)
        except Exception as e:
            self.error_signal.emit(f"Erro no download: {e}")


def install_and_restart(zip_path: str):
    """
    Extracts update zip, prepares a batch script updater, executes it
    (requesting elevation via UAC if needed), and shuts down the application
    so files can be replaced and the new version launched.
    """
    current_exe = sys.executable
    is_frozen = getattr(sys, 'frozen', False)

    if not is_frozen:
        # Running in dev environment from Python source
        return

    current_dir = os.path.dirname(os.path.abspath(current_exe))
    extract_dir = tempfile.mkdtemp(prefix="coelho_update_extract_")

    # Extract zip archive
    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(extract_dir)

    # Locate executable payload inside extracted contents
    source_payload = extract_dir
    possible_subdirs = [
        os.path.join(extract_dir, "CoelhoTranscriber"),
        os.path.join(extract_dir, "Coelho_Lite_Release", "CoelhoTranscriber"),
    ]
    for sub in possible_subdirs:
        if os.path.exists(os.path.join(sub, "CoelhoTranscriber.exe")):
            source_payload = sub
            break

    # Write updater script
    updater_bat = os.path.join(tempfile.gettempdir(), f"coelho_apply_update_{int(time.time())}.bat")

    bat_content = f"""@echo off
chcp 65001 >nul
:: Wait 2 seconds for main application process to exit
timeout /t 2 /nobreak >nul

:: Retry loop to copy files
set ATTEMPTS=0
:RETRY
set /a ATTEMPTS+=1
xcopy "{source_payload}" "{current_dir}" /E /I /Y >nul 2>&1
if errorlevel 1 (
    if %ATTEMPTS% LSS 15 (
        timeout /t 1 /nobreak >nul
        goto RETRY
    )
)

:: Relaunch the new application
start "" "{current_exe}"

:: Clean up temporary files
timeout /t 3 /nobreak >nul
rmdir /s /q "{extract_dir}" >nul 2>&1
del "{zip_path}" >nul 2>&1
(goto) 2>nul & del "%~f0"
"""
    with open(updater_bat, "w", encoding="utf-8") as f:
        f.write(bat_content)

    # Check whether elevation is required
    needs_admin = False
    test_file = os.path.join(current_dir, f".write_test_{os.getpid()}")
    try:
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
    except Exception:
        needs_admin = True

    if needs_admin:
        # Launch with UAC elevation via powershell
        ps_cmd = f'Start-Process -FilePath "cmd.exe" -ArgumentList "/c `"{updater_bat}`"" -Verb RunAs'
        subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_cmd], shell=False)
    else:
        # Launch directly without console window
        subprocess.Popen(
            ["cmd.exe", "/c", updater_bat],
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )

    # Quit application cleanly
    app = QApplication.instance()
    if app:
        app.quit()
    else:
        sys.exit(0)

