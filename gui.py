import sys
import os
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QMessageBox, QDialog,
    QFileDialog, QDateEdit, QStyledItemDelegate, QComboBox, QLabel,
    QProgressBar
)
from PySide6.QtCore import Qt, QDate, QTimer, QThread, Signal
from PySide6 import QtGui
from PySide6.QtGui import QIcon
import webbrowser
import re
from imdb_fetcher import fetch_movie_info
from movie_manager import MovieManager
from models import Movie
from database import init_db, save_movies, load_movies, export_to_json, import_from_json
from version import __version__
from updater import get_latest_release, is_newer, download_update, apply_update
from cloud_sync import is_configured, download_db, upload_db

DATE_FORMAT = "dd/MM/yyyy"
_NULL_DATE = QDate(2000, 1, 1)  # sentinel for "no date selected"

APP_STYLE = """
/* ── Global ────────────────────────────────── */
QWidget {
    font-family: 'Segoe UI', 'Arial';
    font-size: 13px;
    color: #1E293B;
    background-color: #F1F5F9;
}

/* ── Text inputs ───────────────────────────── */
QLineEdit {
    background: #FFFFFF;
    border: 1.5px solid #CBD5E1;
    border-radius: 6px;
    padding: 7px 12px;
    selection-background-color: #BFDBFE;
}
QLineEdit:focus { border-color: #3B82F6; }

/* ── Date / Combo ──────────────────────────── */
QDateEdit, QComboBox {
    background: #FFFFFF;
    border: 1.5px solid #CBD5E1;
    border-radius: 6px;
    padding: 7px 10px;
}
QDateEdit:focus, QComboBox:focus { border-color: #3B82F6; }
QDateEdit::drop-down, QComboBox::drop-down {
    border: none;
    width: 22px;
}
QComboBox QAbstractItemView {
    background: #FFFFFF;
    border: 1px solid #CBD5E1;
    outline: none;
    selection-background-color: #EFF6FF;
    selection-color: #2563EB;
}

/* ── Table ─────────────────────────────────── */
QTableWidget {
    background: #FFFFFF;
    alternate-background-color: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 10px;
    gridline-color: #E2E8F0;
}
QTableWidget::item { padding: 5px 8px; }
QTableWidget::item:selected {
    background: #EFF6FF;
    color: #1D4ED8;
}

/* ── Column headers ────────────────────────── */
QHeaderView::section {
    background: #1E293B;
    color: #F1F5F9;
    padding: 10px 8px;
    font-weight: bold;
    font-size: 12px;
    border: none;
    border-right: 1px solid #334155;
}
QHeaderView::section:last  { border-right: none; }
QHeaderView::section:hover { background: #334155; }

/* Row-number header */
QHeaderView::section:vertical {
    background: #F8FAFC;
    color: #94A3B8;
    font-weight: normal;
    font-size: 11px;
    border: none;
    border-bottom: 1px solid #E2E8F0;
    padding: 0 6px;
}

/* ── Buttons ───────────────────────────────── */
QPushButton {
    background: #3B82F6;
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 600;
    font-size: 12px;
    min-width: 68px;
}
QPushButton:hover   { background: #2563EB; }
QPushButton:pressed { background: #1D4ED8; }

QPushButton#danger          { background: #EF4444; }
QPushButton#danger:hover    { background: #DC2626; }
QPushButton#danger:pressed  { background: #B91C1C; }

QPushButton#secondary         { background: #64748B; }
QPushButton#secondary:hover   { background: #475569; }
QPushButton#secondary:pressed { background: #334155; }

/* ── Scroll bars ───────────────────────────── */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #CBD5E1;
    border-radius: 4px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover { background: #94A3B8; }
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical { height: 0; }

QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: #CBD5E1;
    border-radius: 4px;
    min-width: 24px;
}
QScrollBar::handle:horizontal:hover { background: #94A3B8; }
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal { width: 0; }
"""

