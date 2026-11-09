import sys
import os
import json
import time
from typing import Optional, List, Dict, Tuple

# Ensure components, widgets, and dialogs directories are in python path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
for sub in ["components", "widgets", "dialogs"]:
    sub_path = os.path.join(BASE_DIR, sub)
    if sub_path not in sys.path:
        sys.path.insert(0, sub_path)
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        meipass_sub = os.path.join(sys._MEIPASS, sub)
        if meipass_sub not in sys.path:
            sys.path.insert(0, meipass_sub)

from speaker_dialog import SpeakerSelectionDialog
from update_dialog import UpdateAvailableDialog
from updater import APP_VERSION, UpdateCheckWorker
from speaker_manager import (
    load_speaker_metadata,
    update_transcript_speakers,
    get_meta_base_name,
)

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QListWidget, QListWidgetItem, QPushButton, QLabel, QLineEdit,
    QTextBrowser, QPlainTextEdit, QTextEdit, QCheckBox, QSlider, QFileDialog, QDialog,
    QButtonGroup, QRadioButton, QFrame, QSizePolicy, QTabWidget, QScrollArea,
    QMessageBox, QComboBox
)
from PyQt6.QtGui import (
    QPainter, QColor, QBrush, QPen, QPaintEvent, QIcon, QPixmap,
    QTextCursor, QTextDocument, QTextFormat, QKeySequence, QShortcut, QFont
)
from PyQt6.QtCore import Qt, QPropertyAnimation, pyqtProperty, QEasingCurve, pyqtSignal, QTimer, QSize, QRect, QThread

from transcription_worker import TranscriptionWorker, AUDIO_EXTENSIONS, format_time

# ==================== COLOR THEMES ====================
THEMES = {
    "dark": {
        "NAME": "dark",
        "BG_BASE": "#0d0d0d",
        "BG_PANEL": "#161616",
        "BG_CARD": "#1e1e1e",
        "BG_HOVER": "#2a2a2a",
        "BORDER_MID": "#333333",
        "TXT_PRIMARY": "#ffffff",
        "TXT_SECONDARY": "#aaaaaa",
        "ACCENT_PRIMARY": "#800000",   # RGBA 800000ff
        "ACCENT_HOVER": "#990000",     # Lighter maroon hover
        "BTN_TEXT": "#ffffff",         # High contrast white on #800000
        "THUMB_COLOR": "#ffffff",
    },
    "day": {
        "NAME": "day",
        "BG_BASE": "#fffae7",          # RGBA fffae7ff
        "BG_PANEL": "#f3ecce",         # Warm cream panel
        "BG_CARD": "#ffffff",          # Crisp white surface
        "BG_HOVER": "#eae0bf",         # Subtle warm hover
        "BORDER_MID": "#d6caa7",       # Warm border
        "TXT_PRIMARY": "#1c1b18",      # High contrast dark text
        "TXT_SECONDARY": "#686253",    # Warm secondary text
        "ACCENT_PRIMARY": "#366f93",   # RGBA 366f93ff for buttons & switches
        "ACCENT_HOVER": "#2c5b79",     # Darker hover state
        "BTN_TEXT": "#ffffff",         # Crisp white text on #366f93
        "THUMB_COLOR": "#ffffff",
    },
}

def get_stylesheet(theme: dict, font_size: int = 13) -> str:
    fs_sm = max(10, font_size - 2)
    fs_base = font_size
    fs_md = font_size + 1
    fs_lg = font_size + 2
    fs_xl = font_size + 4

    return f"""
    QMainWindow {{
        background-color: {theme['BG_BASE']};
    }}
    QWidget {{
        color: {theme['TXT_PRIMARY']};
        font-family: 'Segoe UI', Arial, sans-serif;
        font-size: {fs_base}px;
    }}
    QTabWidget::pane {{
        border: 1px solid {theme['BORDER_MID']};
        border-radius: 8px;
        background-color: {theme['BG_BASE']};
        top: -1px;
    }}
    QTabBar::tab {{
        background-color: {theme['BG_PANEL']};
        color: {theme['TXT_SECONDARY']};
        border: 1px solid {theme['BORDER_MID']};
        border-bottom: none;
        border-top-left-radius: 8px;
        border-top-right-radius: 8px;
        padding: 9px 24px;
        margin-right: 4px;
        font-weight: 600;
        font-size: {fs_md}px;
    }}
    QTabBar::tab:selected {{
        background-color: {theme['BG_CARD']};
        color: {theme['TXT_PRIMARY']};
        border-bottom: 2px solid {theme['ACCENT_PRIMARY']};
    }}
    QTabBar::tab:hover:!selected {{
        background-color: {theme['BG_HOVER']};
        color: {theme['TXT_PRIMARY']};
    }}
    QSplitter::handle {{
        background-color: {theme['BORDER_MID']};
        width: 1px;
    }}
    QListWidget {{
        background-color: {theme['BG_CARD']};
        border: 1px solid {theme['BORDER_MID']};
        border-radius: 6px;
        padding: 4px;
        color: {theme['TXT_PRIMARY']};
        font-size: {fs_base}px;
    }}
    QListWidget::item {{
        padding: 4px 6px;
        border-radius: 4px;
        border-bottom: 1px solid {theme['BORDER_MID']};
    }}
    QListWidget::item:hover {{
        background-color: {theme['BG_HOVER']};
    }}
    QListWidget::item:selected {{
        background-color: {theme['BG_HOVER']};
        color: {theme['TXT_PRIMARY']};
    }}
    QPushButton {{
        background-color: {theme['BG_PANEL']};
        border: 1px solid {theme['BORDER_MID']};
        border-radius: 6px;
        padding: 7px 14px;
        color: {theme['TXT_PRIMARY']};
        font-weight: 500;
        font-size: {fs_base}px;
    }}
    QPushButton:hover {{
        background-color: {theme['BG_HOVER']};
        border-color: {theme['BORDER_MID']};
    }}
    QPushButton:disabled {{
        background-color: {theme['BG_PANEL']};
        color: {theme['TXT_SECONDARY']};
        border-color: {theme['BORDER_MID']};
    }}
    QPushButton#btn_theme {{
        background-color: {theme['BG_CARD']};
        border: 1px solid {theme['BORDER_MID']};
        border-radius: 14px;
        padding: 4px 12px;
        font-size: {fs_lg}px;
        font-weight: bold;
        color: {theme['TXT_PRIMARY']};
    }}
    QPushButton#btn_theme:hover {{
        background-color: {theme['BG_HOVER']};
        border-color: {theme['ACCENT_PRIMARY']};
    }}
    QPushButton#btn_reveal {{
        background-color: {theme['BG_CARD']};
        border: 1px solid {theme['BORDER_MID']};
        border-radius: 6px;
        padding: 7px 12px;
        font-size: {fs_sm}px;
        font-weight: 500;
        color: {theme['TXT_PRIMARY']};
    }}
    QPushButton#btn_reveal:hover {{
        background-color: {theme['BG_HOVER']};
        border-color: {theme['ACCENT_PRIMARY']};
    }}
    QPushButton#btn_abort {{
        background-color: transparent;
        border: 1px solid #d9534f;
        border-radius: 4px;
        padding: 4px 12px;
        color: #d9534f;
        font-size: {fs_sm}px;
        font-weight: 600;
    }}
    QPushButton#btn_abort:hover {{
        background-color: #d9534f;
        color: #ffffff;
    }}
    QPushButton#btn_transcribe {{
        background-color: {theme['ACCENT_PRIMARY']};
        color: {theme['BTN_TEXT']};
        font-weight: bold;
        font-size: {fs_md}px;
        padding: 11px;
        border: none;
        border-radius: 6px;
    }}
    QPushButton#btn_transcribe:hover {{
        background-color: {theme['ACCENT_HOVER']};
    }}
    QPushButton#btn_transcribe:disabled {{
        background-color: {theme['BORDER_MID']};
        color: {theme['TXT_SECONDARY']};
    }}
    QLineEdit {{
        background-color: {theme['BG_CARD']};
        border: 1px solid {theme['BORDER_MID']};
        border-radius: 6px;
        padding: 7px 10px;
        color: {theme['TXT_PRIMARY']};
        font-size: {fs_base}px;
    }}
    QLineEdit:focus {{
        border: 1px solid {theme['ACCENT_PRIMARY']};
    }}
    QLineEdit:disabled {{
        background-color: {theme['BG_PANEL']};
        color: {theme['TXT_SECONDARY']};
        border-color: {theme['BORDER_MID']};
    }}
    QTextBrowser, QPlainTextEdit {{
        background-color: {theme['BG_CARD']};
        border: 1px solid {theme['BORDER_MID']};
        border-radius: 6px;
        padding: 8px;
        color: {theme['TXT_PRIMARY']};
        font-family: Consolas, 'Cascadia Code', 'Courier New', monospace;
        font-size: {fs_base}px;
    }}
    QPlainTextEdit:focus {{
        border: 1.5px solid {theme['ACCENT_PRIMARY']};
    }}
    QCheckBox {{
        color: {theme['TXT_SECONDARY']};
        font-size: {fs_sm}px;
        spacing: 6px;
    }}
    QCheckBox::indicator {{
        width: 15px;
        height: 15px;
        border: 1px solid {theme['BORDER_MID']};
        border-radius: 3px;
        background-color: {theme['BG_CARD']};
    }}
    QCheckBox::indicator:checked {{
        background-color: {theme['ACCENT_PRIMARY']};
        border-color: {theme['ACCENT_PRIMARY']};
    }}
    QSlider::groove:horizontal {{
        border: 1px solid {theme['BORDER_MID']};
        height: 6px;
        background: {theme['BG_CARD']};
        border-radius: 3px;
    }}
    QSlider::sub-page:horizontal {{
        background: {theme['ACCENT_PRIMARY']};
        border-radius: 3px;
    }}
    QSlider::handle:horizontal {{
        background: {theme['ACCENT_PRIMARY']};
        border: 2px solid {theme['BG_CARD']};
        width: 18px;
        margin-top: -6px;
        margin-bottom: -6px;
        border-radius: 9px;
    }}
    QSlider::handle:horizontal:hover {{
        background: {theme['ACCENT_HOVER']};
    }}
    QPushButton#btn_save_primary {{
        background-color: {theme['ACCENT_PRIMARY']};
        color: {theme['BTN_TEXT']};
        font-weight: bold;
        font-size: {fs_base}px;
        padding: 6px 14px;
        border: none;
        border-radius: 6px;
    }}
    QPushButton#btn_save_primary:hover {{
        background-color: {theme['ACCENT_HOVER']};
    }}
    QPushButton#btn_save_primary:disabled {{
        background-color: {theme['BORDER_MID']};
        color: {theme['TXT_SECONDARY']};
    }}
    QPushButton#btn_save_revised {{
        background-color: {theme['BG_CARD']};
        border: 1.5px solid {theme['ACCENT_PRIMARY']};
        color: {theme['TXT_PRIMARY']};
        font-weight: bold;
        font-size: {fs_base}px;
        padding: 6px 14px;
        border-radius: 6px;
    }}
    QPushButton#btn_save_revised:hover {{
        background-color: {theme['BG_HOVER']};
    }}
    QPushButton#btn_save_revised:disabled {{
        background-color: {theme['BG_PANEL']};
        border-color: {theme['BORDER_MID']};
        color: {theme['TXT_SECONDARY']};
    }}
    QPushButton#btn_editor_action {{
        background-color: {theme['BG_CARD']};
        border: 1px solid {theme['BORDER_MID']};
        color: {theme['TXT_PRIMARY']};
        font-size: {fs_sm}px;
        font-weight: 500;
        padding: 6px 12px;
        border-radius: 6px;
    }}
    QPushButton#btn_editor_action:hover {{
        background-color: {theme['BG_HOVER']};
        border-color: {theme['ACCENT_PRIMARY']};
    }}
    QPushButton#btn_tag_chip {{
        background-color: {theme['BG_PANEL']};
        border: 1px solid {theme['BORDER_MID']};
        border-radius: 4px;
        padding: 3px 8px;
        font-family: Consolas, monospace;
        font-size: {fs_sm}px;
        font-weight: 600;
        color: {theme['TXT_PRIMARY']};
    }}
    QPushButton#btn_tag_chip:hover {{
        background-color: {theme['BG_HOVER']};
        border-color: {theme['ACCENT_PRIMARY']};
    }}
    QPushButton#btn_find_nav {{
        background-color: {theme['BG_CARD']};
        border: 1px solid {theme['BORDER_MID']};
        border-radius: 4px;
        padding: 5px 10px;
        font-size: {fs_sm}px;
        color: {theme['TXT_PRIMARY']};
    }}
    QPushButton#btn_find_nav:hover {{
        background-color: {theme['BG_HOVER']};
        border-color: {theme['ACCENT_PRIMARY']};
    }}
    QPushButton#btn_mini_tool {{
        background-color: {theme['BG_CARD']};
        border: 1px solid {theme['BORDER_MID']};
        border-radius: 4px;
        padding: 3px 8px;
        font-size: {fs_sm}px;
        font-weight: 500;
        color: {theme['TXT_SECONDARY']};
    }}
    QPushButton#btn_mini_tool:hover {{
        background-color: {theme['BG_HOVER']};
        color: {theme['TXT_PRIMARY']};
    }}
    QPushButton#btn_close_find {{
        background-color: transparent;
        border: none;
        color: {theme['TXT_SECONDARY']};
        font-size: {fs_md}px;
        font-weight: bold;
    }}
    QPushButton#btn_close_find:hover {{
        color: #ff5555;
    }}
    QLabel {{
        color: {theme['TXT_SECONDARY']};
    }}
    QScrollArea {{
        background-color: {theme['BG_BASE']};
        border: none;
    }}
    QScrollBar:vertical {{
        background-color: {theme['BG_BASE']};
        width: 10px;
        margin: 0px;
        border-radius: 5px;
    }}
    QScrollBar::handle:vertical {{
        background-color: {theme['BORDER_MID']};
        min-height: 20px;
        border-radius: 5px;
    }}
    QScrollBar::handle:vertical:hover {{
        background-color: {theme['BG_HOVER']};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QComboBox {{
        background-color: {theme['BG_CARD']};
        border: 1.5px solid {theme['BORDER_MID']};
        border-radius: 6px;
        padding: 6px 12px;
        color: {theme['TXT_PRIMARY']};
        font-size: {fs_base}px;
        font-weight: 600;
        min-height: 20px;
    }}
    QComboBox:hover {{
        border-color: {theme['ACCENT_PRIMARY']};
    }}
    QComboBox:focus {{
        border-color: {theme['ACCENT_PRIMARY']};
    }}
    QComboBox::drop-down {{
        border: none;
        padding-right: 8px;
        background: transparent;
    }}
    QComboBox QAbstractItemView {{
        background-color: {theme['BG_CARD']};
        border: 1.5px solid {theme['BORDER_MID']};
        border-radius: 6px;
        color: {theme['TXT_PRIMARY']};
        selection-background-color: {theme['ACCENT_PRIMARY']};
        selection-color: {theme['BTN_TEXT']};
        padding: 4px;
        outline: none;
    }}
    QComboBox QAbstractItemView::item {{
        min-height: 26px;
        padding: 6px 10px;
        color: {theme['TXT_PRIMARY']};
        border-radius: 4px;
    }}
    QComboBox QAbstractItemView::item:selected {{
        background-color: {theme['ACCENT_PRIMARY']};
        color: {theme['BTN_TEXT']};
    }}
    QComboBox QAbstractItemView::item:hover {{
        background-color: {theme['BG_HOVER']};
        color: {theme['TXT_PRIMARY']};
    }}
"""


# Note: SpeakerSelectionDialog is loaded from dialogs.speaker_dialog for modularity and maintainability.


