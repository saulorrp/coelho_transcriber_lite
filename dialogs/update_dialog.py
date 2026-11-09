"""
update_dialog.py — Pop-up dialog notifying about new Coelho Transcriber Lite releases.

Allows 1-click download, extraction, automated installation, and application restart.
"""

import os
import sys
import webbrowser
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QTextBrowser, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from updater import APP_VERSION, UpdateDownloadWorker, install_and_restart


class UpdateAvailableDialog(QDialog):
    """
    Modal dialog displaying the latest release version, release notes,
    and a 1-click update action with a live download progress bar.
    """

    def __init__(
        self,
        new_version: str,
        release_notes: str,
        download_url: str,
        parent=None,
        theme=None,
    ):
        super().__init__(parent)
        self.new_version = new_version
        self.release_notes = release_notes
        self.download_url = download_url
        self.download_worker: Optional[UpdateDownloadWorker] = None

        self.theme = theme or {
            "NAME": "day",
            "BG_BASE": "#fffae7",
            "BG_PANEL": "#f3ecce",
            "BG_CARD": "#ffffff",
            "BG_HOVER": "#f7f1d8",
            "BORDER_MID": "#d6caa7",
            "TXT_PRIMARY": "#1c1b18",
            "TXT_SECONDARY": "#6e6754",
            "ACCENT_PRIMARY": "#366f93",
            "ACCENT_HOVER": "#2b5a77",
            "BTN_TEXT": "#ffffff",
        }

        self.setWindowTitle(f"Atualização Disponível — {self.new_version}")
        self.setMinimumWidth(520)
        self.resize(540, 420)

        # Set window icon
        if parent and hasattr(parent, "current_window_icon_path") and os.path.exists(parent.current_window_icon_path):
            self.setWindowIcon(QIcon(parent.current_window_icon_path))
        elif parent and hasattr(parent, "icon_path") and os.path.exists(parent.icon_path):
            self.setWindowIcon(QIcon(parent.icon_path))

        self._init_ui()
        self._apply_stylesheet()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Title / Header
        title_lbl = QLabel(f"🚀 Nova Versão Disponível: {self.new_version}")
        title_lbl.setStyleSheet(f"font-size: 17px; font-weight: bold; color: {self.theme['ACCENT_PRIMARY']};")
        layout.addWidget(title_lbl)

        # Subtitle with version comparison
        current_v = APP_VERSION if APP_VERSION.startswith('v') else f"v{APP_VERSION}"
        subtitle_lbl = QLabel(f"Uma versão mais recente foi encontrada. (Sua versão atual: <b>{current_v}</b>)")
        subtitle_lbl.setStyleSheet(f"font-size: 13px; color: {self.theme['TXT_SECONDARY']};")
        layout.addWidget(subtitle_lbl)

        # Release notes text
        notes_frame = QFrame()
        notes_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {self.theme['BG_CARD']};
                border: 1px solid {self.theme['BORDER_MID']};
                border-radius: 6px;
            }}
        """)
        notes_layout = QVBoxLayout(notes_frame)
        notes_layout.setContentsMargins(12, 12, 12, 12)

        notes_title = QLabel("Novidades desta versão:")
        notes_title.setStyleSheet(f"font-weight: 600; font-size: 12px; color: {self.theme['TXT_PRIMARY']};")
        notes_layout.addWidget(notes_title)

        self.browser = QTextBrowser()
        self.browser.setReadOnly(True)
        self.browser.setOpenExternalLinks(True)
        cleaned_notes = self.release_notes.strip() if self.release_notes else "Melhorias de estabilidade e novos recursos."
        self.browser.setMarkdown(cleaned_notes)
        self.browser.setStyleSheet(f"""
            QTextBrowser {{
                background-color: transparent;
                border: none;
                color: {self.theme['TXT_PRIMARY']};
                font-size: 12px;
            }}
        """)
        notes_layout.addWidget(self.browser)
        layout.addWidget(notes_frame, stretch=1)

        # Progress bar (hidden initially)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(18)
        layout.addWidget(self.progress_bar)

        # Status label
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet(f"font-size: 12px; color: {self.theme['TXT_SECONDARY']};")
        layout.addWidget(self.lbl_status)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Depois")
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        is_frozen = getattr(sys, 'frozen', False)
        if is_frozen:
            self.btn_update = QPushButton("Atualizar Agora")
            self.btn_update.setObjectName("btn_confirm")
            self.btn_update.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_update.clicked.connect(self._start_download)
        else:
            self.btn_update = QPushButton("Ver no GitHub")
            self.btn_update.setObjectName("btn_confirm")
            self.btn_update.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_update.clicked.connect(self._open_in_browser)

        btn_layout.addWidget(self.btn_update)
        layout.addLayout(btn_layout)

    def _open_in_browser(self):
        """Open the release link in web browser (used in dev environment)."""
        webbrowser.open(self.download_url)
        self.accept()

    def _start_download(self):
        """Start downloading the update in a background thread."""
        if not self.download_url:
            self.lbl_status.setText("Erro: URL de download não encontrada.")
            self.lbl_status.setStyleSheet("color: #ff4d4d; font-size: 12px;")
            return

        self.btn_update.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.lbl_status.setText("Baixando atualização...")
        self.lbl_status.setStyleSheet(f"color: {self.theme['TXT_SECONDARY']}; font-size: 12px;")

        self.download_worker = UpdateDownloadWorker(self.download_url, parent=self)
        self.download_worker.progress_signal.connect(self._on_download_progress)
        self.download_worker.finished_signal.connect(self._on_download_finished)
        self.download_worker.error_signal.connect(self._on_download_error)
        self.download_worker.start()

    def _on_download_progress(self, percent: int):
        self.progress_bar.setValue(percent)
        self.lbl_status.setText(f"Baixando atualização... {percent}%")

    def _on_download_error(self, err_msg: str):
        self.lbl_status.setText(f"Falha na atualização: {err_msg}")
        self.lbl_status.setStyleSheet("color: #ff4d4d; font-size: 12px; font-weight: bold;")
        self.btn_update.setEnabled(True)
        self.btn_cancel.setEnabled(True)
        self.btn_cancel.setText("Fechar")

    def _on_download_finished(self, zip_path: str):
        self.progress_bar.setValue(100)
        self.lbl_status.setText("Instalando atualização e reiniciando...")
        self.lbl_status.setStyleSheet(f"color: {self.theme['ACCENT_PRIMARY']}; font-size: 12px; font-weight: bold;")

        # Run updater installer script & restart
        install_and_restart(zip_path)
        self.accept()

    def _apply_stylesheet(self):
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {self.theme['BG_BASE']};
            }}
            QLabel {{
                color: {self.theme['TXT_PRIMARY']};
            }}
            QProgressBar {{
                border: 1px solid {self.theme['BORDER_MID']};
                border-radius: 4px;
                background-color: {self.theme['BG_CARD']};
                text-align: center;
                color: {self.theme['TXT_PRIMARY']};
                font-size: 11px;
                font-weight: 600;
            }}
            QProgressBar::chunk {{
                background-color: {self.theme['ACCENT_PRIMARY']};
                border-radius: 3px;
            }}
            QPushButton {{
                font-size: 13px;
                border-radius: 6px;
                padding: 8px 18px;
                border: 1px solid {self.theme['BORDER_MID']};
                background-color: {self.theme['BG_CARD']};
                color: {self.theme['TXT_PRIMARY']};
            }}
            QPushButton:hover {{
                background-color: {self.theme['BG_HOVER']};
            }}
            QPushButton#btn_confirm {{
                background-color: {self.theme['ACCENT_PRIMARY']};
                color: {self.theme['BTN_TEXT']};
                border: none;
                font-weight: 600;
            }}
            QPushButton#btn_confirm:hover {{
                background-color: {self.theme['ACCENT_HOVER']};
            }}
            QPushButton#btn_confirm:disabled {{
                background-color: {self.theme['BORDER_MID']};
                color: {self.theme['TXT_SECONDARY']};
            }}
        """)