# Urgency palette for the Days Left cell
_URGENCY = [
    # (max_days, bg_hex,   fg_hex)
    (0,  "#FEE2E2", "#991B1B"),   # last day / overdue  → red
    (7,  "#FEF3C7", "#92400E"),   # ≤ 7 days            → amber
    (14, "#DCFCE7", "#166534"),   # ≤ 14 days           → green
]

PLATFORMS = [
    "",
    "Netflix",
    "Amazon Prime Video",
    "Disney+",
    "Max",
    "Apple TV+",
    "Hulu",
    "Paramount+",
    "Peacock",
    "Tubi",
    "YouTube Premium",
    "Other",
]

class SmartDateEdit(QDateEdit):
    """Opens the calendar at the current month when no date is selected."""
    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if self.date() == _NULL_DATE:
            QTimer.singleShot(0, self._go_to_today)

    def _go_to_today(self):
        cal = self.calendarWidget()
        if cal and cal.isVisible():
            today = QDate.currentDate()
            cal.setCurrentPage(today.year(), today.month())


COL_TITLE = 0
COL_LENGTH = 1
COL_DATE = 2
COL_DAYS_LEFT = 3
COL_PLATFORM = 4
COL_LINK = 5


def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)


class SortableItem(QTableWidgetItem):
    """QTableWidgetItem that compares by Qt.UserRole (numeric) when available."""
    def __lt__(self, other):
        my_key = self.data(Qt.UserRole)
        other_key = other.data(Qt.UserRole) if isinstance(other, QTableWidgetItem) else None
        if my_key is not None and other_key is not None:
            try:
                return my_key < other_key
            except TypeError:
                pass
        # Never call super().__lt__() — PySide6 routes it back into this
        # Python override, causing infinite recursion. Use text directly.
        other_text = other.text() if isinstance(other, QTableWidgetItem) else str(other)
        return self.text() < other_text


class DateDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QDateEdit(parent)
        editor.setCalendarPopup(True)
        editor.setDisplayFormat(DATE_FORMAT)
        return editor

    def setEditorData(self, editor, index):
        date = QDate.fromString(index.data(Qt.DisplayRole) or "", DATE_FORMAT)
        editor.setDate(date if date.isValid() else QDate.currentDate())

    def setModelData(self, editor, model, index):
        model.setData(index, editor.date().toString(DATE_FORMAT), Qt.EditRole)


class UpdateCheckWorker(QThread):
    update_available = Signal(str, str)  # (latest_tag, download_url)

    def run(self):
        tag, url = get_latest_release()
        if tag and url and is_newer(__version__, tag):
            self.update_available.emit(tag, url)


class DownloadWorker(QThread):
    progress = Signal(int)
    finished = Signal(str)   # path to downloaded file
    error = Signal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            path = download_update(self.url, self.progress.emit)
            self.finished.emit(path)
        except Exception as e:
            self.error.emit(str(e))