# ==================== AUDIO QUEUE ITEM WIDGET ====================
class AudioQueueItemWidget(QWidget):
    """
    Refined custom item widget for the audio queue list with audio icon,
    filename, status badge, speaker assignment button, and remove button.
    """
    removed = pyqtSignal(str)
    select_speaker_requested = pyqtSignal(str)

    def __init__(self, filename: str, filepath: str, theme: dict, font_size: int = 13, parent=None):
        super().__init__(parent)
        self.filename = filename
        self.filepath = filepath
        self.theme = theme
        self.font_size = font_size
        self._is_speaker_confirmed: bool = True

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(8)

        # Audio file symbol
        self.lbl_icon = QLabel("♪")
        self.lbl_icon.setStyleSheet(f"color: {theme['ACCENT_PRIMARY']}; font-weight: bold; font-size: {font_size}px;")
        self.lbl_icon.setFixedWidth(16)

        # Filename
        self.lbl_name = QLabel(filename)
        self.lbl_name.setToolTip(filepath)
        self.lbl_name.setStyleSheet(f"color: {theme['TXT_PRIMARY']}; font-size: {font_size}px; font-weight: 500;")

        # Status badge (Done)
        self.lbl_badge = QLabel("Concluído")
        self.lbl_badge.setStyleSheet(
            f"background-color: {theme['ACCENT_PRIMARY']}; color: {theme['BTN_TEXT']}; "
            f"font-size: {max(10, font_size - 2)}px; font-weight: bold; padding: 2px 8px; border-radius: 4px;"
        )
        self.lbl_badge.setVisible(False)

        # Speaker selection / status button
        self.btn_select_f = QPushButton("Definir F")
        self.btn_select_f.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_select_f.setToolTip("Selecionar ou alterar quem é o falante principal (F.)")
        self.btn_select_f.setVisible(False)
        self.btn_select_f.clicked.connect(lambda: self.select_speaker_requested.emit(self.filepath))

        # Remove button
        self.btn_remove = QPushButton("✕")
        self.btn_remove.setFixedSize(20, 20)
        self.btn_remove.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_remove.setToolTip("Remover este áudio da fila")
        self.btn_remove.setStyleSheet(
            f"QPushButton {{ background-color: transparent; border: none; color: {theme['TXT_SECONDARY']}; font-size: 11px; font-weight: bold; border-radius: 10px; padding: 0px; }}"
            f"QPushButton:hover {{ background-color: #ff5555; color: #ffffff; }}"
        )
        self.btn_remove.clicked.connect(lambda: self.removed.emit(self.filepath))

        layout.addWidget(self.lbl_icon)
        layout.addWidget(self.lbl_name, stretch=1)
        layout.addWidget(self.lbl_badge)
        layout.addWidget(self.btn_select_f)
        layout.addWidget(self.btn_remove)

    def set_done(self, speaker_label: Optional[str] = None, is_confirmed: bool = True):
        self.lbl_badge.setVisible(True)
        self.btn_remove.setVisible(False)
        self._is_speaker_confirmed = is_confirmed
        self._update_speaker_button_style(speaker_label, is_confirmed)
        self.btn_select_f.setVisible(True)

    def set_speaker_confirmed(self, speaker_label: str):
        self._is_speaker_confirmed = True
        self._update_speaker_button_style(speaker_label, is_confirmed=True)

    def is_speaker_confirmed(self) -> bool:
        return self._is_speaker_confirmed

    def _update_speaker_button_style(self, speaker_label: Optional[str] = None, is_confirmed: bool = True):
        fs = max(10, self.font_size - 2)
        if is_confirmed:
            txt = f"Falante: {speaker_label}" if speaker_label else "F Definido"
            self.btn_select_f.setText(txt)
            self.btn_select_f.setToolTip(f"Falante principal confirmado ({speaker_label or 'F'}). Clique para alterar se necessário.")
            self.btn_select_f.setStyleSheet(
                f"QPushButton {{ background-color: transparent; color: {self.theme['TXT_SECONDARY']}; "
                f"border: 1px solid {self.theme['BORDER_MID']}; font-size: {fs}px; font-weight: 500; padding: 2px 8px; border-radius: 4px; }} "
                f"QPushButton:hover {{ border-color: {self.theme['ACCENT_PRIMARY']}; color: {self.theme['TXT_PRIMARY']}; background-color: {self.theme['BG_HOVER']}; }}"
            )
        else:
            self.btn_select_f.setText("⚠️ Definir F")
            self.btn_select_f.setToolTip("Falante F atribuído provisoriamente como sugestão. Clique para definir quem é o F.")
            self.btn_select_f.setStyleSheet(
                f"QPushButton {{ background-color: {self.theme['ACCENT_PRIMARY']}; color: {self.theme['BTN_TEXT']}; "
                f"border: 1px solid {self.theme['ACCENT_PRIMARY']}; font-size: {fs}px; font-weight: bold; padding: 2px 8px; border-radius: 4px; }} "
                f"QPushButton:hover {{ background-color: {self.theme['ACCENT_HOVER']}; }}"
            )

    def is_done(self) -> bool:
        return self.lbl_badge.isVisible()

    def set_removable(self, removable: bool):
        self.btn_remove.setVisible(removable and not self.is_done())

    def set_theme(self, theme: dict, font_size: int = 13):
        self.theme = theme
        self.font_size = font_size
        self.lbl_icon.setStyleSheet(f"color: {theme['ACCENT_PRIMARY']}; font-weight: bold; font-size: {font_size}px;")
        self.lbl_name.setStyleSheet(f"color: {theme['TXT_PRIMARY']}; font-size: {font_size}px; font-weight: 500;")
        self.lbl_badge.setStyleSheet(
            f"background-color: {theme['ACCENT_PRIMARY']}; color: {theme['BTN_TEXT']}; "
            f"font-size: {max(10, font_size - 2)}px; font-weight: bold; padding: 2px 8px; border-radius: 4px;"
        )
        self.btn_remove.setStyleSheet(
            f"QPushButton {{ background-color: transparent; border: none; color: {theme['TXT_SECONDARY']}; font-size: 11px; font-weight: bold; border-radius: 10px; padding: 0px; }}"
            f"QPushButton:hover {{ background-color: #ff5555; color: #ffffff; }}"
        )
        if self.btn_select_f.isVisible():
            self._update_speaker_button_style(
                speaker_label=self.btn_select_f.text().replace("Falante: ", "").replace("⚠️ Definir F", ""),
                is_confirmed=self._is_speaker_confirmed
            )


# ==================== LINE NUMBERED TRANSCRIPT EDITOR ====================
class LineNumberArea(QWidget):
    """
    Left gutter widget that renders line numbers and allows clicking to toggle
    line highlighting.
    """
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Clique no número para destacar ou remover o destaque da linha")

    def sizeHint(self) -> QSize:
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event: QPaintEvent):
        self.editor.line_number_area_paint_event(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.editor.line_number_area_mouse_press_event(event)
        super().mousePressEvent(event)


class TranscriptEditor(QPlainTextEdit):
    """
    Advanced transcription editor with:
    - Clean line numbering in left gutter
    - Click number to highlight whole line (Blue in Day mode, Green in Dark mode)
    - Re-click to remove line highlight
    - Supports multiple simultaneous highlighted lines
    - Seamless theme & font scaling integration
    """
    def __init__(self, parent=None, theme=None, font_size: int = 13):
        super().__init__(parent)
        self.theme = theme or THEMES["day"]
        self.font_size = font_size
        self.highlighted_blocks: set[int] = set()

        self.line_number_area = LineNumberArea(self)

        self.setUndoRedoEnabled(True)
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_lines)

        self.update_line_number_area_width(0)

    def set_theme(self, theme: dict, font_size: int = 13):
        self.theme = theme
        self.font_size = font_size
        self.update_line_number_area_width(0)
        self.highlight_current_lines()
        self.line_number_area.update()

    def clear_highlights(self):
        self.highlighted_blocks.clear()
        self.highlight_current_lines()
        self.line_number_area.update()

    def line_number_area_width(self) -> int:
        digits = 1
        max_num = max(1, self.blockCount())
        while max_num >= 10:
            max_num //= 10
            digits += 1
        digits = max(digits, 2)
        space = 16 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect: QRect, dy: int):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height())
        )

    def line_number_area_mouse_press_event(self, event):
        y = event.pos().y()
        block = self.firstVisibleBlock()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        while block.isValid() and top <= y:
            if block.isVisible() and bottom >= y:
                block_num = block.blockNumber()
                if block_num in self.highlighted_blocks:
                    self.highlighted_blocks.remove(block_num)
                else:
                    self.highlighted_blocks.add(block_num)
                self.highlight_current_lines()
                self.line_number_area.update()
                break
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())

    def get_highlight_color(self) -> QColor:
        if self.theme.get("NAME") == "dark":
            # Soft maroon/wine highlight for dark mode (#800000)
            return QColor(128, 0, 0, 130)
        else:
            # Soft theme blue highlight for day mode
            return QColor(54, 111, 147, 65)

    def highlight_current_lines(self):
        extra_selections = []

        color = self.get_highlight_color()
        for block_num in sorted(self.highlighted_blocks):
            block = self.document().findBlockByNumber(block_num)
            if block.isValid():
                selection = QTextEdit.ExtraSelection()
                selection.format.setBackground(color)
                selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
                cursor = QTextCursor(block)
                selection.cursor = cursor
                extra_selections.append(selection)

        self.setExtraSelections(extra_selections)

    def line_number_area_paint_event(self, event: QPaintEvent):
        painter = QPainter(self.line_number_area)
        
        # Gutter theme colors
        if self.theme.get("NAME") == "dark":
            bg_gutter = QColor("#141414")
            border_gutter = QColor(self.theme.get("BORDER_MID", "#333333"))
            txt_gutter = QColor("#666666")
            txt_highlighted = QColor("#ff7777")
            bg_num_highlight = QColor(128, 0, 0, 95)
        else:
            bg_gutter = QColor("#f2edd9")
            border_gutter = QColor(self.theme.get("BORDER_MID", "#d6caa7"))
            txt_gutter = QColor("#8f8774")
            txt_highlighted = QColor(self.theme.get("ACCENT_PRIMARY", "#366f93"))
            bg_num_highlight = QColor(54, 111, 147, 50)

        painter.fillRect(event.rect(), bg_gutter)
        painter.setPen(QPen(border_gutter, 1))
        painter.drawLine(
            self.line_number_area.width() - 1, event.rect().top(),
            self.line_number_area.width() - 1, event.rect().bottom()
        )

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        font = self.font()
        font.setPointSize(max(9, self.font_size - 2))
        painter.setFont(font)

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number_str = str(block_number + 1)
                is_hl = block_number in self.highlighted_blocks
                
                if is_hl:
                    pill_rect = QRect(2, top + 1, self.line_number_area.width() - 5, bottom - top - 2)
                    painter.fillRect(pill_rect, bg_num_highlight)
                    painter.setPen(txt_highlighted)
                    bold_font = QFont(font)
                    bold_font.setBold(True)
                    painter.setFont(bold_font)
                else:
                    painter.setPen(txt_gutter)
                    painter.setFont(font)

                painter.drawText(
                    0, top, self.line_number_area.width() - 6,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                    number_str
                )

            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1


# ==================== CUSTOM TOGGLE SWITCH ====================
class ToggleSwitch(QWidget):
    toggled = pyqtSignal(bool)
    
    def __init__(self, parent=None, theme=None):
        super().__init__(parent)
        self.setFixedSize(50, 24)
        self._checked = False
        self._position = 3.0
        self.theme = theme or THEMES["day"]
        
        self.animation = QPropertyAnimation(self, b"position")
        self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.animation.setDuration(200)

    def set_theme(self, theme: dict):
        self.theme = theme
        self.update()

    @pyqtProperty(float)
    def position(self):
        return self._position
        
    @position.setter
    def position(self, pos):
        self._position = pos
        self.update()

    def isChecked(self):
        return self._checked
        
    def setChecked(self, checked, animate=True):
        if self._checked == checked:
            return
        self._checked = checked
        if animate:
            self.animation.setEndValue(26.0 if self._checked else 3.0)
            self.animation.start()
        else:
            self._position = 26.0 if self._checked else 3.0
            self.update()
        self.toggled.emit(self._checked)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Background
        bg_color = QColor(self.theme["ACCENT_PRIMARY"]) if self._checked else QColor(self.theme["BG_CARD"])
        border_color = QColor(self.theme["ACCENT_PRIMARY"]) if self._checked else QColor(self.theme["BORDER_MID"])
        
        painter.setBrush(QBrush(bg_color))
        painter.setPen(QPen(border_color, 1.5))
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 12, 12)
        
        # Toggle thumb
        painter.setBrush(QBrush(QColor(self.theme.get("THUMB_COLOR", "#ffffff"))))
        if self.theme.get("NAME") == "day" and not self._checked:
            painter.setPen(QPen(QColor(self.theme["BORDER_MID"]), 1))
        else:
            painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(int(self._position), 3, 18, 18)
        
        painter.end()


# ==================== DEEPGRAM BALANCE WORKER ====================
class DeepgramBalanceWorker(QThread):
    """
    Asynchronous worker that fetches the Deepgram balance using projects and
    balances REST endpoints, safely reporting results back to GUI thread via pyqtSignal.
    """
    result_signal = pyqtSignal(str, bool)  # (result_message, is_error)

    def __init__(self, api_key: str, parent=None):
        super().__init__(parent)
        self.api_key = api_key

    def run(self):
        import httpx
        try:
            headers = {"Authorization": f"Token {self.api_key}"}

            with httpx.Client(timeout=httpx.Timeout(15.0)) as client:
                # Step 1: Query user's projects to get project_id
                r1 = client.get("https://api.deepgram.com/v1/projects", headers=headers)
                if r1.status_code == 401:
                    self.result_signal.emit("Chave de API inválida ou expirada.", True)
                    return
                elif r1.status_code == 403:
                    self.result_signal.emit("Acesso negado (403). Verifique as permissões da chave.", True)
                    return
                elif r1.status_code != 200:
                    self.result_signal.emit(f"Erro Deepgram ({r1.status_code}): {r1.text[:60]}", True)
                    return

                data1 = r1.json()
                projects = data1.get("projects", [])
                if not projects:
                    self.result_signal.emit("Nenhum projeto encontrado nesta conta.", True)
                    return

                project_id = projects[0].get("project_id", "")
                if not project_id:
                    self.result_signal.emit("ID do projeto não encontrado.", True)
                    return

                # Step 2: Query balances for this project
                r2 = client.get(f"https://api.deepgram.com/v1/projects/{project_id}/balances", headers=headers)
                if r2.status_code == 403:
                    self.result_signal.emit("A chave requer permissão Admin/Owner para consultar o saldo.", True)
                    return
                elif r2.status_code != 200:
                    self.result_signal.emit(f"Erro ao consultar saldo ({r2.status_code}).", True)
                    return

                data2 = r2.json()
                balances = data2.get("balances", [])
                if not balances:
                    self.result_signal.emit("Conta pay-as-you-go (sem créditos pré-pagos fixos).", False)
                    return

                bal = balances[0]
                amount = float(bal.get("amount", 0.0))
                units = str(bal.get("units", "USD")).upper()
                self.result_signal.emit(f"Saldo: ${amount:.2f} {units}", False)

        except httpx.TimeoutException:
            self.result_signal.emit("Tempo limite esgotado ao conectar ao Deepgram.", True)
        except Exception as exc:
            self.result_signal.emit(f"Erro de conexão: {exc}", True)


