"""
SpeakerSelectionDialog — Modal dialog allowing selection of the primary speaker (F.).

Supports:
- Auto-countdown timer during batch processing so queues never stall.
- Post-processing selection on already completed transcripts.
- Explicit pause, decide-later, and abort controls.
"""

import os
from typing import Optional, List, Tuple

from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QRadioButton, QButtonGroup, QScrollArea, QFrame
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon


def format_time_helper(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"


class SpeakerSelectionDialog(QDialog):
    """
    Modal dialog displaying detected speakers and allowing the user to
    designate which speaker is F.
    """

    def __init__(
        self,
        speaker_info: List[dict],
        parent=None,
        theme=None,
        auto_timeout_sec: int = 0,
        current_f: Optional[str] = None,
        filename: str = "",
    ):
        super().__init__(parent)
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
        
        display_title = "Selecionar Falante Principal (F.)"
        if filename:
            display_title += f" — {filename}"
        self.setWindowTitle(display_title)
        self.setMinimumWidth(540)

        # Set window icon
        if parent and hasattr(parent, "current_window_icon_path") and os.path.exists(parent.current_window_icon_path):
            self.setWindowIcon(QIcon(parent.current_window_icon_path))
        elif parent and hasattr(parent, "icon_path") and os.path.exists(parent.icon_path):
            self.setWindowIcon(QIcon(parent.icon_path))

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {self.theme['BG_BASE']};
            }}
            QLabel {{
                color: {self.theme['TXT_PRIMARY']};
            }}
            QRadioButton {{
                color: {self.theme['TXT_PRIMARY']};
                font-size: 13px;
                spacing: 8px;
            }}
            QRadioButton::indicator {{
                width: 16px;
                height: 16px;
                border: 2px solid {self.theme['BORDER_MID']};
                border-radius: 9px;
                background-color: {self.theme['BG_CARD']};
            }}
            QRadioButton::indicator:checked {{
                background-color: {self.theme['ACCENT_PRIMARY']};
                border-color: {self.theme['ACCENT_PRIMARY']};
            }}
            QPushButton {{
                font-size: 13px;
                border-radius: 6px;
                padding: 8px 16px;
            }}
            QPushButton#btn_confirm {{
                background-color: {self.theme['ACCENT_PRIMARY']};
                color: {self.theme['BTN_TEXT']};
                font-weight: bold;
                border: none;
            }}
            QPushButton#btn_confirm:hover {{
                background-color: {self.theme['ACCENT_HOVER']};
            }}
            QPushButton#btn_confirm:disabled {{
                background-color: {self.theme['BORDER_MID']};
                color: {self.theme['TXT_SECONDARY']};
            }}
            QPushButton#btn_later {{
                background-color: transparent;
                color: {self.theme['TXT_PRIMARY']};
                border: 1px solid {self.theme['BORDER_MID']};
            }}
            QPushButton#btn_later:hover {{
                background-color: {self.theme['BG_HOVER']};
            }}
            QPushButton#btn_pause {{
                background-color: transparent;
                color: {self.theme['TXT_SECONDARY']};
                border: 1px solid {self.theme['BORDER_MID']};
                font-size: 11px;
                padding: 4px 10px;
            }}
            QPushButton#btn_pause:hover {{
                background-color: {self.theme['BG_HOVER']};
                color: {self.theme['TXT_PRIMARY']};
            }}
            QPushButton#btn_abort {{
                background-color: transparent;
                color: #ff5555;
                border: none;
                font-size: 12px;
                text-decoration: underline;
            }}
            QPushButton#btn_abort:hover {{
                color: #ff2222;
            }}
        """)

        self.selected_id: Optional[str] = None
        self.is_confirmed: bool = False
        self.is_aborted: bool = False
        self._speaker_info = speaker_info
        self._countdown_remaining = auto_timeout_sec
        self._timer: Optional[QTimer] = None

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 20, 24, 20)

        # Header Title
        title_text = "Quem é o falante principal (F.)?"
        title = QLabel(title_text)
        title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {self.theme['TXT_PRIMARY']};")
        layout.addWidget(title)

        subtitle = QLabel(
            "O sistema detectou os seguintes falantes. "
            "Selecione quem deve ser marcado como F. na transcrição."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color: {self.theme['TXT_SECONDARY']}; font-size: 12px; margin-bottom: 2px;")
        layout.addWidget(subtitle)

        # Countdown Timer Bar (if auto_timeout_sec > 0)
        self.timer_widget = QWidget()
        timer_layout = QHBoxLayout(self.timer_widget)
        timer_layout.setContentsMargins(10, 6, 10, 6)
        timer_layout.setSpacing(8)
        self.timer_widget.setStyleSheet(
            f"background-color: {self.theme['BG_PANEL']}; border-radius: 6px; border: 1px dashed {self.theme['BORDER_MID']};"
        )

        self.lbl_countdown = QLabel()
        self.lbl_countdown.setStyleSheet(f"font-size: 12px; color: {self.theme['TXT_PRIMARY']}; font-weight: 500;")
        timer_layout.addWidget(self.lbl_countdown, stretch=1)

        self.btn_pause_timer = QPushButton("⏸ Pausar tempo")
        self.btn_pause_timer.setObjectName("btn_pause")
        self.btn_pause_timer.clicked.connect(self._pause_timer)
        timer_layout.addWidget(self.btn_pause_timer)

        if auto_timeout_sec > 0:
            layout.addWidget(self.timer_widget)
            self._update_timer_label()
            self._timer = QTimer(self)
            self._timer.setInterval(1000)
            self._timer.timeout.connect(self._on_timer_tick)
            self._timer.start()
        else:
            self.timer_widget.setVisible(False)

        # Speaker cards container inside QScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"QScrollArea {{ background-color: {self.theme['BG_BASE']}; border: none; }}")

        cards_widget = QWidget()
        cards_widget.setStyleSheet(f"QWidget {{ background-color: {self.theme['BG_BASE']}; }}")
        cards_layout = QVBoxLayout(cards_widget)
        cards_layout.setSpacing(10)
        cards_layout.setContentsMargins(0, 0, 6, 0)

        self._btn_group = QButtonGroup(self)
        self._btn_group.setExclusive(True)

        # Pre-selection logic:
        # If current_f is provided, pick current_f.
        # Otherwise, pick the suggested speaker.
        suggested_id = None
        for info in speaker_info:
            if info.get("suggested"):
                suggested_id = info["id"]
        if not suggested_id and speaker_info:
            suggested_id = speaker_info[0]["id"]

        target_preselect = current_f if current_f else suggested_id

        for i, info in enumerate(speaker_info):
            is_active = (info["id"] == target_preselect)
            card = self._build_speaker_card(i, info, is_active)
            cards_layout.addWidget(card)

        cards_layout.addStretch()
        scroll.setWidget(cards_widget)
        layout.addWidget(scroll, stretch=1)

        # Bottom row with buttons
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(10)

        self.btn_abort = QPushButton("Abortar fila")
        self.btn_abort.setObjectName("btn_abort")
        self.btn_abort.setToolTip("Cancelar e interromper toda a transcrição")
        self.btn_abort.clicked.connect(self._on_abort_clicked)
        bottom_row.addWidget(self.btn_abort)

        bottom_row.addStretch()

        self.btn_later = QPushButton("Decidir depois (usar sugerido)")
        self.btn_later.setObjectName("btn_later")
        self.btn_later.setToolTip("Aplica o falante sugerido agora e permite alterar depois")
        self.btn_later.clicked.connect(self._on_later_clicked)
        bottom_row.addWidget(self.btn_later)

        self.btn_confirm = QPushButton("Confirmar seleção")
        self.btn_confirm.setObjectName("btn_confirm")
        self.btn_confirm.clicked.connect(self._on_confirm_clicked)
        bottom_row.addWidget(self.btn_confirm)

        layout.addLayout(bottom_row)

        self._btn_group.buttonClicked.connect(self._on_radio_clicked)

        # Set initial selected_id
        self.selected_id = target_preselect
        self.btn_confirm.setEnabled(bool(self.selected_id))

        self.resize(560, min(580, 220 + len(speaker_info) * 110))

    def _build_speaker_card(self, index: int, info: dict, is_checked: bool) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {self.theme['BG_CARD']};
                border: 1px solid {self.theme['BORDER_MID']};
                border-radius: 6px;
                padding: 12px;
            }}
            QFrame:hover {{
                border-color: {self.theme['ACCENT_PRIMARY']};
            }}
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(6)
        card_layout.setContentsMargins(12, 10, 12, 10)

        # Top row: radio + speaker ID + badge
        top_row = QHBoxLayout()
        radio = QRadioButton(f"Falante {info['id']}")
        radio.setStyleSheet(f"font-weight: bold; font-size: 14px; color: {self.theme['TXT_PRIMARY']};")
        self._btn_group.addButton(radio, index)
        top_row.addWidget(radio)

        if info.get("suggested"):
            badge = QLabel("SUGERIDO (MAIOR FALA)")
            badge.setStyleSheet(
                f"background-color: {self.theme['ACCENT_PRIMARY']}; color: {self.theme['BTN_TEXT']}; "
                f"font-size: 10px; font-weight: bold; padding: 2px 8px; border-radius: 3px;"
            )
            top_row.addWidget(badge)

        top_row.addStretch()

        if is_checked:
            radio.setChecked(True)

        # Stats row
        duration_str = format_time_helper(info.get("duration", 0))
        pct = info.get("pct", 0)
        first_time = info.get("first_time", "00:00")
        stats = QLabel(
            f"Tempo de fala: {duration_str}  ·  {pct:.1f}% do total  ·  "
            f"Primeira fala em {first_time}"
        )
        stats.setStyleSheet(f"color: {self.theme['TXT_SECONDARY']}; font-size: 12px;")

        # Preview row
        preview_text = info.get("first_text", "")
        if len(preview_text) > 85:
            preview_text = preview_text[:85] + "…"
        preview = QLabel(f'"{preview_text}"')
        preview.setWordWrap(True)
        preview.setStyleSheet(f"color: {self.theme['TXT_SECONDARY']}; font-style: italic; font-size: 12px;")

        card_layout.addLayout(top_row)
        card_layout.addWidget(stats)
        card_layout.addWidget(preview)

        return card

    def _update_timer_label(self):
        self.lbl_countdown.setText(
            f"⏳ Aplicando falante sugerido em {self._countdown_remaining}s para não pausar a fila…"
        )

    def _on_timer_tick(self):
        self._countdown_remaining -= 1
        if self._countdown_remaining <= 0:
            if self._timer:
                self._timer.stop()
            # Timeout expired: accept suggested speaker provisorily
            self.is_confirmed = False
            self.accept()
        else:
            self._update_timer_label()

    def _pause_timer(self):
        if self._timer and self._timer.isActive():
            self._timer.stop()
            self.lbl_countdown.setText("⏸ Tempo pausado. Selecione o falante com calma.")
            self.btn_pause_timer.setText("▶ Retomar")
        elif self._timer:
            self._timer.start()
            self._update_timer_label()
            self.btn_pause_timer.setText("⏸ Pausar tempo")

    def _on_radio_clicked(self, button):
        # User explicitly interacted — pause timer so they don't feel rushed
        if self._timer and self._timer.isActive():
            self._pause_timer()

        idx = self._btn_group.id(button)
        if 0 <= idx < len(self._speaker_info):
            self.selected_id = self._speaker_info[idx]["id"]
            self.btn_confirm.setEnabled(True)

    def _on_confirm_clicked(self):
        if self._timer:
            self._timer.stop()
        self.is_confirmed = True
        self.accept()

    def _on_later_clicked(self):
        if self._timer:
            self._timer.stop()
        # Fall back to suggested speaker if not explicitly selected
        if not self.selected_id:
            for info in self._speaker_info:
                if info.get("suggested"):
                    self.selected_id = info["id"]
                    break
            if not self.selected_id and self._speaker_info:
                self.selected_id = self._speaker_info[0]["id"]
        self.is_confirmed = False
        self.accept()

    def _on_abort_clicked(self):
        if self._timer:
            self._timer.stop()
        self.is_aborted = True
        self.reject()

    def closeEvent(self, event):
        """If user closes via 'X', accept suggested without aborting."""
        if self._timer:
            self._timer.stop()
        if not self.is_aborted and not self.is_confirmed and self.selected_id is None:
            for info in self._speaker_info:
                if info.get("suggested"):
                    self.selected_id = info["id"]
                    break
            if not self.selected_id and self._speaker_info:
                self.selected_id = self._speaker_info[0]["id"]
            self.is_confirmed = False
        super().closeEvent(event)

    @staticmethod
    def select_speaker(
        speaker_info: List[dict],
        parent=None,
        theme=None,
        auto_timeout_sec: int = 0,
        current_f: Optional[str] = None,
        filename: str = "",
    ) -> Tuple[Optional[str], bool, bool]:
        """
        Convenience method to show the dialog.
        Returns:
            (selected_speaker_id, is_confirmed_by_user, is_aborted)
        """
        dlg = SpeakerSelectionDialog(
            speaker_info,
            parent=parent,
            theme=theme,
            auto_timeout_sec=auto_timeout_sec,
            current_f=current_f,
            filename=filename,
        )
        result = dlg.exec()

        if dlg.is_aborted:
            return None, False, True

        # If accepted or closed with 'X', return selected_id (or fallback suggested)
        chosen = dlg.selected_id
        if not chosen:
            for info in speaker_info:
                if info.get("suggested"):
                    chosen = info["id"]
                    break
            if not chosen and speaker_info:
                chosen = speaker_info[0]["id"]

        return chosen, dlg.is_confirmed, False