class UpdateDialog(QDialog):
    def __init__(self, latest_tag, download_url, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Update Available")
        self.setFixedWidth(420)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self._download_url = download_url
        self._worker = None

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        info = QLabel(
            f"<b>Version {latest_tag} is available.</b><br>"
            f"You are on version {__version__}.<br><br>"
            "Download and install now?"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.hide()
        layout.addWidget(self._progress)

        self._status = QLabel("")
        self._status.hide()
        layout.addWidget(self._status)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._update_btn = QPushButton("Update Now")
        self._skip_btn = QPushButton("Skip")
        self._skip_btn.setObjectName("secondary")
        btn_row.addWidget(self._update_btn)
        btn_row.addWidget(self._skip_btn)
        layout.addLayout(btn_row)

        self.setLayout(layout)
        self._update_btn.clicked.connect(self._start_download)
        self._skip_btn.clicked.connect(self.reject)

    def _start_download(self):
        self._update_btn.setEnabled(False)
        self._skip_btn.setEnabled(False)
        self._progress.show()
        self._status.setText("Downloading…")
        self._status.show()

        self._worker = DownloadWorker(self._download_url)
        self._worker.progress.connect(self._progress.setValue)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_finished(self, new_exe_path):
        self._status.setText("Installing update…")
        apply_update(new_exe_path)
        QApplication.quit()

    def _on_error(self, msg):
        self._status.setText(f"Error: {msg}")
        self._update_btn.setEnabled(True)
        self._skip_btn.setEnabled(True)


class MovieWatchlistApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Movie Watchlist")
        icon_path = get_resource_path(os.path.join("assets", "movie-icon-15159.png"))
        self.setWindowIcon(QIcon(icon_path))
        self.manager = MovieManager()
        self.init_ui()
        self.table.cellClicked.connect(self.open_link)
        self.table.itemChanged.connect(self.on_item_changed)

    def _make_item(self, text, editable=False):
        item = SortableItem(text)
        item.setTextAlignment(Qt.AlignCenter)
        if not editable:
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        return item

    # --- urgency color for Days Left cell ---
    def _urgency_color(self, sort_key):
        """Return (QBrush bg, QBrush fg) for a days-left sort key, or (None, None)."""
        if sort_key == float('inf'):
            return None, None
        for max_days, bg_hex, fg_hex in _URGENCY:
            if sort_key <= max_days:
                return QtGui.QBrush(QtGui.QColor(bg_hex)), QtGui.QBrush(QtGui.QColor(fg_hex))
        return None, None

    # --- sort key helpers ---
    def _length_sort_key(self, length_str):
        m = re.search(r'\((\d+)\s*min\)', length_str)
        return int(m.group(1)) if m else float('inf')

    def _date_sort_key(self, date_str):
        date = QDate.fromString(date_str, DATE_FORMAT)
        return date.toJulianDay() if date.isValid() else float('inf')

    def _days_left_sort_key(self, date_str):
        date = QDate.fromString(date_str, DATE_FORMAT)
        return QDate.currentDate().daysTo(date) if date.isValid() else float('inf')

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        input_layout = QHBoxLayout()
        input_layout.setSpacing(10)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("IMDB URL")

        self.date_input = SmartDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat(DATE_FORMAT)
        self.date_input.setMinimumDate(_NULL_DATE)
        self.date_input.setSpecialValueText("Date to watch")
        self.date_input.setDate(_NULL_DATE)
        self.date_input.setFixedWidth(140)

        self.platform_input = QComboBox()
        self.platform_input.addItems(PLATFORMS)
        self.platform_input.setFixedWidth(160)

        input_layout.addWidget(self.url_input)
        input_layout.addWidget(self.date_input)
        input_layout.addWidget(self.platform_input)
        layout.addLayout(input_layout)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Title", "Length", "Date", "Days Left", "Platform", "Link"])
        for col in range(self.table.columnCount()):
            self.table.horizontalHeaderItem(col).setTextAlignment(Qt.AlignCenter)
        self.table.setItemDelegateForColumn(COL_DATE, DateDelegate(self))
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(COL_TITLE, 220)
        self.table.setColumnWidth(COL_LENGTH, 120)
        self.table.setColumnWidth(COL_DATE, 95)
        self.table.setColumnWidth(COL_DAYS_LEFT, 90)
        self.table.setColumnWidth(COL_PLATFORM, 140)
        layout.addWidget(self.table)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        self.add_button    = QPushButton("Add")
        self.remove_button = QPushButton("Remove")
        self.edit_button   = QPushButton("Edit")
        self.up_button     = QPushButton("↑")
        self.down_button   = QPushButton("↓")
        self.export_button = QPushButton("Export")
        self.import_button = QPushButton("Import")

        self.remove_button.setObjectName("danger")

        self.add_button.clicked.connect(self.add_movie)
        self.remove_button.clicked.connect(self.remove_movie)
        self.edit_button.clicked.connect(self.edit_movie)
        self.up_button.clicked.connect(self.move_up)
        self.down_button.clicked.connect(self.move_down)
        self.export_button.clicked.connect(self.export_movies)
        self.import_button.clicked.connect(self.import_movies)

        for btn in [self.add_button, self.remove_button, self.edit_button,
                    self.up_button, self.down_button, self.export_button, self.import_button]:
            button_layout.addWidget(btn)

        layout.addLayout(button_layout)
        self.setLayout(layout)

        for url, title, length, date, platform in load_movies():
            self.manager.add_movie(Movie(url, title, length, date, platform))
            self._insert_row(url, title, length, date, platform)
        self.table.sortByColumn(COL_DAYS_LEFT, Qt.AscendingOrder)

    def _days_left_text(self, date_str):
        date = QDate.fromString(date_str, DATE_FORMAT)
        if not date.isValid():
            return ""
        days = QDate.currentDate().daysTo(date)
        if days == 0:
            return "Last Day"
        if days > 0:
            return str(days)
        return f"{abs(days)}d ago"

    def _insert_row(self, url, title, length, date, platform=""):
        self.table.setSortingEnabled(False)
        self.table.blockSignals(True)
        row = self.table.rowCount()
        self.table.insertRow(row)

        self.table.setItem(row, COL_TITLE, self._make_item(title))

        length_item = self._make_item(length)
        length_item.setData(Qt.UserRole, self._length_sort_key(length))
        self.table.setItem(row, COL_LENGTH, length_item)

        date_item = self._make_item(date, editable=True)
        date_item.setData(Qt.UserRole, self._date_sort_key(date))
        self.table.setItem(row, COL_DATE, date_item)

        days_key = self._days_left_sort_key(date)
        days_item = self._make_item(self._days_left_text(date))
        days_item.setData(Qt.UserRole, days_key)
        bg, fg = self._urgency_color(days_key)
        if bg:
            days_item.setBackground(bg)
        if fg:
            days_item.setForeground(fg)
        self.table.setItem(row, COL_DAYS_LEFT, days_item)

        self.table.setItem(row, COL_PLATFORM, self._make_item(platform))

        link_item = self._make_item(url)
        link_item.setForeground(QtGui.QColor("blue"))
        self.table.setItem(row, COL_LINK, link_item)

        self.table.blockSignals(False)
        self.table.setSortingEnabled(True)

    def on_item_changed(self, item):
        if item.column() != COL_DATE:
            return
        self.table.setSortingEnabled(False)
        self.table.blockSignals(True)
        date_str = item.text()
        item.setData(Qt.UserRole, self._date_sort_key(date_str))
        days_item = self.table.item(item.row(), COL_DAYS_LEFT)
        if days_item:
            days_key = self._days_left_sort_key(date_str)
            days_item.setText(self._days_left_text(date_str))
            days_item.setData(Qt.UserRole, days_key)
            bg, fg = self._urgency_color(days_key)
            days_item.setBackground(bg if bg else QtGui.QBrush())
            days_item.setForeground(fg if fg else QtGui.QBrush())
        self.table.blockSignals(False)
        self.table.setSortingEnabled(True)

    def add_movie(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Warning", "Please enter an IMDB URL.")
            return
        if not re.match(r'https?://(www\.)?imdb\.com/title/tt\d+', url):
            QMessageBox.warning(self, "Warning", "Please enter a valid IMDB URL.\nExample: https://www.imdb.com/title/tt1234567/")
            return

        date = ""
        if self.date_input.date() != _NULL_DATE:
            date = self.date_input.date().toString(DATE_FORMAT)
        platform = self.platform_input.currentText()

        title, length = fetch_movie_info(url)
        if title and length:
            movie = Movie(url, title, length, date, platform)
            self.manager.add_movie(movie)
            self._insert_row(url, title, length, date, platform)
            self.url_input.clear()
            self.date_input.setDate(_NULL_DATE)
            self.platform_input.setCurrentIndex(0)
        else:
            QMessageBox.critical(self, "Error", "Failed to fetch movie data.")

    def remove_movie(self):
        selected = self.table.currentRow()
        if selected >= 0:
            self.manager.remove_movie(selected)
            self.table.removeRow(selected)

    def edit_movie(self):
        selected = self.table.currentRow()
        if selected < 0:
            return
        current_url = self.table.item(selected, COL_LINK).text()
        current_date = self.table.item(selected, COL_DATE).text()
        current_platform = self.table.item(selected, COL_PLATFORM).text()

        dialog = EditDialog(current_url, current_date, current_platform, self)
        if dialog.exec():
            new_url, new_date, new_platform = dialog.get_data()
            new_title, new_length = fetch_movie_info(new_url)
            if new_title and new_length:
                self.table.setSortingEnabled(False)
                self.table.blockSignals(True)
                self.table.setItem(selected, COL_TITLE, self._make_item(new_title))

                length_item = self._make_item(new_length)
                length_item.setData(Qt.UserRole, self._length_sort_key(new_length))
                self.table.setItem(selected, COL_LENGTH, length_item)

                date_item = self._make_item(new_date, editable=True)
                date_item.setData(Qt.UserRole, self._date_sort_key(new_date))
                self.table.setItem(selected, COL_DATE, date_item)

                new_days_key = self._days_left_sort_key(new_date)
                days_item = self._make_item(self._days_left_text(new_date))
                days_item.setData(Qt.UserRole, new_days_key)
                bg, fg = self._urgency_color(new_days_key)
                if bg:
                    days_item.setBackground(bg)
                if fg:
                    days_item.setForeground(fg)
                self.table.setItem(selected, COL_DAYS_LEFT, days_item)

                self.table.setItem(selected, COL_PLATFORM, self._make_item(new_platform))

                link_item = self._make_item(new_url)
                link_item.setForeground(QtGui.QColor("blue"))
                self.table.setItem(selected, COL_LINK, link_item)
                self.table.blockSignals(False)
                self.table.setSortingEnabled(True)
                self.manager.edit_movie(selected, Movie(new_url, new_title, new_length, new_date, new_platform))
            else:
                QMessageBox.warning(self, "Error", "Failed to fetch movie info.")

    def move_up(self):
        row = self.table.currentRow()
        if row > 0:
            self.manager.move_up(row)
            self.swap_rows(row, row - 1)
            self.table.selectRow(row - 1)

    def move_down(self):
        row = self.table.currentRow()
        if row < self.table.rowCount() - 1:
            self.manager.move_down(row)
            self.swap_rows(row, row + 1)
            self.table.selectRow(row + 1)

    def swap_rows(self, row1, row2):
        self.table.setSortingEnabled(False)
        self.table.blockSignals(True)
        for col in range(self.table.columnCount()):
            item1 = self.table.item(row1, col)
            item2 = self.table.item(row2, col)
            text1, text2 = item1.text(), item2.text()
            fg1, fg2 = item1.foreground(), item2.foreground()
            bg1, bg2 = item1.background(), item2.background()
            flags1, flags2 = item1.flags(), item2.flags()
            key1, key2 = item1.data(Qt.UserRole), item2.data(Qt.UserRole)

            new1 = SortableItem(text2)
            new1.setTextAlignment(Qt.AlignCenter)
            new1.setForeground(fg2)
            new1.setBackground(bg2)
            new1.setFlags(flags2)
            new1.setData(Qt.UserRole, key2)

            new2 = SortableItem(text1)
            new2.setTextAlignment(Qt.AlignCenter)
            new2.setForeground(fg1)
            new2.setBackground(bg1)
            new2.setFlags(flags1)
            new2.setData(Qt.UserRole, key1)

            self.table.setItem(row1, col, new1)
            self.table.setItem(row2, col, new2)
        self.table.blockSignals(False)
        self.table.setSortingEnabled(True)

    def open_link(self, row, column):
        if column == COL_LINK:
            item = self.table.item(row, column)
            if item and item.text():
                webbrowser.open(item.text())

    def export_movies(self):
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "Warning", "No movies to export.")
            return
        filepath, _ = QFileDialog.getSaveFileName(self, "Export Movies", "", "JSON Files (*.json)")
        if filepath:
            movies = []
            for row in range(self.table.rowCount()):
                title = self.table.item(row, COL_TITLE).text()
                length = self.table.item(row, COL_LENGTH).text()
                date = self.table.item(row, COL_DATE).text()
                platform = self.table.item(row, COL_PLATFORM).text()
                url = self.table.item(row, COL_LINK).text()
                movies.append(Movie(url, title, length, date, platform))
            try:
                export_to_json(movies, filepath)
                QMessageBox.information(self, "Success", "Movies exported successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export: {e}")

    def import_movies(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Import Movies", "", "JSON Files (*.json)")
        if filepath:
            try:
                imported = import_from_json(filepath)
                for url, title, length, date, platform in imported:
                    movie = Movie(url, title, length, date, platform)
                    self.manager.add_movie(movie)
                    self._insert_row(url, title, length, date, platform)
                QMessageBox.information(self, "Success", f"Imported {len(imported)} movies.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to import: {e}")

    def closeEvent(self, event):
        self.manager.movies.clear()
        for row in range(self.table.rowCount()):
            title = self.table.item(row, COL_TITLE).text()
            length = self.table.item(row, COL_LENGTH).text()
            date = self.table.item(row, COL_DATE).text()
            platform = self.table.item(row, COL_PLATFORM).text()
            url_item = self.table.item(row, COL_LINK)
            url = url_item.text() if url_item else ""
            self.manager.add_movie(Movie(url, title, length, date, platform))
        save_movies(self.manager.movies)

        # Push updated db to Google Drive (silent if not configured)
        try:
            if is_configured():
                upload_db("watchlist.db")
        except Exception as e:
            print(f"Cloud sync upload skipped: {e}")

        event.accept()


class EditDialog(QDialog):
    def __init__(self, current_url, current_date, current_platform="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Movie")
        self.resize(600, 180)
        self.url_input = QLineEdit(current_url)

        self.date_input = SmartDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat(DATE_FORMAT)
        self.date_input.setMinimumDate(_NULL_DATE)
        self.date_input.setSpecialValueText("No date")
        date = QDate.fromString(current_date, DATE_FORMAT)
        self.date_input.setDate(date if date.isValid() else _NULL_DATE)

        self.platform_input = QComboBox()
        self.platform_input.addItems(PLATFORMS)
        if current_platform in PLATFORMS:
            self.platform_input.setCurrentText(current_platform)

        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(self.url_input)

        date_platform_layout = QHBoxLayout()
        date_platform_layout.addWidget(self.date_input)
        date_platform_layout.addWidget(self.platform_input)
        layout.addLayout(date_platform_layout)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondary")
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        self.setLayout(layout)

        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)

    def get_data(self):
        date = ""
        if self.date_input.date() != _NULL_DATE:
            date = self.date_input.date().toString(DATE_FORMAT)
        return self.url_input.text(), date, self.platform_input.currentText()


def run_app():
    # Pull latest db from Google Drive before opening (silent if not configured)
    try:
        if is_configured():
            download_db("watchlist.db")
    except Exception as e:
        print(f"Cloud sync download skipped: {e}")

    init_db()
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLE)
    window = MovieWatchlistApp()
    window.resize(900, 700)
    window.show()

    # Background update check — fires 2 s after startup so it never blocks the UI
    _checker = UpdateCheckWorker()
    _checker.update_available.connect(
        lambda tag, url: UpdateDialog(tag, url, window).exec()
    )
    QTimer.singleShot(2000, _checker.start)

    sys.exit(app.exec())