# ==================== MAIN WINDOW ====================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Transcritor de Áudio — v{APP_VERSION}")
        self.resize(1020, 720)

        self.current_theme_name = "day"
        self.current_theme = THEMES["day"]
        self.current_font_size = 13
        self.worker = None          # Reference to the running TranscriptionWorker
        self._audio_paths = []      # Full paths of queued audio files

        # Reader Editor State
        self._current_open_filepath: Optional[str] = None
        self._is_editor_modified = False
        self._ignore_text_changes = False

        self._setup_paths()
        self._init_animation()
        self._init_ui()
        self._load_config()
        self.apply_theme(self.current_theme_name)
        QTimer.singleShot(1500, self._check_for_updates)
        
    def _setup_paths(self):
        """Configure directory paths ensuring compatibility with PyInstaller and components/icons"""
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            self.base_path = sys._MEIPASS
        else:
            self.base_path = os.path.dirname(os.path.abspath(__file__))
            
        self.components_dir = os.path.join(self.base_path, 'components')
        self.icons_dir = os.path.join(self.components_dir, 'icons')
        docs_dir = os.path.join(os.path.expanduser('~'), 'Documents', 'Coelho95 Transcriber')
        self.output_dir = os.path.join(docs_dir, 'output da transcricao')
        self.config_path = os.path.join(docs_dir, 'config.json')

        for d in (self.components_dir, self.icons_dir, self.output_dir):
            if not os.path.exists(d):
                try:
                    os.makedirs(d)
                except Exception as e:
                    print(f"Aviso: Não foi possível criar o diretório {d}: {e}")

        # Helper to search for icon files in components/icons/ and components/
        def find_file(*candidates):
            for d in (self.icons_dir, self.components_dir):
                for name in candidates:
                    full_p = os.path.join(d, name)
                    if os.path.exists(full_p):
                        return full_p
            return os.path.join(self.icons_dir, candidates[0])

        # Day icons
        self.icon_day_ico = find_file('icon.ico', 'icon.png')
        self.icon_day_png = find_file('icon.png', 'icon.ico')
        self.icon2_day_png = find_file('icon2.png', 'icon2.ico')

        # Dark icons (with fallback to day icons)
        self.icon_dark_ico = find_file('icon_dark.ico', 'icon_dark.png', 'icon.ico')
        self.icon_dark_png = find_file('icon_dark.png', 'icon_dark.ico', 'icon.png')
        self.icon2_dark_png = find_file('icon2_dark.png', 'icon2_dark.ico', 'icon2.png')

        # Backwards compatible properties
        self.icon_path = self.icon_day_ico
        self.icon_png_path = self.icon_day_png
        self.icon2_path = find_file('icon2.ico', 'icon2.png')
        self.icon2_png_path = self.icon2_day_png
        self.current_window_icon_path = self.icon_day_ico

    def _init_animation(self):
        """Prepare animation timer and pixmaps for the running rabbit waiting animation."""
        self._anim_frame = 0
        self.anim_timer = QTimer(self)
        self.anim_timer.setInterval(220)  # ~220ms interval between jumping frames
        self.anim_timer.timeout.connect(self._on_anim_tick)
        self._load_theme_icons(self.current_theme_name)

    def _load_theme_icons(self, theme_name: str):
        """Load pixmaps and window icons corresponding to the current theme (day or dark)."""
        if theme_name == "dark":
            window_icon_path = self.icon_dark_ico if os.path.exists(self.icon_dark_ico) else self.icon_dark_png
            p1 = self.icon_dark_png if os.path.exists(self.icon_dark_png) else self.icon_dark_ico
            p2 = self.icon2_dark_png if os.path.exists(self.icon2_dark_png) else p1
        else:
            window_icon_path = self.icon_day_ico if os.path.exists(self.icon_day_ico) else self.icon_day_png
            p1 = self.icon_day_png if os.path.exists(self.icon_day_png) else self.icon_day_ico
            p2 = self.icon2_day_png if os.path.exists(self.icon2_day_png) else p1

        self.current_window_icon_path = window_icon_path
        if os.path.exists(window_icon_path):
            self.setWindowIcon(QIcon(window_icon_path))
            app = QApplication.instance()
            if app:
                app.setWindowIcon(QIcon(window_icon_path))

        size_header = 26
        size_banner = 42

        if os.path.exists(p1):
            self.pix_frame1 = QPixmap(p1).scaled(
                size_header, size_header, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            self.pix_frame1_large = QPixmap(p1).scaled(
                size_banner, size_banner, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
        else:
            self.pix_frame1 = QPixmap()
            self.pix_frame1_large = QPixmap()

        if os.path.exists(p2):
            self.pix_frame2 = QPixmap(p2).scaled(
                size_header, size_header, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            self.pix_frame2_large = QPixmap(p2).scaled(
                size_banner, size_banner, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
        else:
            self.pix_frame2 = self.pix_frame1
            self.pix_frame2_large = self.pix_frame1_large

        # If animation is not currently running, update static icons immediately
        if not (hasattr(self, "anim_timer") and self.anim_timer.isActive()):
            if hasattr(self, "lbl_icon") and not self.pix_frame1.isNull():
                self.lbl_icon.setPixmap(self.pix_frame1)
            if hasattr(self, "lbl_status_icon") and not self.pix_frame1_large.isNull():
                self.lbl_status_icon.setPixmap(self.pix_frame1_large)

    def _on_anim_tick(self):
        """Swap frames when active to create the jumping/running rabbit animation."""
        self._anim_frame = (self._anim_frame + 1) % 2
        current_pix = self.pix_frame1 if self._anim_frame == 0 else self.pix_frame2
        current_pix_large = self.pix_frame1_large if self._anim_frame == 0 else self.pix_frame2_large

        # Banner icon above logs always animates when transcription is active
        if hasattr(self, "lbl_status_icon") and not current_pix_large.isNull():
            self.lbl_status_icon.setPixmap(current_pix_large)

        # Top icon only moves if user is on another tab (not the transcription tab)
        is_on_transcription_tab = hasattr(self, "tab_widget") and self.tab_widget.currentIndex() == 0
        if hasattr(self, "lbl_icon"):
            if is_on_transcription_tab:
                if not self.pix_frame1.isNull():
                    self.lbl_icon.setPixmap(self.pix_frame1)
            else:
                if not current_pix.isNull():
                    self.lbl_icon.setPixmap(current_pix)

    def _start_waiting_animation(self):
        self._anim_frame = 0
        if hasattr(self, "status_banner"):
            self.status_banner.setVisible(True)
        if hasattr(self, "lbl_status_text"):
            self.lbl_status_text.setText("Transcrevendo áudios… Aguarde um instante")
        self.anim_timer.start()

    def _pause_waiting_animation(self, status_text: str = "Aguardando interação do usuário…"):
        """Pause the rabbit jumping animation and display static frame while waiting for dialogs."""
        self.anim_timer.stop()
        self._anim_frame = 0
        if hasattr(self, "lbl_icon") and not self.pix_frame1.isNull():
            self.lbl_icon.setPixmap(self.pix_frame1)
        if hasattr(self, "lbl_status_icon") and not self.pix_frame1_large.isNull():
            self.lbl_status_icon.setPixmap(self.pix_frame1_large)
        if hasattr(self, "lbl_status_text") and status_text:
            self.lbl_status_text.setText(status_text)

    def _resume_waiting_animation(self, status_text: str = "Transcrevendo áudios… Aguarde um instante"):
        """Resume the rabbit jumping animation when transcription work continues."""
        self._anim_frame = 0
        if hasattr(self, "lbl_status_text") and status_text:
            self.lbl_status_text.setText(status_text)
        self.anim_timer.start()

    def _stop_waiting_animation(self):
        self.anim_timer.stop()
        self._anim_frame = 0
        if hasattr(self, "lbl_icon") and not self.pix_frame1.isNull():
            self.lbl_icon.setPixmap(self.pix_frame1)
        if hasattr(self, "lbl_status_icon") and not self.pix_frame1_large.isNull():
            self.lbl_status_icon.setPixmap(self.pix_frame1_large)
        if hasattr(self, "status_banner"):
            self.status_banner.setVisible(False)

    def _on_tab_changed(self, index: int):
        """When switching to the transcription tab, top header icon stays static."""
        if index == 0:
            if hasattr(self, "lbl_icon") and not self.pix_frame1.isNull():
                self.lbl_icon.setPixmap(self.pix_frame1)
        elif hasattr(self, "anim_timer") and self.anim_timer.isActive():
            current_pix = self.pix_frame1 if self._anim_frame == 0 else self.pix_frame2
            if hasattr(self, "lbl_icon") and not current_pix.isNull():
                self.lbl_icon.setPixmap(current_pix)

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 12, 15, 15)
        main_layout.setSpacing(10)

        # ------------------- HEADER / TOP BAR -------------------
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 2)
        header_layout.setSpacing(8)
        
        # UI App Icon (animates when processing and another tab is active)
        self.lbl_icon = QLabel()
        if not self.pix_frame1.isNull():
            self.lbl_icon.setPixmap(self.pix_frame1)
            self.lbl_icon.setFixedSize(26, 26)
            header_layout.addWidget(self.lbl_icon)

        self.lbl_app_title = QLabel("Coelho Transcriber")
        self.lbl_app_title.setStyleSheet("font-size: 15px; font-weight: bold;")
        
        self.btn_theme = QPushButton("☾")
        self.btn_theme.setObjectName("btn_theme")
        self.btn_theme.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_theme.setToolTip("Alternar entre Modo Dia e Modo Noite")
        self.btn_theme.clicked.connect(self._toggle_theme)
        
        header_layout.addWidget(self.lbl_app_title)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_theme)
        
        main_layout.addLayout(header_layout)

        # ------------------- MAIN TAB WIDGET -------------------
        self.tab_widget = QTabWidget()
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        main_layout.addWidget(self.tab_widget)

        # Build Tab 1 (Transcription), Tab 2 (Reader) & Tab 3 (Settings)
        self._build_transcription_tab()
        self._build_reader_tab()
        self._build_settings_tab()

    def _build_transcription_tab(self):
        tab_transcription = QWidget()
        tab_transcription.setObjectName("tab_transcription")
        self.tab_transcription = tab_transcription
        tab_layout = QVBoxLayout(tab_transcription)
        tab_layout.setContentsMargins(10, 10, 10, 10)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        tab_layout.addWidget(splitter)
        
        # ------------------- LEFT PANEL -------------------
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 10, 0)
        
        self.lbl_audios = QLabel("Áudios para transcrição")
        self.lbl_audios.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 5px;")
        
        self.btn_add_audio = QPushButton("+ Adicionar Áudios")
        self.btn_add_audio.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add_audio.clicked.connect(self._on_add_audio)
        
        self.list_audios = QListWidget()
        self.list_audios.setObjectName("list_audios")
        self.list_audios.setSpacing(2)
        
        self.btn_transcribe = QPushButton("Transcrever Fila")
        self.btn_transcribe.setObjectName("btn_transcribe")
        self.btn_transcribe.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_transcribe.clicked.connect(self._on_transcribe)
        
        left_layout.addWidget(self.lbl_audios)
        left_layout.addWidget(self.btn_add_audio)
        left_layout.addWidget(self.list_audios)
        left_layout.addWidget(self.btn_transcribe)
        
        # ------------------- RIGHT PANEL -------------------
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(10, 0, 0, 0)
        
        # Mode Status Header Card
        self.mode_status_card = QFrame()
        self.mode_status_card.setObjectName("mode_status_card")
        status_card_layout = QHBoxLayout(self.mode_status_card)
        status_card_layout.setContentsMargins(14, 10, 14, 10)
        status_card_layout.setSpacing(10)

        self.lbl_active_mode_title = QLabel("Modo:")
        self.lbl_active_mode_title.setStyleSheet("font-size: 13px; font-weight: bold;")

        # Mode selector (2 cloud options)
        self.combo_mode = QComboBox()
        self.combo_mode.setObjectName("combo_mode")
        self.combo_mode.addItems([
            "Transcrição em Nuvem (Deepgram - Nova-3) [Padrão]",
            "Transcrição em Nuvem (AssemblyAI - Universal-3.5)",
        ])
        self.combo_mode.setCurrentIndex(0)  # default: Deepgram
        self.combo_mode.setCursor(Qt.CursorShape.PointingHandCursor)
        self.combo_mode.setToolTip("Selecione o motor de transcrição a ser utilizado")
        self.combo_mode.currentIndexChanged.connect(self._on_mode_changed)

        self.lbl_academic_badge = QLabel("Modo Acadêmico Ativo")
        self.lbl_academic_badge.setStyleSheet(
            f"background-color: {self.current_theme['ACCENT_PRIMARY']}; color: #ffffff; font-size: 11px; "
            "font-weight: bold; padding: 2px 8px; border-radius: 4px;"
        )
        self.lbl_academic_badge.setVisible(False)

        status_card_layout.addWidget(self.lbl_active_mode_title)
        status_card_layout.addWidget(self.combo_mode, stretch=1)
        status_card_layout.addWidget(self.lbl_academic_badge)

        # Running / Waiting Status Banner (Prominent & Elegant with Jumping Rabbit)
        self.status_banner = QFrame()
        self.status_banner.setObjectName("status_banner")
        self.status_banner.setVisible(False)
        banner_layout = QHBoxLayout(self.status_banner)
        banner_layout.setContentsMargins(16, 10, 16, 10)
        banner_layout.setSpacing(12)

        self.lbl_status_icon = QLabel()
        if hasattr(self, "pix_frame1_large") and not self.pix_frame1_large.isNull():
            self.lbl_status_icon.setPixmap(self.pix_frame1_large)
        elif not self.pix_frame1.isNull():
            self.lbl_status_icon.setPixmap(self.pix_frame1)
        self.lbl_status_icon.setFixedSize(42, 42)

        self.lbl_status_text = QLabel("Transcrevendo áudios… Aguarde um instante")
        self.lbl_status_text.setStyleSheet("font-size: 13px; font-weight: 600;")

        self.btn_abort = QPushButton("Abortar")
        self.btn_abort.setObjectName("btn_abort")
        self.btn_abort.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_abort.clicked.connect(self._on_abort)

        banner_layout.addWidget(self.lbl_status_icon)
        banner_layout.addWidget(self.lbl_status_text, stretch=1)
        banner_layout.addWidget(self.btn_abort)
        
        # Logs Section
        self.lbl_logs = QLabel("Logs")
        self.lbl_logs.setStyleSheet("font-size: 14px; font-weight: bold; margin-top: 6px; margin-bottom: 4px;")
        
        self.txt_logs = QTextBrowser()
        self.txt_logs.append("> Sistema iniciado. Aguardando áudios...")
        
        right_layout.addWidget(self.mode_status_card)
        right_layout.addWidget(self.status_banner)
        right_layout.addWidget(self.lbl_logs)
        right_layout.addWidget(self.txt_logs, stretch=1)
        
        # Add panels to splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([340, 660])

        self.tab_widget.addTab(tab_transcription, "Transcrição")

    def _build_reader_tab(self):
        """Tab for browsing, previewing, and editing generated transcriptions."""
        tab_reader = QWidget()
        tab_reader.setObjectName("tab_reader")
        self.tab_reader = tab_reader
        tab_layout = QVBoxLayout(tab_reader)
        tab_layout.setContentsMargins(10, 10, 10, 10)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter_reader = splitter
        tab_layout.addWidget(splitter)

        # ------------------- LEFT PANEL (FILES) -------------------
        left_panel = QWidget()
        self.reader_left_panel = left_panel
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 10, 0)
        left_layout.setSpacing(8)

        lbl_reader_files = QLabel("Transcrições Salvas (.txt)")
        lbl_reader_files.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.lbl_reader_files = lbl_reader_files

        self.btn_refresh_reader = QPushButton("↻ Atualizar Lista")
        self.btn_refresh_reader.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_refresh_reader.clicked.connect(self._refresh_reader_files)

        self.list_transcripts = QListWidget()
        self.list_transcripts.currentItemChanged.connect(self._on_transcript_selected)

        left_layout.addWidget(lbl_reader_files)
        left_layout.addWidget(self.btn_refresh_reader)
        left_layout.addWidget(self.list_transcripts, stretch=1)

        # ------------------- RIGHT PANEL (EDITOR & TOOLS) -------------------
        right_panel = QWidget()
        self.reader_right_panel = right_panel
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(10, 0, 0, 0)
        right_layout.setSpacing(8)

        # Top Action Bar: File Name + Save Buttons + Find Toggle
        top_bar = QWidget()
        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(0, 0, 0, 0)
        top_bar_layout.setSpacing(8)

        self.lbl_reader_filename = QLabel("Nenhum arquivo aberto")
        self.lbl_reader_filename.setStyleSheet("font-size: 14px; font-weight: bold;")

        self.btn_toggle_find = QPushButton("Localizar")
        self.btn_toggle_find.setObjectName("btn_editor_action")
        self.btn_toggle_find.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_find.setToolTip("Alternar barra de busca e substituição (Ctrl+F ou Ctrl+H)")
        self.btn_toggle_find.clicked.connect(self._toggle_find_replace_bar)

        self.btn_save_revised = QPushButton("Salvar como Revisada")
        self.btn_save_revised.setObjectName("btn_save_revised")
        self.btn_save_revised.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save_revised.setToolTip("Salva uma nova versão com sufixo '_revisada.txt'")
        self.btn_save_revised.clicked.connect(self._save_revised_transcript)
        self.btn_save_revised.setEnabled(False)

        self.btn_save_transcript = QPushButton("Salvar (Ctrl+S)")
        self.btn_save_transcript.setObjectName("btn_save_primary")
        self.btn_save_transcript.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save_transcript.setToolTip("Salva as alterações no arquivo atual (Ctrl+S)")
        self.btn_save_transcript.clicked.connect(self._save_current_transcript)
        self.btn_change_speaker = QPushButton("👤 Definir Falante (F.)")
        self.btn_change_speaker.setObjectName("btn_editor_action")
        self.btn_change_speaker.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_change_speaker.setToolTip("Alterar ou definir o falante principal (F.) para esta transcrição")
        self.btn_change_speaker.setEnabled(False)
        self.btn_change_speaker.clicked.connect(self._on_reader_change_speaker_clicked)

        top_bar_layout.addWidget(self.lbl_reader_filename, stretch=1)
        top_bar_layout.addWidget(self.btn_change_speaker)
        top_bar_layout.addWidget(self.btn_toggle_find)
        top_bar_layout.addWidget(self.btn_save_revised)
        top_bar_layout.addWidget(self.btn_save_transcript)

        # ------------------- FIND & REPLACE BAR (COLLAPSIBLE) -------------------
        self.find_replace_card = QFrame()
        self.find_replace_card.setObjectName("find_replace_card")
        self.find_replace_card.setVisible(False)
        find_layout = QVBoxLayout(self.find_replace_card)
        find_layout.setContentsMargins(12, 10, 12, 10)
        find_layout.setSpacing(8)

        # Row 1: Find input + Next/Prev + Count + Close
        find_row1 = QHBoxLayout()
        find_row1.setSpacing(6)

        lbl_find = QLabel("Localizar:")
        lbl_find.setStyleSheet("font-weight: 600; font-size: 12px;")
        self.lbl_find = lbl_find

        self.txt_find = QLineEdit()
        self.txt_find.setPlaceholderText("Texto a pesquisar...")
        self.txt_find.textChanged.connect(self._on_find_text_changed)
        self.txt_find.returnPressed.connect(lambda: self._find_next_match(reverse=False))

        self.btn_find_prev = QPushButton("Anterior")
        self.btn_find_prev.setObjectName("btn_find_nav")
        self.btn_find_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_find_prev.clicked.connect(lambda: self._find_next_match(reverse=True))

        self.btn_find_next = QPushButton("Próximo")
        self.btn_find_next.setObjectName("btn_find_nav")
        self.btn_find_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_find_next.clicked.connect(lambda: self._find_next_match(reverse=False))

        self.lbl_find_count = QLabel("0 ocorrências")
        self.lbl_find_count.setStyleSheet("font-size: 11px; font-weight: 500; min-width: 90px;")

        self.btn_close_find = QPushButton("✕")
        self.btn_close_find.setObjectName("btn_close_find")
        self.btn_close_find.setFixedSize(24, 24)
        self.btn_close_find.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close_find.setToolTip("Fechar busca (Esc)")
        self.btn_close_find.clicked.connect(lambda: self.find_replace_card.setVisible(False))

        find_row1.addWidget(lbl_find)
        find_row1.addWidget(self.txt_find, stretch=1)
        find_row1.addWidget(self.btn_find_prev)
        find_row1.addWidget(self.btn_find_next)
        find_row1.addWidget(self.lbl_find_count)
        find_row1.addWidget(self.btn_close_find)

        # Row 2: Replace input + Replace / Replace All + Options
        find_row2 = QHBoxLayout()
        find_row2.setSpacing(6)

        lbl_replace = QLabel("Substituir:")
        lbl_replace.setStyleSheet("font-weight: 600; font-size: 12px;")
        self.lbl_replace = lbl_replace

        self.txt_replace = QLineEdit()
        self.txt_replace.setPlaceholderText("Substituir por...")
        self.txt_replace.returnPressed.connect(self._replace_current_match)

        self.btn_replace = QPushButton("Substituir")
        self.btn_replace.setObjectName("btn_find_nav")
        self.btn_replace.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_replace.clicked.connect(self._replace_current_match)

        self.btn_replace_all = QPushButton("Substituir Tudo")
        self.btn_replace_all.setObjectName("btn_find_nav")
        self.btn_replace_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_replace_all.clicked.connect(self._replace_all_matches)

        self.chk_case_sensitive = QCheckBox("Maiúsculas/Minúsculas")
        self.chk_case_sensitive.stateChanged.connect(self._on_find_text_changed)

        self.chk_whole_words = QCheckBox("Palavra Inteira")
        self.chk_whole_words.stateChanged.connect(self._on_find_text_changed)

        find_row2.addWidget(lbl_replace)
        find_row2.addWidget(self.txt_replace, stretch=1)
        find_row2.addWidget(self.btn_replace)
        find_row2.addWidget(self.btn_replace_all)
        find_row2.addWidget(self.chk_case_sensitive)
        find_row2.addWidget(self.chk_whole_words)

        find_layout.addLayout(find_row1)
        find_layout.addLayout(find_row2)

        # ------------------- QUICK TAGS TOOLBAR -------------------
        tags_bar = QWidget()
        tags_bar_layout = QHBoxLayout(tags_bar)
        tags_bar_layout.setContentsMargins(0, 0, 0, 0)
        tags_bar_layout.setSpacing(6)

        lbl_tags = QLabel("Tags Rápidas:")
        lbl_tags.setStyleSheet("font-size: 12px; font-weight: 600;")
        self.lbl_tags = lbl_tags
        tags_bar_layout.addWidget(lbl_tags)

        tags_list = [
            ("(hes)", "(hes) - Hesitação vocal"),
            ("(inint)", "(inint) - Trecho inaudível"),
            ("(ruído)", "(ruído) - Ruído ambiente"),
            ("(risos)", "(risos) - Risos"),
            ("(est)", "(est) - Estalo/Pigarrada"),
            ("[?]", "[?] - Baixa confiança"),
            ('(" ")', '(" ") - Termo incerto'),
            ("[fala]-", "[fala]- - Autocorreção"),
        ]

        for tag_text, tooltip in tags_list:
            btn_tag = QPushButton(tag_text)
            btn_tag.setObjectName("btn_tag_chip")
            btn_tag.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_tag.setToolTip(tooltip)
            btn_tag.clicked.connect(lambda checked, t=tag_text: self._insert_tag(t))
            tags_bar_layout.addWidget(btn_tag)

        tags_bar_layout.addStretch()

        # Undo / Redo buttons
        self.btn_undo = QPushButton("Desfazer")
        self.btn_undo.setObjectName("btn_mini_tool")
        self.btn_undo.setToolTip("Desfazer (Ctrl+Z)")
        self.btn_undo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_undo.clicked.connect(lambda: self.txt_reader.undo())

        self.btn_redo = QPushButton("Refazer")
        self.btn_redo.setObjectName("btn_mini_tool")
        self.btn_redo.setToolTip("Refazer (Ctrl+Y)")
        self.btn_redo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_redo.clicked.connect(lambda: self.txt_reader.redo())

        tags_bar_layout.addWidget(self.btn_undo)
        tags_bar_layout.addWidget(self.btn_redo)

        # ------------------- FILEPATH BAR -------------------
        filepath_bar = QWidget()
        self.filepath_bar = filepath_bar
        filepath_bar_layout = QHBoxLayout(filepath_bar)
        filepath_bar_layout.setContentsMargins(0, 0, 0, 0)
        filepath_bar_layout.setSpacing(6)

        self.lbl_save_path = QLabel("Salvar em:")
        self.lbl_save_path.setStyleSheet("font-size: 12px; font-weight: 600;")

        self.txt_filepath_display = QLineEdit()
        self.txt_filepath_display.setReadOnly(True)
        self.txt_filepath_display.setPlaceholderText("Nenhum arquivo aberto...")

        self.btn_save_as = QPushButton("Salvar Como...")
        self.btn_save_as.setObjectName("btn_editor_action")
        self.btn_save_as.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save_as.setToolTip("Escolher um novo local para salvar o arquivo")
        self.btn_save_as.clicked.connect(self._save_as_transcript)
        self.btn_save_as.setEnabled(False)

        filepath_bar_layout.addWidget(self.lbl_save_path)
        filepath_bar_layout.addWidget(self.txt_filepath_display, stretch=1)
        filepath_bar_layout.addWidget(self.btn_save_as)

        # ------------------- MAIN TEXT EDITOR -------------------
        self.txt_reader = TranscriptEditor(theme=self.current_theme, font_size=self.current_font_size)
        self.txt_reader.setPlaceholderText("Selecione um arquivo .txt à esquerda para visualizar e editar sua transcrição...")
        self.txt_reader.textChanged.connect(self._on_editor_text_changed)
        self.txt_reader.cursorPositionChanged.connect(self._update_text_stats)

        # ------------------- STATUS & STATS FOOTER -------------------
        stats_bar = QWidget()
        stats_layout = QHBoxLayout(stats_bar)
        stats_layout.setContentsMargins(4, 2, 4, 2)
        stats_layout.setSpacing(16)

        self.lbl_save_status = QLabel("Pronto")
        self.lbl_save_status.setStyleSheet("font-size: 11px; font-weight: 500;")

        self.lbl_stats = QLabel("Linhas: 0  |  Palavras: 0  |  Caracteres: 0  |  Lin 1, Col 1")
        self.lbl_stats.setStyleSheet("font-size: 11px; font-style: italic;")

        stats_layout.addWidget(self.lbl_save_status)
        stats_layout.addStretch()
        stats_layout.addWidget(self.lbl_stats)

        # Assemble right panel
        right_layout.addWidget(top_bar)
        right_layout.addWidget(self.find_replace_card)
        right_layout.addWidget(tags_bar)
        right_layout.addWidget(filepath_bar)
        right_layout.addWidget(self.txt_reader, stretch=1)
        right_layout.addWidget(stats_bar)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([280, 720])

        self.tab_widget.addTab(tab_reader, "Leitor")

        self._setup_editor_shortcuts()
        self._refresh_reader_files()

    def _setup_editor_shortcuts(self):
        """Configure keyboard shortcuts for the editor."""
        self._shortcut_save = QShortcut(QKeySequence("Ctrl+S"), self.tab_reader)
        self._shortcut_save.activated.connect(self._save_current_transcript)

        # Explicit Undo / Redo shortcuts (Ctrl+Z, Ctrl+Y, Ctrl+Shift+Z)
        self._shortcut_undo = QShortcut(QKeySequence.StandardKey.Undo, self.tab_reader)
        self._shortcut_undo.activated.connect(self.txt_reader.undo)

        self._shortcut_redo = QShortcut(QKeySequence.StandardKey.Redo, self.tab_reader)
        self._shortcut_redo.activated.connect(self.txt_reader.redo)

        self._shortcut_redo_alt = QShortcut(QKeySequence("Ctrl+Shift+Z"), self.tab_reader)
        self._shortcut_redo_alt.activated.connect(self.txt_reader.redo)

        self._shortcut_find = QShortcut(QKeySequence("Ctrl+F"), self.tab_reader)
        self._shortcut_find.activated.connect(self._open_find_bar)

        self._shortcut_replace = QShortcut(QKeySequence("Ctrl+H"), self.tab_reader)
        self._shortcut_replace.activated.connect(self._open_replace_bar)

        self._shortcut_escape = QShortcut(QKeySequence("Esc"), self.find_replace_card)
        self._shortcut_escape.activated.connect(lambda: self.find_replace_card.setVisible(False))

    def _toggle_find_replace_bar(self):
        is_vis = self.find_replace_card.isVisible()
        self.find_replace_card.setVisible(not is_vis)
        if not is_vis:
            self.txt_find.setFocus()
            self.txt_find.selectAll()
            self._on_find_text_changed()

    def _open_find_bar(self):
        self.find_replace_card.setVisible(True)
        self.txt_find.setFocus()
        self.txt_find.selectAll()
        self._on_find_text_changed()

    def _open_replace_bar(self):
        self.find_replace_card.setVisible(True)
        self.txt_replace.setFocus()
        self.txt_replace.selectAll()
        self._on_find_text_changed()

    def _insert_tag(self, tag: str):
        """Insert a transcription annotation tag at the current cursor position as a single undoable step."""
        cursor = self.txt_reader.textCursor()
        cursor.beginEditBlock()
        cursor.insertText(tag)
        cursor.endEditBlock()
        self.txt_reader.setTextCursor(cursor)
        self.txt_reader.setFocus()

    def _on_editor_text_changed(self):
        if self._ignore_text_changes:
            return
        if not self._is_editor_modified and self._current_open_filepath:
            self._is_editor_modified = True
            filename = os.path.basename(self._current_open_filepath)
            self.lbl_reader_filename.setText(f"* {filename}")
            self.lbl_save_status.setText("Alterações não salvas")
        self._update_text_stats()

    def _update_text_stats(self):
        """Update live document counters and cursor position."""
        text = self.txt_reader.toPlainText()
        lines = len(text.splitlines()) if text else 0
        words = len(text.split()) if text else 0
        chars = len(text)
        cursor = self.txt_reader.textCursor()
        line_num = cursor.blockNumber() + 1
        col_num = cursor.columnNumber() + 1
        self.lbl_stats.setText(f"Linhas: {lines:,}  |  Palavras: {words:,}  |  Caracteres: {chars:,}  |  Lin {line_num}, Col {col_num}".replace(",", "."))

    def _on_find_text_changed(self):
        """Update match count whenever search text or flags change."""
        query = self.txt_find.text() if hasattr(self, "txt_find") else ""
        if not query:
            self.lbl_find_count.setText("0 ocorrências")
            return

        doc = self.txt_reader.document()
        flags = QTextDocument.FindFlag(0)
        if hasattr(self, "chk_case_sensitive") and self.chk_case_sensitive.isChecked():
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        if hasattr(self, "chk_whole_words") and self.chk_whole_words.isChecked():
            flags |= QTextDocument.FindFlag.FindWholeWords

        count = 0
        cursor = QTextCursor(doc)
        while True:
            cursor = doc.find(query, cursor, flags)
            if cursor.isNull():
                break
            count += 1

        self.lbl_find_count.setText(f"{count} ocorrência(s)" if count > 0 else "Não encontrado")

    def _find_next_match(self, reverse: bool = False) -> bool:
        """Find the next or previous occurrence of the search query."""
        query = self.txt_find.text() if hasattr(self, "txt_find") else ""
        if not query:
            return False

        flags = QTextDocument.FindFlag(0)
        if reverse:
            flags |= QTextDocument.FindFlag.FindBackward
        if hasattr(self, "chk_case_sensitive") and self.chk_case_sensitive.isChecked():
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        if hasattr(self, "chk_whole_words") and self.chk_whole_words.isChecked():
            flags |= QTextDocument.FindFlag.FindWholeWords

        found = self.txt_reader.find(query, flags)
        if not found:
            # Wrap around
            cursor = self.txt_reader.textCursor()
            if reverse:
                cursor.movePosition(QTextCursor.MoveOperation.End)
            else:
                cursor.movePosition(QTextCursor.MoveOperation.Start)
            self.txt_reader.setTextCursor(cursor)
            found = self.txt_reader.find(query, flags)

        self._on_find_text_changed()
        return found

    def _replace_current_match(self):
        """Replace the current selection if matching, then find next."""
        query = self.txt_find.text() if hasattr(self, "txt_find") else ""
        replacement = self.txt_replace.text() if hasattr(self, "txt_replace") else ""
        if not query:
            return

        cursor = self.txt_reader.textCursor()
        selected_text = cursor.selectedText()

        is_match = False
        if hasattr(self, "chk_case_sensitive") and self.chk_case_sensitive.isChecked():
            is_match = (selected_text == query)
        else:
            is_match = (selected_text.lower() == query.lower())

        if is_match:
            cursor.beginEditBlock()
            cursor.insertText(replacement)
            cursor.endEditBlock()
            self._find_next_match(reverse=False)
        else:
            self._find_next_match(reverse=False)

    def _replace_all_matches(self):
        """Replace all occurrences in the document in a single undo block."""
        query = self.txt_find.text() if hasattr(self, "txt_find") else ""
        replacement = self.txt_replace.text() if hasattr(self, "txt_replace") else ""
        if not query:
            return

        doc = self.txt_reader.document()
        flags = QTextDocument.FindFlag(0)
        if hasattr(self, "chk_case_sensitive") and self.chk_case_sensitive.isChecked():
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        if hasattr(self, "chk_whole_words") and self.chk_whole_words.isChecked():
            flags |= QTextDocument.FindFlag.FindWholeWords

        cursor = QTextCursor(doc)
        cursor.beginEditBlock()
        replaced = 0
        while True:
            cursor = doc.find(query, cursor, flags)
            if cursor.isNull():
                break
            cursor.insertText(replacement)
            replaced += 1
        cursor.endEditBlock()

        self._on_find_text_changed()
        self.lbl_save_status.setText(f"{replaced} substituição(ões) realizada(s)")

    def _save_current_transcript(self):
        """Save the editor content directly to the currently open file."""
        if not self._current_open_filepath:
            return

        try:
            content = self.txt_reader.toPlainText()
            with open(self._current_open_filepath, "w", encoding="utf-8") as f:
                f.write(content)

            self._is_editor_modified = False
            filename = os.path.basename(self._current_open_filepath)
            self.lbl_reader_filename.setText(filename)
            self.lbl_save_status.setText(f"Salvo com sucesso ({time.strftime('%H:%M:%S')})")
        except Exception as e:
            QMessageBox.critical(self, "Erro ao Salvar", f"Não foi possível salvar as alterações:\n{e}")

    def _save_as_transcript(self):
        """Open a Save As dialog to choose a new path for the current transcript."""
        if not self._current_open_filepath:
            return

        current_dir = os.path.dirname(self._current_open_filepath)
        current_name = os.path.basename(self._current_open_filepath)

        new_path, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar Como...",
            os.path.join(current_dir, current_name),
            "Arquivos de Texto (*.txt);;Todos os Arquivos (*)",
        )

        if not new_path:
            return

        try:
            content = self.txt_reader.toPlainText()
            with open(new_path, "w", encoding="utf-8") as f:
                f.write(content)

            self._current_open_filepath = new_path
            self._is_editor_modified = False
            new_name = os.path.basename(new_path)
            self.lbl_reader_filename.setText(new_name)
            self.txt_filepath_display.setText(new_path)
            self.lbl_save_status.setText(f"Salvo em novo local ({time.strftime('%H:%M:%S')})")
            self._refresh_reader_files()
        except Exception as e:
            QMessageBox.critical(self, "Erro ao Salvar", f"Não foi possível salvar no local escolhido:\n{e}")

    def _save_revised_transcript(self):
        """Save a new copy of the current transcript with '_revisada.txt' suffix."""
        if not self._current_open_filepath:
            return

        base_dir = os.path.dirname(self._current_open_filepath)
        filename = os.path.basename(self._current_open_filepath)
        name, ext = os.path.splitext(filename)

        if name.endswith("_revisada"):
            revised_name = f"{name}.txt"
        elif name.endswith("_raw"):
            revised_name = f"{name[:-4]}_revisada.txt"
        else:
            revised_name = f"{name}_revisada.txt"

        new_filepath = os.path.join(base_dir, revised_name)

        try:
            content = self.txt_reader.toPlainText()
            with open(new_filepath, "w", encoding="utf-8") as f:
                f.write(content)

            self._current_open_filepath = new_filepath
            self._is_editor_modified = False
            self.lbl_reader_filename.setText(revised_name)
            self.lbl_save_status.setText(f"Cópia revisada salva: {revised_name}")

            self._refresh_reader_files()

            for i in range(self.list_transcripts.count()):
                item = self.list_transcripts.item(i)
                if item.text() == revised_name:
                    self.list_transcripts.setCurrentItem(item)
                    break
        except Exception as e:
            QMessageBox.critical(self, "Erro ao Salvar", f"Não foi possível salvar o arquivo revisado:\n{e}")

    def _refresh_reader_files(self):
        """Populate the reader list with all .txt transcript files."""
        if not hasattr(self, "list_transcripts"):
            return

        current_file = None
        if self.list_transcripts.currentItem():
            current_file = self.list_transcripts.currentItem().text()

        self.list_transcripts.clear()

        dirs_to_check = [self.output_dir]
        alt_output = os.path.join(self.base_path, 'outputs da transcricao')
        if os.path.exists(alt_output) and alt_output not in dirs_to_check:
            dirs_to_check.append(alt_output)

        found_files = []
        for d in dirs_to_check:
            if os.path.exists(d):
                try:
                    for fname in sorted(os.listdir(d)):
                        if fname.lower().endswith(".txt"):
                            full_p = os.path.join(d, fname)
                            if (fname, full_p) not in found_files:
                                found_files.append((fname, full_p))
                except Exception as e:
                    print(f"Aviso ao listar {d}: {e}")

        for fname, full_p in found_files:
            item = QListWidgetItem(fname)
            item.setData(Qt.ItemDataRole.UserRole, full_p)
            self.list_transcripts.addItem(item)
            if current_file and fname == current_file:
                self.list_transcripts.setCurrentItem(item)

    def _on_transcript_selected(self, current, previous):
        """Handle file selection and prompt if previous file has unsaved changes."""
        if self._is_editor_modified and self._current_open_filepath:
            old_name = os.path.basename(self._current_open_filepath)
            reply = QMessageBox.question(
                self,
                "Alterações Não Salvas",
                f"O arquivo '{old_name}' possui alterações não salvas.\nDeseja salvar antes de abrir outro arquivo?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
            )
            if reply == QMessageBox.StandardButton.Save:
                self._save_current_transcript()
            elif reply == QMessageBox.StandardButton.Cancel:
                if previous:
                    self._ignore_text_changes = True
                    self.list_transcripts.setCurrentItem(previous)
                    self._ignore_text_changes = False
                return

        if not current:
            self._ignore_text_changes = True
            self.txt_reader.clear()
            self.txt_reader.clear_highlights()
            self._ignore_text_changes = False
            self.lbl_reader_filename.setText("Nenhum arquivo aberto")
            self._current_open_filepath = None
            self._is_editor_modified = False
            if hasattr(self, "btn_save_transcript"):
                self.btn_save_transcript.setEnabled(False)
            if hasattr(self, "btn_save_revised"):
                self.btn_save_revised.setEnabled(False)
            if hasattr(self, "btn_change_speaker"):
                self.btn_change_speaker.setEnabled(False)
            self._update_text_stats()
            return

        filepath = current.data(Qt.ItemDataRole.UserRole)
        if filepath and os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                self._ignore_text_changes = True
                self.txt_reader.setPlainText(content)
                self.txt_reader.clear_highlights()
                self._ignore_text_changes = False

                self._current_open_filepath = filepath
                self._is_editor_modified = False
                self.lbl_reader_filename.setText(os.path.basename(filepath))
                if hasattr(self, "txt_filepath_display"):
                    self.txt_filepath_display.setText(filepath)
                self.lbl_save_status.setText("Pronto")
                if hasattr(self, "btn_save_transcript"):
                    self.btn_save_transcript.setEnabled(True)
                if hasattr(self, "btn_save_revised"):
                    self.btn_save_revised.setEnabled(True)
                if hasattr(self, "btn_save_as"):
                    self.btn_save_as.setEnabled(True)
                if hasattr(self, "btn_change_speaker"):
                    meta = load_speaker_metadata(self.output_dir, os.path.basename(filepath))
                    self.btn_change_speaker.setEnabled(bool(meta and meta.get("speaker_info")))
                self._update_text_stats()
            except Exception as e:
                self.txt_reader.setPlainText(f"Erro ao ler arquivo: {e}")

    def _build_settings_tab(self):
        tab_settings = QWidget()
        self.tab_settings = tab_settings
        tab_layout = QVBoxLayout(tab_settings)
        tab_layout.setContentsMargins(10, 10, 10, 10)

        # Auto-save note at the top
        self.lbl_auto_save_note = QLabel("As configurações e chaves são salvas automaticamente.")
        self.lbl_auto_save_note.setStyleSheet(f"color: {self.current_theme['TXT_PRIMARY']}; font-size: 12px; font-style: normal; font-weight: normal;")
        tab_layout.addWidget(self.lbl_auto_save_note)

        # ── Inner tab widget for settings categories ────────────────────
        self.settings_tabs = QTabWidget()
        self.settings_tabs.setObjectName("settings_tabs")
        tab_layout.addWidget(self.settings_tabs)

        # ═══════════════════════════════════════════════════════════════
        #  TAB 1: APIs de Nuvem
        # ═══════════════════════════════════════════════════════════════
        tab_apis = QWidget()
        tab_apis_scroll = QScrollArea()
        tab_apis_scroll.setWidgetResizable(True)
        tab_apis_scroll.setFrameShape(QFrame.Shape.NoFrame)

        tab_apis_container = QWidget()
        apis_layout = QVBoxLayout(tab_apis_container)
        apis_layout.setContentsMargins(10, 14, 10, 10)
        apis_layout.setSpacing(20)

        # ── Deepgram card ────────────────────────────────────────────────
        self.card_deepgram = QFrame()
        self.card_deepgram.setObjectName("card_deepgram")
        deepgram_layout = QVBoxLayout(self.card_deepgram)
        deepgram_layout.setContentsMargins(18, 18, 18, 18)
        deepgram_layout.setSpacing(14)

        lbl_deepgram_title = QLabel("Transcrição em Nuvem — Deepgram [Padrão]")
        lbl_deepgram_title.setStyleSheet("font-size: 15px; font-weight: bold;")
        self.lbl_deepgram_title = lbl_deepgram_title

        lbl_deepgram_desc = QLabel(
            "Utiliza a API do Deepgram (Nova-3) para transcrição ultrarrápida em português brasileiro. "
            "Oferece diarização, pontuação inteligente e formatação automática com altíssima velocidade."
        )
        lbl_deepgram_desc.setWordWrap(True)
        lbl_deepgram_desc.setStyleSheet("font-size: 12px; line-height: 1.4;")
        self.lbl_deepgram_desc = lbl_deepgram_desc

        # Deepgram API Key field
        dg_key_label = QLabel("Deepgram API Key:")
        dg_key_label.setStyleSheet("font-weight: 600; font-size: 12px;")
        self.lbl_deepgram_key = dg_key_label

        dg_input_layout = QHBoxLayout()
        dg_input_layout.setSpacing(8)

        self.txt_deepgram_key = QLineEdit()
        self.txt_deepgram_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_deepgram_key.setPlaceholderText("Insira sua chave de API do Deepgram aqui...")
        self.txt_deepgram_key.textChanged.connect(self._save_config)

        self.btn_reveal_deepgram = QPushButton("Mostrar")
        self.btn_reveal_deepgram.setObjectName("btn_reveal")
        self.btn_reveal_deepgram.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reveal_deepgram.clicked.connect(lambda: self._toggle_echo_mode(self.txt_deepgram_key, self.btn_reveal_deepgram))

        dg_input_layout.addWidget(self.txt_deepgram_key, stretch=1)
        dg_input_layout.addWidget(self.btn_reveal_deepgram)

        # Deepgram Balance Monitor
        dg_balance_layout = QHBoxLayout()
        dg_balance_layout.setSpacing(10)

        self.btn_check_deepgram_balance = QPushButton("Verificar Saldo")
        self.btn_check_deepgram_balance.setObjectName("btn_editor_action")
        self.btn_check_deepgram_balance.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_check_deepgram_balance.setToolTip("Consultar saldo restante na conta Deepgram")
        self.btn_check_deepgram_balance.clicked.connect(self._check_deepgram_balance)

        self.lbl_deepgram_balance = QLabel("")
        self.lbl_deepgram_balance.setStyleSheet("font-size: 12px; font-weight: 600;")

        dg_balance_layout.addWidget(self.btn_check_deepgram_balance)
        dg_balance_layout.addWidget(self.lbl_deepgram_balance, stretch=1)

        deepgram_layout.addWidget(lbl_deepgram_title)
        deepgram_layout.addWidget(lbl_deepgram_desc)
        deepgram_layout.addWidget(dg_key_label)
        deepgram_layout.addLayout(dg_input_layout)
        deepgram_layout.addLayout(dg_balance_layout)

        # ── AssemblyAI card ──────────────────────────────────────────────
        self.card_cloud = QFrame()
        self.card_cloud.setObjectName("card_cloud")
        cloud_layout = QVBoxLayout(self.card_cloud)
        cloud_layout.setContentsMargins(18, 18, 18, 18)
        cloud_layout.setSpacing(14)

        lbl_cloud_title = QLabel("Transcrição em Nuvem — AssemblyAI")
        lbl_cloud_title.setStyleSheet("font-size: 15px; font-weight: bold;")
        self.lbl_cloud_title = lbl_cloud_title

        lbl_cloud_desc = QLabel(
            "Utiliza a API da AssemblyAI (Universal-3.5 Pro) para transcrição rápida, "
            "com diarização e detecção de múltiplos falantes."
        )
        lbl_cloud_desc.setWordWrap(True)
        lbl_cloud_desc.setStyleSheet("font-size: 12px; line-height: 1.4;")
        self.lbl_cloud_desc = lbl_cloud_desc

        # API Key field
        api_row_label = QLabel("AssemblyAI API Key:")
        api_row_label.setStyleSheet("font-weight: 600; font-size: 12px;")
        self.lbl_api_key = api_row_label

        api_input_layout = QHBoxLayout()
        api_input_layout.setSpacing(8)

        self.txt_api_key = QLineEdit()
        self.txt_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_api_key.setPlaceholderText("Insira sua chave de API do AssemblyAI aqui...")
        self.txt_api_key.textChanged.connect(self._save_config)

        self.btn_reveal_api = QPushButton("Mostrar")
        self.btn_reveal_api.setObjectName("btn_reveal")
        self.btn_reveal_api.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reveal_api.clicked.connect(lambda: self._toggle_echo_mode(self.txt_api_key, self.btn_reveal_api))

        api_input_layout.addWidget(self.txt_api_key, stretch=1)
        api_input_layout.addWidget(self.btn_reveal_api)

        # Academic Mode Option
        self.academic_box = QFrame()
        self.academic_box.setObjectName("academic_box")
        academic_layout = QVBoxLayout(self.academic_box)
        academic_layout.setContentsMargins(14, 12, 14, 12)
        academic_layout.setSpacing(8)

        academic_top_row = QHBoxLayout()
        academic_top_row.setSpacing(12)
        
        self.toggle_academic = ToggleSwitch(theme=self.current_theme)
        self.toggle_academic.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_academic.toggled.connect(self._on_academic_toggled)

        self.lbl_academic_title = QLabel("Modo Acadêmico Sociolinguístico (--academic)")
        self.lbl_academic_title.setStyleSheet("font-size: 13px; font-weight: bold;")
        
        academic_top_row.addWidget(self.toggle_academic)
        academic_top_row.addWidget(self.lbl_academic_title)
        academic_top_row.addStretch()

        self.lbl_academic_desc = QLabel(
            "Aplica formatação LLM automática no estilo VARSUL/FLP: converte hesitações em (hes), "
            "trechos inaudíveis em (inint), ruídos em (ruído), disfluências em [fala]- "
            "e padroniza os falantes como F. (Informante) e E. (Entrevistador). "
            "Funciona com Deepgram e AssemblyAI (requer chave AssemblyAI para o LLM Gateway)."
        )
        self.lbl_academic_desc.setWordWrap(True)
        self.lbl_academic_desc.setStyleSheet("font-size: 11px; line-height: 1.3;")

        academic_layout.addLayout(academic_top_row)
        academic_layout.addWidget(self.lbl_academic_desc)

        cloud_layout.addWidget(lbl_cloud_title)
        cloud_layout.addWidget(lbl_cloud_desc)
        cloud_layout.addWidget(api_row_label)
        cloud_layout.addLayout(api_input_layout)
        cloud_layout.addWidget(self.academic_box)

        apis_layout.addWidget(self.card_deepgram)
        apis_layout.addWidget(self.card_cloud)
        apis_layout.addStretch()

        tab_apis_scroll.setWidget(tab_apis_container)
        tab_apis_layout = QVBoxLayout(tab_apis)
        tab_apis_layout.setContentsMargins(0, 0, 0, 0)
        tab_apis_layout.addWidget(tab_apis_scroll)

        self.settings_tabs.addTab(tab_apis, "APIs de Nuvem")

        # ═══════════════════════════════════════════════════════════════
        #  TAB 2: Acessibilidade
        # ═══════════════════════════════════════════════════════════════
        tab_access = QWidget()
        tab_access_scroll = QScrollArea()
        tab_access_scroll.setWidgetResizable(True)
        tab_access_scroll.setFrameShape(QFrame.Shape.NoFrame)

        tab_access_container = QWidget()
        access_outer_layout = QVBoxLayout(tab_access_container)
        access_outer_layout.setContentsMargins(10, 14, 10, 10)
        access_outer_layout.setSpacing(20)

        # ── Theme toggle card ────────────────────────────────────────────
        self.card_theme = QFrame()
        self.card_theme.setObjectName("card_theme")
        theme_card_layout = QVBoxLayout(self.card_theme)
        theme_card_layout.setContentsMargins(18, 18, 18, 18)
        theme_card_layout.setSpacing(14)

        lbl_theme_title = QLabel("Tema da Interface")
        lbl_theme_title.setStyleSheet("font-size: 15px; font-weight: bold;")
        self.lbl_theme_title = lbl_theme_title

        lbl_theme_desc = QLabel(
            "Alterne entre o Modo Dia (claro) e o Modo Noite (escuro) para conforto visual."
        )
        lbl_theme_desc.setWordWrap(True)
        lbl_theme_desc.setStyleSheet("font-size: 12px; line-height: 1.4;")
        self.lbl_theme_desc = lbl_theme_desc

        theme_toggle_row = QHBoxLayout()
        theme_toggle_row.setSpacing(12)

        self.toggle_theme_switch = ToggleSwitch(theme=self.current_theme)
        self.toggle_theme_switch.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_theme_switch.setToolTip("Alternar entre Modo Dia e Modo Noite")
        # Set initial state: checked = dark mode
        is_dark = (self.current_theme_name == "dark")
        self.toggle_theme_switch.setChecked(is_dark, animate=False)
        self.toggle_theme_switch.toggled.connect(self._on_theme_switch_toggled)

        self.lbl_theme_toggle_label = QLabel("Modo Noite" if is_dark else "Modo Dia")
        self.lbl_theme_toggle_label.setStyleSheet("font-size: 13px; font-weight: bold;")

        theme_toggle_row.addWidget(self.toggle_theme_switch)
        theme_toggle_row.addWidget(self.lbl_theme_toggle_label)
        theme_toggle_row.addStretch()

        theme_card_layout.addWidget(lbl_theme_title)
        theme_card_layout.addWidget(lbl_theme_desc)
        theme_card_layout.addLayout(theme_toggle_row)

        # ── Font size card ───────────────────────────────────────────────
        self.card_accessibility = QFrame()
        self.card_accessibility.setObjectName("card_accessibility")
        access_layout = QVBoxLayout(self.card_accessibility)
        access_layout.setContentsMargins(18, 18, 18, 18)
        access_layout.setSpacing(14)

        lbl_access_title = QLabel("Tamanho da Fonte")
        lbl_access_title.setStyleSheet("font-size: 15px; font-weight: bold;")
        self.lbl_access_title = lbl_access_title

        lbl_access_desc = QLabel(
            "Aumente ou diminua o tamanho das letras de toda a interface, abas e editor de texto para facilitar a visualização."
        )
        lbl_access_desc.setWordWrap(True)
        lbl_access_desc.setStyleSheet("font-size: 12px; line-height: 1.4;")
        self.lbl_access_desc = lbl_access_desc

        font_control_layout = QHBoxLayout()
        font_control_layout.setSpacing(10)

        self.btn_font_decrease = QPushButton("A-")
        self.btn_font_decrease.setObjectName("btn_editor_action")
        self.btn_font_decrease.setFixedWidth(42)
        self.btn_font_decrease.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_font_decrease.setToolTip("Diminuir tamanho da fonte")
        self.btn_font_decrease.clicked.connect(self._decrease_font_size)

        self.slider_font_size = QSlider(Qt.Orientation.Horizontal)
        self.slider_font_size.setRange(11, 22)
        self.slider_font_size.setValue(self.current_font_size)
        self.slider_font_size.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider_font_size.setTickInterval(1)
        self.slider_font_size.setCursor(Qt.CursorShape.PointingHandCursor)
        self.slider_font_size.valueChanged.connect(self._on_font_slider_changed)

        self.btn_font_increase = QPushButton("A+")
        self.btn_font_increase.setObjectName("btn_editor_action")
        self.btn_font_increase.setFixedWidth(42)
        self.btn_font_increase.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_font_increase.setToolTip("Aumentar tamanho da fonte")
        self.btn_font_increase.clicked.connect(self._increase_font_size)

        self.lbl_font_size_val = QLabel(f"{self.current_font_size}px (100%)")
        self.lbl_font_size_val.setStyleSheet("font-weight: bold; min-width: 90px;")

        self.btn_font_reset = QPushButton("Padrão (13px)")
        self.btn_font_reset.setObjectName("btn_editor_action")
        self.btn_font_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_font_reset.clicked.connect(lambda: self._set_font_size(13))

        font_control_layout.addWidget(self.btn_font_decrease)
        font_control_layout.addWidget(self.slider_font_size, stretch=1)
        font_control_layout.addWidget(self.btn_font_increase)
        font_control_layout.addWidget(self.lbl_font_size_val)
        font_control_layout.addWidget(self.btn_font_reset)

        self.lbl_font_preview = QLabel("Exemplo de visualização: [00:12 - 00:25] F. Olá, tudo bem? Vamos iniciar a gravação.")
        self.lbl_font_preview.setStyleSheet(f"font-size: {self.current_font_size}px; font-style: italic; padding: 6px; border-radius: 4px;")

        access_layout.addWidget(lbl_access_title)
        access_layout.addWidget(lbl_access_desc)
        access_layout.addLayout(font_control_layout)
        access_layout.addWidget(self.lbl_font_preview)

        access_outer_layout.addWidget(self.card_theme)
        access_outer_layout.addWidget(self.card_accessibility)
        access_outer_layout.addStretch()

        tab_access_scroll.setWidget(tab_access_container)
        tab_access_layout = QVBoxLayout(tab_access)
        tab_access_layout.setContentsMargins(0, 0, 0, 0)
        tab_access_layout.addWidget(tab_access_scroll)

        self.settings_tabs.addTab(tab_access, "Acessibilidade")

        # ═══════════════════════════════════════════════════════════════
        #  TAB 3: Sobre
        # ═══════════════════════════════════════════════════════════════
        tab_about = QWidget()
        tab_about_layout = QVBoxLayout(tab_about)
        tab_about_layout.setContentsMargins(18, 24, 18, 18)
        tab_about_layout.setSpacing(16)

        self.card_about = QFrame()
        self.card_about.setObjectName("card_about")
        about_card_layout = QVBoxLayout(self.card_about)
        about_card_layout.setContentsMargins(18, 18, 18, 18)
        about_card_layout.setSpacing(12)

        lbl_about_title = QLabel("Coelho Transcriber — Lite Edition")
        lbl_about_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.lbl_about_title = lbl_about_title

        lbl_about_desc = QLabel(
            "Ferramenta de transcrição sociolinguística em nuvem, desenvolvida para apoiar "
            "pesquisas acadêmicas com transcrições de áudio em português brasileiro."
        )
        lbl_about_desc.setWordWrap(True)
        lbl_about_desc.setStyleSheet("font-size: 12px; line-height: 1.5;")
        self.lbl_about_desc = lbl_about_desc

        credit_color = self.current_theme['ACCENT_PRIMARY'] if self.current_theme_name == "day" else "#ff5555"

        self.lbl_capes_note = QLabel(
            "O presente trabalho foi realizado com apoio da Coordenação de Aperfeiçoamento "
            "de Pessoal de Nível Superior - Brasil (CAPES)."
        )
        self.lbl_capes_note.setStyleSheet(f"color: {credit_color}; font-size: 12px; font-style: italic;")
        self.lbl_capes_note.setWordWrap(True)

        self.lbl_dev_note = QLabel(
            "Desenvolvido por Saulo R. com auxílio de LLMs. Em caso de dúvidas ou erros, contatar: "
            "<a href='mailto:saulorrp@gmail.com' style='color: #FFD700; text-decoration: underline;'>saulorrp@gmail.com</a>"
        )
        self.lbl_dev_note.setStyleSheet(f"color: {credit_color}; font-size: 12px; font-style: italic;")
        self.lbl_dev_note.setWordWrap(True)
        self.lbl_dev_note.setOpenExternalLinks(True)

        about_card_layout.addWidget(lbl_about_title)
        about_card_layout.addWidget(lbl_about_desc)
        about_card_layout.addWidget(self.lbl_capes_note)
        about_card_layout.addWidget(self.lbl_dev_note)

        tab_about_layout.addWidget(self.card_about)
        tab_about_layout.addStretch()

        self.settings_tabs.addTab(tab_about, "Sobre")

        self.tab_widget.addTab(tab_settings, "Configurações")


    # ==================== CONFIG PERSISTENCE ====================
    # Mode index mapping: 0 = cloud_deepgram, 1 = cloud_assemblyai
    _MODE_INDEX_MAP = {
        "cloud_deepgram": 0,
        "cloud_assemblyai": 1,
    }
    _INDEX_MODE_MAP = {v: k for k, v in _MODE_INDEX_MAP.items()}

    def _get_current_mode_str(self) -> str:
        """Return the current transcription mode as a string key."""
        idx = self.combo_mode.currentIndex() if hasattr(self, "combo_mode") else 0
        return self._INDEX_MODE_MAP.get(idx, "cloud_deepgram")

    def _load_config(self):
        """Load persistent settings from config.json"""
        if not os.path.exists(self.config_path):
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if "api_key" in data and isinstance(data["api_key"], str):
                self.txt_api_key.setText(data["api_key"])
            if "deepgram_api_key" in data and isinstance(data["deepgram_api_key"], str):
                self.txt_deepgram_key.setText(data["deepgram_api_key"])
            if "academic_mode" in data and isinstance(data["academic_mode"], bool):
                self.toggle_academic.setChecked(data["academic_mode"], animate=False)
                self._update_academic_badge(data["academic_mode"])
            if "theme" in data and data["theme"] in THEMES:
                self.current_theme_name = data["theme"]
            else:
                self.current_theme_name = "day"

            if "font_size" in data and isinstance(data["font_size"], int):
                self.current_font_size = max(11, min(22, data["font_size"]))
                if hasattr(self, "slider_font_size"):
                    self.slider_font_size.blockSignals(True)
                    self.slider_font_size.setValue(self.current_font_size)
                    self.slider_font_size.blockSignals(False)
                self._update_font_size_label()
            
            # Load transcription mode (cloud-only, default: Deepgram)
            mode_str = data.get("transcription_mode", "cloud_deepgram")
            if mode_str not in self._MODE_INDEX_MAP:
                mode_str = "cloud_deepgram"

            mode_idx = self._MODE_INDEX_MAP.get(mode_str, 0)
            if hasattr(self, "combo_mode"):
                self.combo_mode.blockSignals(True)
                self.combo_mode.setCurrentIndex(mode_idx)
                self.combo_mode.blockSignals(False)
            self._update_academic_badge(
                self.toggle_academic.isChecked() if hasattr(self, "toggle_academic") else False
            )
        except Exception as e:
            print(f"Aviso ao carregar config.json: {e}")

    def _save_config(self):
        """Save settings automatically to config.json"""
        data = {
            "api_key": self.txt_api_key.text().strip() if hasattr(self, "txt_api_key") else "",
            "deepgram_api_key": self.txt_deepgram_key.text().strip() if hasattr(self, "txt_deepgram_key") else "",
            "academic_mode": self.toggle_academic.isChecked() if hasattr(self, "toggle_academic") else False,
            "theme": self.current_theme_name,
            "transcription_mode": self._get_current_mode_str(),
            "font_size": self.current_font_size,
        }

        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Aviso ao salvar config.json: {e}")

    def _toggle_echo_mode(self, line_edit: QLineEdit, button: QPushButton):
        if line_edit.echoMode() == QLineEdit.EchoMode.Password:
            line_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            button.setText("Ocultar")
        else:
            line_edit.setEchoMode(QLineEdit.EchoMode.Password)
            button.setText("Mostrar")

    # ==================== FONT SIZE ACCESSIBILITY ====================
    def _on_font_slider_changed(self, value: int):
        self._set_font_size(value)

    def _decrease_font_size(self):
        new_val = max(11, self.current_font_size - 1)
        self._set_font_size(new_val)

    def _increase_font_size(self):
        new_val = min(22, self.current_font_size + 1)
        self._set_font_size(new_val)

    def _set_font_size(self, size: int):
        self.current_font_size = size
        if hasattr(self, "slider_font_size") and self.slider_font_size.value() != size:
            self.slider_font_size.blockSignals(True)
            self.slider_font_size.setValue(size)
            self.slider_font_size.blockSignals(False)
        self._update_font_size_label()
        self.apply_theme(self.current_theme_name)
        self._save_config()

    def _update_font_size_label(self):
        pct = int((self.current_font_size / 13.0) * 100)
        if hasattr(self, "lbl_font_size_val"):
            self.lbl_font_size_val.setText(f"{self.current_font_size}px ({pct}%)")
        if hasattr(self, "lbl_font_preview"):
            self.lbl_font_preview.setStyleSheet(f"font-size: {self.current_font_size}px; font-style: italic; padding: 6px; border-radius: 4px;")

    # ==================== THEME & ACCESSIBILITY SWITCHING ====================
    def apply_theme(self, theme_name: str):
        self.current_theme_name = theme_name
        self.current_theme = THEMES[theme_name]
        theme = self.current_theme
        fs = self.current_font_size
        fs_sm = max(10, fs - 2)
        fs_base = fs
        fs_md = fs + 1
        fs_lg = fs + 2
        fs_xl = fs + 4

        # Update theme-specific icons and window icon
        self._load_theme_icons(theme_name)

        # Set application-wide font
        app = QApplication.instance()
        if app:
            app.setFont(QFont("Segoe UI", fs_base))
        
        self.setStyleSheet(get_stylesheet(theme, fs_base))
        
        # Tabs and scroll background cleanup with targeted selectors
        if hasattr(self, "tab_settings"):
            self.tab_settings.setStyleSheet(f"QWidget#tab_settings {{ background-color: {theme['BG_BASE']}; }}")
        if hasattr(self, "scroll_settings"):
            self.scroll_settings.setStyleSheet(f"background-color: {theme['BG_BASE']}; border: none;")
            self.scroll_settings.viewport().setStyleSheet(f"background-color: {theme['BG_BASE']};")
        if hasattr(self, "container_settings"):
            self.container_settings.setStyleSheet(f"QWidget#container_settings {{ background-color: {theme['BG_BASE']}; }}")
        if hasattr(self, "tab_transcription"):
            self.tab_transcription.setStyleSheet(f"QWidget#tab_transcription {{ background-color: {theme['BG_BASE']}; }}")
        if hasattr(self, "tab_reader"):
            self.tab_reader.setStyleSheet(f"QWidget#tab_reader {{ background-color: {theme['BG_BASE']}; }}")

        if hasattr(self, "lbl_app_title"):
            self.lbl_app_title.setStyleSheet(f"color: {theme['TXT_PRIMARY']}; font-size: {fs_xl}px; font-weight: bold;")
        if hasattr(self, "lbl_audios"):
            self.lbl_audios.setStyleSheet(f"color: {theme['TXT_PRIMARY']}; font-size: {fs_md}px; font-weight: bold; margin-bottom: 5px;")
        if hasattr(self, "btn_add_audio"):
            self.btn_add_audio.setStyleSheet(
                f"background-color: {theme['BG_PANEL']}; border: 1px solid {theme['BORDER_MID']}; border-radius: 6px; padding: 7px 14px; color: {theme['TXT_PRIMARY']}; font-weight: 500; font-size: {fs_base}px;"
            )
        if hasattr(self, "btn_transcribe"):
            self.btn_transcribe.setStyleSheet(
                f"QPushButton#btn_transcribe {{ background-color: {theme['ACCENT_PRIMARY']}; color: {theme['BTN_TEXT']}; font-weight: bold; font-size: {fs_md}px; padding: 11px; border: none; border-radius: 6px; }} "
                f"QPushButton#btn_transcribe:hover {{ background-color: {theme['ACCENT_HOVER']}; }} "
                f"QPushButton#btn_transcribe:disabled {{ background-color: {theme['BORDER_MID']}; color: {theme['TXT_SECONDARY']}; }}"
            )
        if hasattr(self, "mode_status_card"):
            self.mode_status_card.setStyleSheet(f"QFrame#mode_status_card {{ background-color: {theme['BG_PANEL']}; border-radius: 8px; border: 1px solid {theme['BORDER_MID']}; }}")
        if hasattr(self, "lbl_active_mode_title"):
            self.lbl_active_mode_title.setStyleSheet(f"color: {theme['TXT_PRIMARY']}; font-size: {fs_base}px; font-weight: bold;")
        if hasattr(self, "combo_mode"):
            self.combo_mode.setStyleSheet(
                f"QComboBox#combo_mode {{ "
                f"background-color: {theme['BG_CARD']}; "
                f"border: 1.5px solid {theme['BORDER_MID']}; "
                f"border-radius: 6px; "
                f"padding: 6px 12px; "
                f"color: {theme['TXT_PRIMARY']}; "
                f"font-size: {fs_base}px; "
                f"font-weight: 600; "
                f"min-height: 20px; "
                f"}} "
                f"QComboBox#combo_mode:hover {{ "
                f"border-color: {theme['ACCENT_PRIMARY']}; "
                f"}} "
                f"QComboBox#combo_mode:focus {{ "
                f"border-color: {theme['ACCENT_PRIMARY']}; "
                f"}} "
                f"QComboBox#combo_mode::drop-down {{ "
                f"border: none; "
                f"padding-right: 8px; "
                f"background: transparent; "
                f"}} "
                f"QComboBox#combo_mode QAbstractItemView {{ "
                f"background-color: {theme['BG_CARD']}; "
                f"border: 1.5px solid {theme['BORDER_MID']}; "
                f"border-radius: 6px; "
                f"color: {theme['TXT_PRIMARY']}; "
                f"selection-background-color: {theme['ACCENT_PRIMARY']}; "
                f"selection-color: {theme['BTN_TEXT']}; "
                f"padding: 4px; "
                f"outline: none; "
                f"}} "
                f"QComboBox#combo_mode QAbstractItemView::item {{ "
                f"min-height: 26px; "
                f"padding: 6px 10px; "
                f"color: {theme['TXT_PRIMARY']}; "
                f"border-radius: 4px; "
                f"}} "
                f"QComboBox#combo_mode QAbstractItemView::item:selected {{ "
                f"background-color: {theme['ACCENT_PRIMARY']}; "
                f"color: {theme['BTN_TEXT']}; "
                f"}} "
                f"QComboBox#combo_mode QAbstractItemView::item:hover {{ "
                f"background-color: {theme['BG_HOVER']}; "
                f"color: {theme['TXT_PRIMARY']}; "
                f"}} "
            )

        if hasattr(self, "status_banner"):
            self.status_banner.setStyleSheet(
                f"QFrame#status_banner {{ background-color: {theme['BG_PANEL']}; border: 1.5px solid {theme['ACCENT_PRIMARY']}; border-radius: 8px; }}"
            )
        if hasattr(self, "lbl_status_text"):
            self.lbl_status_text.setStyleSheet(f"color: {theme['TXT_PRIMARY']}; font-size: {fs_base}px; font-weight: 600;")
        if hasattr(self, "lbl_reader_files"):
            self.lbl_reader_files.setStyleSheet(f"color: {theme['TXT_PRIMARY']}; font-size: {fs_md}px; font-weight: bold;")
        if hasattr(self, "lbl_reader_filename"):
            self.lbl_reader_filename.setStyleSheet(f"color: {theme['TXT_PRIMARY']}; font-size: {fs_md}px; font-weight: bold;")
        if hasattr(self, "btn_refresh_reader"):
            self.btn_refresh_reader.setStyleSheet(
                f"background-color: {theme['BG_PANEL']}; border: 1px solid {theme['BORDER_MID']}; border-radius: 6px; padding: 7px 12px; color: {theme['TXT_PRIMARY']}; font-weight: 500; font-size: {fs_base}px;"
            )
        if hasattr(self, "find_replace_card"):
            self.find_replace_card.setStyleSheet(
                f"QFrame#find_replace_card {{ background-color: {theme['BG_PANEL']}; border-radius: 8px; border: 1px solid {theme['BORDER_MID']}; }}"
            )
        if hasattr(self, "lbl_find"):
            self.lbl_find.setStyleSheet(f"color: {theme['TXT_PRIMARY']}; font-weight: 600; font-size: {fs_sm}px;")
        if hasattr(self, "lbl_replace"):
            self.lbl_replace.setStyleSheet(f"color: {theme['TXT_PRIMARY']}; font-weight: 600; font-size: {fs_sm}px;")
        if hasattr(self, "lbl_find_count"):
            self.lbl_find_count.setStyleSheet(f"color: {theme['TXT_SECONDARY']}; font-size: {fs_sm}px; font-weight: 500; min-width: 90px;")
        if hasattr(self, "lbl_tags"):
            self.lbl_tags.setStyleSheet(f"color: {theme['TXT_PRIMARY']}; font-size: {fs_sm}px; font-weight: 600;")
        if hasattr(self, "lbl_save_path"):
            self.lbl_save_path.setStyleSheet(f"color: {theme['TXT_PRIMARY']}; font-size: {fs_sm}px; font-weight: 600;")
        if hasattr(self, "txt_filepath_display"):
            self.txt_filepath_display.setStyleSheet(
                f"background-color: {theme['BG_PANEL']}; color: {theme['TXT_SECONDARY']}; "
                f"border: 1px solid {theme['BORDER_MID']}; border-radius: 4px; "
                f"padding: 3px 6px; font-size: {fs_sm}px;"
            )
        if hasattr(self, "lbl_save_status"):
            self.lbl_save_status.setStyleSheet(f"color: {theme['ACCENT_PRIMARY']}; font-size: {fs_sm}px; font-weight: 500;")
        if hasattr(self, "lbl_stats"):
            self.lbl_stats.setStyleSheet(f"color: {theme['TXT_SECONDARY']}; font-size: {fs_sm}px; font-style: italic;")
        if hasattr(self, "btn_save_transcript"):
            self.btn_save_transcript.setStyleSheet(
                f"QPushButton#btn_save_primary {{ background-color: {theme['ACCENT_PRIMARY']}; color: {theme['BTN_TEXT']}; font-weight: bold; font-size: {fs_base}px; padding: 6px 14px; border: none; border-radius: 6px; }} "
                f"QPushButton#btn_save_primary:hover {{ background-color: {theme['ACCENT_HOVER']}; }} "
                f"QPushButton#btn_save_primary:disabled {{ background-color: {theme['BORDER_MID']}; color: {theme['TXT_SECONDARY']}; }}"
            )
        if hasattr(self, "btn_save_revised"):
            self.btn_save_revised.setStyleSheet(
                f"QPushButton#btn_save_revised {{ background-color: {theme['BG_CARD']}; border: 1.5px solid {theme['ACCENT_PRIMARY']}; color: {theme['TXT_PRIMARY']}; font-weight: bold; font-size: {fs_base}px; padding: 6px 14px; border-radius: 6px; }} "
                f"QPushButton#btn_save_revised:hover {{ background-color: {theme['BG_HOVER']}; }} "
                f"QPushButton#btn_save_revised:disabled {{ background-color: {theme['BG_PANEL']}; border-color: {theme['BORDER_MID']}; color: {theme['TXT_SECONDARY']}; }}"
            )
        if hasattr(self, "card_cloud"):
            self.card_cloud.setStyleSheet(f"QFrame#card_cloud {{ background-color: {theme['BG_PANEL']}; border-radius: 8px; border: 1px solid {theme['BORDER_MID']}; }}")
        if hasattr(self, "card_deepgram"):
            self.card_deepgram.setStyleSheet(f"QFrame#card_deepgram {{ background-color: {theme['BG_PANEL']}; border-radius: 8px; border: 1px solid {theme['BORDER_MID']}; }}")
        if hasattr(self, "card_accessibility"):
            self.card_accessibility.setStyleSheet(f"QFrame#card_accessibility {{ background-color: {theme['BG_PANEL']}; border-radius: 8px; border: 1px solid {theme['BORDER_MID']}; }}")
        if hasattr(self, "card_theme"):
            self.card_theme.setStyleSheet(f"QFrame#card_theme {{ background-color: {theme['BG_PANEL']}; border-radius: 8px; border: 1px solid {theme['BORDER_MID']}; }}")
        if hasattr(self, "card_about"):
            self.card_about.setStyleSheet(f"QFrame#card_about {{ background-color: {theme['BG_PANEL']}; border-radius: 8px; border: 1px solid {theme['BORDER_MID']}; }}")
        if hasattr(self, "academic_box"):
            self.academic_box.setStyleSheet(f"QFrame#academic_box {{ background-color: {theme['BG_CARD']}; border-radius: 6px; border: 1px solid {theme['BORDER_MID']}; }}")
        if hasattr(self, "lbl_academic_badge"):
            self.lbl_academic_badge.setStyleSheet(
                f"background-color: {theme['ACCENT_PRIMARY']}; color: #ffffff; font-size: {fs_sm}px; "
                "font-weight: bold; padding: 2px 8px; border-radius: 4px;"
            )
        if hasattr(self, "lbl_cloud_title"):
            self.lbl_cloud_title.setStyleSheet(f"color: {theme['TXT_PRIMARY']}; font-size: {fs_md}px; font-weight: bold;")
        if hasattr(self, "lbl_cloud_desc"):
            self.lbl_cloud_desc.setStyleSheet(f"color: {theme['TXT_SECONDARY']}; font-size: {fs_sm}px; line-height: 1.4;")
        if hasattr(self, "lbl_access_title"):
            self.lbl_access_title.setStyleSheet(f"color: {theme['TXT_PRIMARY']}; font-size: {fs_md}px; font-weight: bold;")
        if hasattr(self, "lbl_access_desc"):
            self.lbl_access_desc.setStyleSheet(f"color: {theme['TXT_SECONDARY']}; font-size: {fs_sm}px; line-height: 1.4;")
        if hasattr(self, "lbl_font_size_val"):
            self.lbl_font_size_val.setStyleSheet(f"color: {theme['TXT_PRIMARY']}; font-size: {fs_base}px; font-weight: bold; min-width: 90px;")
        if hasattr(self, "lbl_academic_title"):
            self.lbl_academic_title.setStyleSheet(f"color: {theme['TXT_PRIMARY']}; font-size: {fs_base}px; font-weight: bold;")
        if hasattr(self, "lbl_academic_desc"):
            self.lbl_academic_desc.setStyleSheet(f"color: {theme['TXT_SECONDARY']}; font-size: {fs_sm}px; line-height: 1.3;")

        if hasattr(self, "lbl_api_key"):
            self.lbl_api_key.setStyleSheet(f"color: {theme['TXT_PRIMARY']}; font-weight: 600; font-size: {fs_sm}px;")
        if hasattr(self, "lbl_logs"):
            self.lbl_logs.setStyleSheet(f"color: {theme['TXT_PRIMARY']}; font-size: {fs_md}px; font-weight: bold; margin-top: 6px; margin-bottom: 4px;")
        credit_color = theme['ACCENT_PRIMARY'] if theme_name == "day" else "#FFD700"
        if hasattr(self, "lbl_auto_save_note"):
            self.lbl_auto_save_note.setStyleSheet(f"color: {theme['TXT_PRIMARY']}; font-size: {fs_sm}px; font-style: normal; font-weight: normal;")
        if hasattr(self, "lbl_capes_note"):
            self.lbl_capes_note.setStyleSheet(f"color: {credit_color}; font-size: {fs_sm}px; font-style: italic;")
        if hasattr(self, "lbl_dev_note"):
            self.lbl_dev_note.setStyleSheet(f"color: {credit_color}; font-size: {fs_sm}px; font-style: italic;")
        if hasattr(self, "btn_theme"):
            if theme_name == "day":
                self.btn_theme.setText("☾")
            else:
                self.btn_theme.setText("☼")
        if hasattr(self, "lbl_deepgram_title"):
            self.lbl_deepgram_title.setStyleSheet(f"color: {theme['TXT_PRIMARY']}; font-size: {fs_md}px; font-weight: bold;")
        if hasattr(self, "lbl_deepgram_desc"):
            self.lbl_deepgram_desc.setStyleSheet(f"color: {theme['TXT_SECONDARY']}; font-size: {fs_sm}px; line-height: 1.4;")
        if hasattr(self, "lbl_deepgram_key"):
            self.lbl_deepgram_key.setStyleSheet(f"color: {theme['TXT_PRIMARY']}; font-weight: 600; font-size: {fs_sm}px;")
        if hasattr(self, "toggle_academic"):
            self.toggle_academic.set_theme(theme)
        if hasattr(self, "toggle_theme_switch"):
            self.toggle_theme_switch.set_theme(theme)
            is_dark = (theme_name == "dark")
            self.toggle_theme_switch.blockSignals(True)
            self.toggle_theme_switch.setChecked(is_dark, animate=False)
            self.toggle_theme_switch.blockSignals(False)
        if hasattr(self, "lbl_theme_title"):
            self.lbl_theme_title.setStyleSheet(f"color: {theme['TXT_PRIMARY']}; font-size: {fs_md}px; font-weight: bold;")
        if hasattr(self, "lbl_theme_desc"):
            self.lbl_theme_desc.setStyleSheet(f"color: {theme['TXT_SECONDARY']}; font-size: {fs_sm}px; line-height: 1.4;")
        if hasattr(self, "lbl_theme_toggle_label"):
            self.lbl_theme_toggle_label.setText("Modo Noite" if theme_name == "dark" else "Modo Dia")
            self.lbl_theme_toggle_label.setStyleSheet(f"color: {theme['TXT_PRIMARY']}; font-size: {fs_base}px; font-weight: bold;")
        if hasattr(self, "lbl_about_title"):
            self.lbl_about_title.setStyleSheet(f"color: {theme['TXT_PRIMARY']}; font-size: {fs_lg}px; font-weight: bold;")
        if hasattr(self, "lbl_about_desc"):
            self.lbl_about_desc.setStyleSheet(f"color: {theme['TXT_SECONDARY']}; font-size: {fs_sm}px; line-height: 1.5;")

        if hasattr(self, "txt_reader") and isinstance(self.txt_reader, TranscriptEditor):
            self.txt_reader.set_theme(theme, fs_base)

        # Update queue items theme and size hints
        if hasattr(self, "list_audios"):
            for i in range(self.list_audios.count()):
                item = self.list_audios.item(i)
                w = self.list_audios.itemWidget(item)
                if isinstance(w, AudioQueueItemWidget):
                    w.set_theme(theme, fs_base)
                    item.setSizeHint(QSize(0, max(36, fs_base * 2 + 10)))

    def _toggle_theme(self):
        new_theme = "day" if self.current_theme_name == "dark" else "dark"
        self.apply_theme(new_theme)
        self._save_config()

    def _on_theme_switch_toggled(self, checked: bool):
        """Handle the ToggleSwitch in the Acessibilidade tab."""
        new_theme = "dark" if checked else "day"
        self.apply_theme(new_theme)
        self._save_config()

    # ==================== SLOTS ====================
    def _on_add_audio(self):
        # If previous queue was completely finished, reset before adding new batch
        if self._audio_paths and all(
            isinstance(self.list_audios.itemWidget(self.list_audios.item(i)), AudioQueueItemWidget) and
            self.list_audios.itemWidget(self.list_audios.item(i)).is_done()
            for i in range(self.list_audios.count())
        ):
            self._audio_paths.clear()
            self.list_audios.clear()

        filter_str = "Arquivos de Áudio (" + " ".join(f"*{ext}" for ext in AUDIO_EXTENSIONS) + ")"
        files, _ = QFileDialog.getOpenFileNames(
            self, "Selecionar áudios", "", filter_str,
        )
        if files:
            for f in files:
                if f not in self._audio_paths:
                    self._audio_paths.append(f)
                    item = QListWidgetItem(self.list_audios)
                    item_widget = AudioQueueItemWidget(
                        os.path.basename(f), f, self.current_theme, self.current_font_size
                    )
                    item_widget.removed.connect(self._on_remove_queued_audio)
                    item_widget.select_speaker_requested.connect(self._on_select_speaker_for_file)
                    item.setSizeHint(QSize(0, max(36, self.current_font_size * 2 + 10)))
                    self.list_audios.addItem(item)
                    self.list_audios.setItemWidget(item, item_widget)
            self.txt_logs.append(f"> {len(files)} arquivo(s) adicionado(s) à fila.")

    def _on_remove_queued_audio(self, filepath: str):
        """Remove a specific audio file from queue."""
        if filepath in self._audio_paths:
            self._audio_paths.remove(filepath)
        for i in range(self.list_audios.count()):
            item = self.list_audios.item(i)
            w = self.list_audios.itemWidget(item)
            if isinstance(w, AudioQueueItemWidget) and w.filepath == filepath:
                self.list_audios.takeItem(i)
                break
        self.txt_logs.append(f"> '{os.path.basename(filepath)}' removido da fila.")

    def _on_transcribe(self):
        # ── Guard: nothing queued ────────────────────────────────────────
        if not self._audio_paths:
            self.txt_logs.append("> Nenhum áudio na fila. Use '+ Adicionar Áudios' primeiro.")
            return

        # ── Guard: already running ───────────────────────────────────────
        if self.worker is not None and self.worker.isRunning():
            self.txt_logs.append("> Transcrição já em andamento – aguarde ou aborte.")
            return

        mode_str = self._get_current_mode_str()
        academic_mode = self.toggle_academic.isChecked() if hasattr(self, "toggle_academic") else False

        api_key = self.txt_api_key.text().strip()
        deepgram_api_key = self.txt_deepgram_key.text().strip() if hasattr(self, "txt_deepgram_key") else ""

        # Map mode_str to worker mode
        if mode_str == "cloud_deepgram":
            worker_mode = "deepgram"
        else:
            worker_mode = "cloud"

        # Feedback & validation
        if worker_mode == "cloud" and not api_key:
            self.txt_logs.append("> [Atenção] Nenhuma API Key da AssemblyAI configurada. Acesse a aba 'Configurações'.")
        if worker_mode == "deepgram" and not deepgram_api_key:
            self.txt_logs.append("> [Atenção] Nenhuma API Key do Deepgram configurada. Acesse a aba 'Configurações'.")

        mode_desc = self.combo_mode.currentText()
        if academic_mode:
            mode_desc += " + Modo Acadêmico"
        self.txt_logs.append(f"> Iniciando transcrição ({mode_desc})…")

        self.worker = TranscriptionWorker(
            file_paths=list(self._audio_paths),
            output_dir=self.output_dir,
            mode=worker_mode,
            api_key=api_key,
            academic_mode=academic_mode,
            deepgram_api_key=deepgram_api_key,
            parent=self,
        )

        # Connect worker signals to GUI slots
        self.worker.log_signal.connect(self._on_worker_log)
        self.worker.error_signal.connect(self._on_worker_error)
        self.worker.finished_signal.connect(self._on_worker_finished)
        self.worker.request_speaker_signal.connect(self._on_speaker_requested)
        self.worker.file_finished_signal.connect(self._on_file_finished)
        self.worker.request_continue_signal.connect(self._on_continue_requested)

        # Start jumping rabbit waiting animation & disable controls
        self._start_waiting_animation()
        self.btn_transcribe.setText("Transcrevendo...")
        self.btn_transcribe.setEnabled(False)
        self.btn_add_audio.setEnabled(False)
        if hasattr(self, "combo_mode"):
            self.combo_mode.setEnabled(False)

        for i in range(self.list_audios.count()):
            w = self.list_audios.itemWidget(self.list_audios.item(i))
            if isinstance(w, AudioQueueItemWidget):
                w.set_removable(False)

        self.worker.start()

    def _on_abort(self):
        if self.worker and self.worker.isRunning():
            self.worker.request_abort()
            if hasattr(self, "lbl_status_text"):
                self.lbl_status_text.setText("Abortando processo… Aguarde finalizar etapa")
            self.txt_logs.append("> Solicitação de aborto enviada – finalizando etapa atual…")

    # ── Worker signal handlers ───────────────────────────────────────────
    def _on_worker_log(self, message: str):
        self.txt_logs.append(message)

    def _on_worker_error(self, message: str):
        self.txt_logs.append(f"<span style='color:#ff5555;'>[Erro] {message}</span>")

    def _on_speaker_requested(self, speaker_info: list):
        """
        Triggered by the worker when speakers are detected.
        Shows the selection dialog with an automatic countdown timer (15s).
        If the user does not choose or closes the dialog, the suggested speaker
        is used provisorily so that the queue continues without stopping!
        """
        filename = speaker_info[0].get("filename", "") if speaker_info else ""
        self._pause_waiting_animation(f"Seleção de falante (F.) para '{filename}'…")

        chosen, is_confirmed, is_aborted = SpeakerSelectionDialog.select_speaker(
            speaker_info,
            parent=self,
            theme=self.current_theme,
            auto_timeout_sec=15,
            filename=filename,
        )

        if is_aborted:
            self.txt_logs.append("> Transcrição interrompida pelo usuário.")
            self._stop_waiting_animation()
            self.worker.request_abort()
            return

        if is_confirmed:
            self.txt_logs.append(f"> Falante principal (F.) confirmado: {chosen}")
        else:
            self.txt_logs.append(
                f"> Falante provisório definido como sugerido ({chosen}) para não travar a fila. Você poderá alterar depois."
            )

        self._resume_waiting_animation("Transcrevendo áudios… Aguarde um instante")
        self.worker.set_selected_speaker(chosen, is_confirmed=is_confirmed)

    def _on_file_finished(self, filename: str):
        """Mark the corresponding queue item as completed and set speaker status."""
        meta = load_speaker_metadata(self.output_dir, filename)
        is_confirmed = meta.get("is_confirmed", False) if meta else True
        f_speaker = meta.get("f_speaker_id", "") if meta else ""

        for i in range(self.list_audios.count()):
            item = self.list_audios.item(i)
            widget = self.list_audios.itemWidget(item)
            if isinstance(widget, AudioQueueItemWidget):
                if widget.filename == filename or os.path.basename(widget.filepath) == filename:
                    widget.set_done(speaker_label=f_speaker, is_confirmed=is_confirmed)
        self._refresh_reader_files()

    def _on_continue_requested(self, next_basename: str):
        """Proceed to the next file in the queue automatically without interrupting batch flow."""
        self.txt_logs.append(f"> Prosseguindo para o próximo áudio: '{next_basename}'…")
        self._resume_waiting_animation(f"Iniciando '{next_basename}'…")
        self.worker.set_continue_response(True)

    def _on_worker_finished(self):
        self.txt_logs.append("> Pipeline finalizado.")

        # Stop waiting animation & restore controls
        self._stop_waiting_animation()
        self.btn_transcribe.setText("Transcrever Fila")
        self.btn_transcribe.setEnabled(True)
        self.btn_add_audio.setEnabled(True)
        if hasattr(self, "combo_mode"):
            self.combo_mode.setEnabled(True)

        for i in range(self.list_audios.count()):
            w = self.list_audios.itemWidget(self.list_audios.item(i))
            if isinstance(w, AudioQueueItemWidget):
                w.set_removable(True)

        self._refresh_reader_files()
        self.worker = None

        # Check for any files where F was auto-assigned as suggested without user confirmation
        pending_files = []
        for i in range(self.list_audios.count()):
            item = self.list_audios.item(i)
            widget = self.list_audios.itemWidget(item)
            if isinstance(widget, AudioQueueItemWidget) and widget.is_done() and not widget.is_speaker_confirmed():
                pending_files.append(widget.filepath)

        if pending_files:
            self.txt_logs.append(
                f"> Concluído: {len(pending_files)} áudio(s) possuem falante principal (F.) com sugestão provisória."
            )
            reply = QMessageBox.question(
                self,
                "Revisão de Falantes (F.)",
                f"A fila de áudios foi totalmente transcrita com sucesso!\n\n"
                f"Existem {len(pending_files)} áudio(s) com o falante principal (F.) atribuído provisoriamente como sugestão.\n\n"
                f"Deseja selecionar/revisar o falante principal de cada um agora?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                for fp in pending_files:
                    self._on_select_speaker_for_file(fp)

    def _on_select_speaker_for_file(self, filepath: str):
        """Open speaker selection dialog for an already completed transcription."""
        filename = os.path.basename(filepath)
        meta = load_speaker_metadata(self.output_dir, filename)
        if not meta or not meta.get("speaker_info"):
            QMessageBox.information(
                self,
                "Informações de Falantes",
                f"Não foram encontrados dados de falantes detectados para '{filename}'.\n"
                f"Isso pode ocorrer caso o arquivo tenha sido gerado por uma versão antiga.",
            )
            return

        speaker_info = meta.get("speaker_info", [])
        current_f = meta.get("f_speaker_id")

        chosen, is_confirmed, is_aborted = SpeakerSelectionDialog.select_speaker(
            speaker_info,
            parent=self,
            theme=self.current_theme,
            auto_timeout_sec=0,  # No countdown in post-processing mode
            current_f=current_f,
            filename=filename,
        )

        if is_aborted:
            return

        if chosen:
            success, msg = update_transcript_speakers(meta, chosen, self.output_dir)
            if success:
                self.txt_logs.append(f"> '{filename}': {msg}")
                # Update queue item widget if present in the audio list
                for i in range(self.list_audios.count()):
                    item = self.list_audios.item(i)
                    widget = self.list_audios.itemWidget(item)
                    if isinstance(widget, AudioQueueItemWidget) and (
                        widget.filepath == filepath or widget.filename == filename
                    ):
                        widget.set_done(speaker_label=chosen, is_confirmed=True)

                # If currently open in reader editor, reload content
                if self._current_open_filepath:
                    curr_name = os.path.basename(self._current_open_filepath)
                    if get_meta_base_name(curr_name) == get_meta_base_name(filename):
                        self._load_transcript_file(self._current_open_filepath)

                self._refresh_reader_files()
            else:
                QMessageBox.warning(self, "Aviso", msg)

    def _on_reader_change_speaker_clicked(self):
        """Handle 'Definir Falante (F.)' button click in the reader tab."""
        if not self._current_open_filepath:
            return
        self._on_select_speaker_for_file(self._current_open_filepath)

    def _load_transcript_file(self, filepath: str):
        """Helper to reload a transcript file into the editor."""
        if not filepath or not os.path.exists(filepath):
            return
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            self._ignore_text_changes = True
            self.txt_reader.setPlainText(content)
            self.txt_reader.clear_highlights()
            self._ignore_text_changes = False
            self.lbl_reader_filename.setText(os.path.basename(filepath))
            self.lbl_save_status.setText("Atualizado após seleção de falante")
            self._update_text_stats()
        except Exception as e:
            self.txt_logs.append(f"> Erro ao recarregar transcrição no leitor: {e}")

    # ── Mode selection & updates ─────────────────────────────────────────
    def _on_mode_changed(self, index: int):
        """Handle mode QComboBox change — log the new mode and save config."""
        mode_labels = {
            0: "Transcrição em Nuvem (Deepgram - Nova-3)",
            1: "Transcrição em Nuvem (AssemblyAI - Universal-3.5)",
        }
        label = mode_labels.get(index, "Desconhecido")
        self.txt_logs.append(f"> [Modo] Alternado para {label}.")
        # Academic badge always visible for cloud modes when academic is on
        self._update_academic_badge(
            self.toggle_academic.isChecked() if hasattr(self, "toggle_academic") else False
        )
        self._save_config()

    def _update_academic_badge(self, is_academic: bool):
        """Show the academic badge when academic mode is enabled (all modes are cloud)."""
        self.lbl_academic_badge.setVisible(is_academic)

    def _on_academic_toggled(self, checked: bool):
        self._update_academic_badge(checked)
        state_str = "ativado" if checked else "desativado"
        self.txt_logs.append(f"> [Config] Modo Acadêmico (--academic) {state_str}.")
        self._save_config()

    # ── Deepgram Balance Check ───────────────────────────────────────────
    def _check_deepgram_balance(self):
        """Fetch Deepgram account balance asynchronously via QThread."""
        api_key = self.txt_deepgram_key.text().strip() if hasattr(self, "txt_deepgram_key") else ""
        if not api_key:
            self.lbl_deepgram_balance.setText("⚠ Insira uma API Key primeiro.")
            self.lbl_deepgram_balance.setStyleSheet("color: #ff5555; font-size: 12px; font-weight: 600;")
            return

        self.lbl_deepgram_balance.setText("Consultando saldo…")
        self.lbl_deepgram_balance.setStyleSheet(f"color: {self.current_theme['TXT_SECONDARY']}; font-size: 12px; font-weight: 600;")
        self.btn_check_deepgram_balance.setEnabled(False)

        self._balance_worker = DeepgramBalanceWorker(api_key, parent=self)
        self._balance_worker.result_signal.connect(self._on_deepgram_balance_result)
        self._balance_worker.start()

    def _on_deepgram_balance_result(self, message: str, is_error: bool):
        """Receive balance result from worker and update UI."""
        color = "#ff5555" if is_error else self.current_theme['ACCENT_PRIMARY']
        prefix = "⚠ " if is_error else "✓ "
        self.lbl_deepgram_balance.setText(f"{prefix}{message}")
        self.lbl_deepgram_balance.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: 600;")
        self.btn_check_deepgram_balance.setEnabled(True)

    def _check_for_updates(self):
        """Initiate background update check."""
        self._update_worker = UpdateCheckWorker(self)
        self._update_worker.update_available.connect(self._on_update_available)
        self._update_worker.start()

    def _on_update_available(self, new_version: str, notes: str, url: str):
        """Open update dialog when a newer version is discovered."""
        dialog = UpdateAvailableDialog(
            new_version=new_version,
            release_notes=notes,
            download_url=url,
            parent=self,
            theme=self.current_theme
        )
        dialog.exec()


if __name__ == "__main__":
    # Ensure Windows taskbar groups and shows the application icon
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"coelho.transcriber.app.{APP_VERSION}")
    except Exception:
        pass

    app = QApplication(sys.argv)
    
    # Configure application icon globally
    base_dir = os.path.dirname(os.path.abspath(__file__))
    icon_candidate = os.path.join(base_dir, 'components', 'icons', 'icon.ico')
    if not os.path.exists(icon_candidate):
        icon_candidate = os.path.join(base_dir, 'components', 'icon.ico')
    if os.path.exists(icon_candidate):
        app.setWindowIcon(QIcon(icon_candidate))

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
