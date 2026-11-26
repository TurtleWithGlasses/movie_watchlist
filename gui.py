import sys
import os
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QMessageBox, QDialog,
    QFileDialog, QDateEdit, QStyledItemDelegate, QComboBox, QLabel,
    QProgressBar, QCalendarWidget, QStyleOptionViewItem
)
from PySide6.QtCore import Qt, QDate, QTimer, QThread, Signal, QSettings
from PySide6 import QtGui
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QStyle
import webbrowser
import re
from imdb_fetcher import fetch_movie_info
from models import Movie
from database import (init_db, save_movies, load_movies, export_to_json,
                      import_from_json, migrate_legacy_db)
from paths import DB_PATH
from version import __version__
from updater import (get_latest_release, is_newer, download_update,
                     apply_update, do_staged_update, cleanup_old_version)
from cloud_sync import is_configured, download_db, upload_db

DATE_FORMAT = "dd/MM/yyyy"
_NULL_DATE = QDate(2000, 1, 1)  # sentinel for "no date selected"
_HAS_FOCUS_MASK = 0x100  # QStyle.StateFlag.HasFocus — stable Qt constant, avoids strict-enum int() issues
_IMDB_URL_RE = re.compile(r'https?://(www\.)?imdb\.com/title/tt\d+')

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
QTableWidget { outline: none; }
QTableWidget::item { padding: 5px 8px; }
QTableWidget::item:selected {
    background: #EFF6FF;
    color: #1D4ED8;
}
/* Suppress native OS blue on hover and focus — no explicit rule → fallback to native */
QTableWidget::item:focus       { background: transparent; border: none; }
QTableWidget::item:hover       { background: transparent; }
/* More-specific combined states keep selected appearance */
QTableWidget::item:selected:focus { background: #EFF6FF; color: #1D4ED8; }
QTableWidget::item:selected:hover { background: #EFF6FF; color: #1D4ED8; }

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

    def show_calendar(self):
        """Open a calendar popup positioned below this widget."""
        popup = QDialog(self, Qt.Popup)
        cal = QCalendarWidget(popup)
        cal.setSelectedDate(
            self.date() if self.date() != _NULL_DATE else QDate.currentDate()
        )
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(cal)
        popup.setLayout(layout)

        def on_activated(date):
            self.setDate(date)
            popup.close()

        cal.activated.connect(on_activated)
        popup.move(self.mapToGlobal(self.rect().bottomLeft()))
        popup.show()


COL_TITLE = 0
COL_LENGTH = 1
COL_EPISODES = 2
COL_RATING = 3
COL_DATE = 4
COL_DAYS_LEFT = 5
COL_PLATFORM = 6
COL_LINK = 7
COL_FLAG = 8  # displayed as the first column (see init_ui)

FLAG_ON = "⚑"
FLAG_OFF = "⚐"
_FLAG_ON_COLOR = "#DC2626"
_FLAG_OFF_COLOR = "#CBD5E1"


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


class NoFocusDelegate(QStyledItemDelegate):
    """Removes the solid-blue current-cell overlay (State_HasFocus).

    Owns the full draw path: copy option → initStyleOption → strip HasFocus bit
    via raw integer mask → drawControl.  Never calls super().paint() because
    that re-invokes initStyleOption internally and would restore the flag."""
    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        # .value works on both QFlags and PySide6 strict-enum StateFlag objects
        opt.state = QStyle.State(opt.state.value & ~_HAS_FOCUS_MASK)
        widget = option.widget
        style = widget.style() if widget else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, widget)


class DateDelegate(NoFocusDelegate):
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


class FetchWorker(QThread):
    """Runs fetch_movie_info off the UI thread."""
    result = Signal(object)  # (title, runtime, episodes, imdb_rating)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            info = fetch_movie_info(self.url)
        except Exception:
            info = (None, None, None, None)
        self.result.emit(info)


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
        self._update_btn.hide()
        self._skip_btn.hide()
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
        self._update_btn.show()
        self._skip_btn.show()


class MovieWatchlistApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Movie Watchlist v{__version__}")
        icon_path = get_resource_path(os.path.join("assets", "movie-icon-15159.png"))
        self.setWindowIcon(QIcon(icon_path))
        self._sort_col = COL_DAYS_LEFT
        self._sort_order = Qt.AscendingOrder
        self._fetch_worker = None
        self._fetch_ctx = None  # what to do with the result of the in-flight fetch
        self.init_ui()
        self._restore_settings()
        self.table.cellClicked.connect(self.on_cell_clicked)
        self.table.itemChanged.connect(self.on_item_changed)

        # Recompute "Days Left" when the date rolls over while the app is open
        self._today = QDate.currentDate()
        self._day_timer = QTimer(self)
        self._day_timer.timeout.connect(self._check_day_rollover)
        self._day_timer.start(60_000)

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

    def _apply_sort(self):
        if self._sort_col >= 0:
            self.table.sortItems(self._sort_col, self._sort_order)

    def _on_header_clicked(self, col):
        if col == self._sort_col:
            self._sort_order = (Qt.DescendingOrder if self._sort_order == Qt.AscendingOrder
                                else Qt.AscendingOrder)
        else:
            self._sort_col = col
            self._sort_order = Qt.AscendingOrder
        self.table.sortItems(self._sort_col, self._sort_order)
        self.table.horizontalHeader().setSortIndicator(self._sort_col, self._sort_order)

    def _restore_settings(self):
        s = QSettings("MovieWatchlist", "MovieWatchlist")
        geom = s.value("window_geometry")
        if geom:
            self.restoreGeometry(geom)
        else:
            self.resize(900, 700)
        self._sort_col = int(s.value("sort_col", COL_DAYS_LEFT))
        order_val = int(s.value("sort_order", 0))
        self._sort_order = Qt.DescendingOrder if order_val == 1 else Qt.AscendingOrder
        for col in range(self.table.columnCount()):
            w = s.value(f"col_width_{col}")
            if w is not None:
                self.table.setColumnWidth(col, int(w))
        # sort_col == -1 means the user ordered rows manually; rows were loaded
        # in their saved order, so leave them as they are.
        self._apply_sort()
        self.table.horizontalHeader().setSortIndicator(self._sort_col, self._sort_order)

    def _save_settings(self):
        s = QSettings("MovieWatchlist", "MovieWatchlist")
        s.setValue("window_geometry", self.saveGeometry())
        s.setValue("sort_col", self._sort_col)
        s.setValue("sort_order", 1 if self._sort_order == Qt.DescendingOrder else 0)
        for col in range(self.table.columnCount()):
            s.setValue(f"col_width_{col}", self.table.columnWidth(col))

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

        self.cal_btn = QPushButton("📅")
        self.cal_btn.setFixedWidth(38)
        self.cal_btn.setToolTip("Open calendar")
        self.cal_btn.clicked.connect(self.date_input.show_calendar)

        self.platform_input = QComboBox()
        self.platform_input.addItems(PLATFORMS)
        self.platform_input.setFixedWidth(160)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setObjectName("secondary")
        self.clear_btn.setFixedWidth(68)
        self.clear_btn.clicked.connect(self._clear_inputs)

        input_layout.addWidget(self.url_input)
        input_layout.addWidget(self.date_input)
        input_layout.addWidget(self.cal_btn)
        input_layout.addWidget(self.platform_input)
        input_layout.addWidget(self.clear_btn)
        layout.addLayout(input_layout)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(["Title", "Length", "Episodes", "IMDb", "Date", "Days Left", "Platform", "Link", FLAG_ON])
        for col in range(self.table.columnCount()):
            self.table.horizontalHeaderItem(col).setTextAlignment(Qt.AlignCenter)
        self.table.setItemDelegate(NoFocusDelegate(self))
        self.table.setItemDelegateForColumn(COL_DATE, DateDelegate(self))
        self.table.setSortingEnabled(False)
        self.table.horizontalHeader().sectionClicked.connect(self._on_header_clicked)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(COL_TITLE, 220)
        self.table.setColumnWidth(COL_LENGTH, 120)
        self.table.setColumnWidth(COL_EPISODES, 80)
        self.table.setColumnWidth(COL_RATING, 70)
        self.table.setColumnWidth(COL_DATE, 95)
        self.table.setColumnWidth(COL_DAYS_LEFT, 90)
        self.table.setColumnWidth(COL_PLATFORM, 140)
        self.table.setColumnWidth(COL_FLAG, 44)
        self.table.horizontalHeaderItem(COL_FLAG).setToolTip("Flagged — click a cell to toggle")
        # The flag column is the last logical column (so saved column widths
        # and sort settings keep their indices) but is shown first.
        self.table.horizontalHeader().moveSection(COL_FLAG, 0)

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
        layout.addWidget(self.table)
        self.setLayout(layout)

        for row_data in load_movies():
            self._insert_row(*row_data)
        # Sorting is applied in _restore_settings (default: Days Left ascending)

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

    def _set_days_left(self, item, date_str):
        days_key = self._days_left_sort_key(date_str)
        item.setText(self._days_left_text(date_str))
        item.setData(Qt.UserRole, days_key)
        bg, fg = self._urgency_color(days_key)
        item.setBackground(bg if bg else QtGui.QBrush())
        item.setForeground(fg if fg else QtGui.QBrush())

    def _set_flag(self, item, flagged):
        item.setText(FLAG_ON if flagged else FLAG_OFF)
        item.setForeground(QtGui.QBrush(QtGui.QColor(_FLAG_ON_COLOR if flagged else _FLAG_OFF_COLOR)))
        # Sort key: flagged rows come first in ascending order
        item.setData(Qt.UserRole, 0 if flagged else 1)

    def _is_flagged(self, row):
        item = self.table.item(row, COL_FLAG)
        return bool(item) and item.data(Qt.UserRole) == 0

    def toggle_flag(self, row):
        item = self.table.item(row, COL_FLAG)
        if item is None:
            return
        self.table.blockSignals(True)
        self._set_flag(item, not self._is_flagged(row))
        self.table.blockSignals(False)
        # Deliberately no re-sort: the row stays under the cursor

    def _fill_row(self, row, url, title, length, date, platform="", episodes="-", imdb_rating="-",
                  flagged=False):
        """Populate every cell of an existing row. Caller must block signals."""
        flag_item = self._make_item("")
        font = flag_item.font()
        font.setPointSize(13)
        flag_item.setFont(font)
        self._set_flag(flag_item, flagged)
        self.table.setItem(row, COL_FLAG, flag_item)

        self.table.setItem(row, COL_TITLE, self._make_item(title))

        length_item = self._make_item(length)
        length_item.setData(Qt.UserRole, self._length_sort_key(length))
        self.table.setItem(row, COL_LENGTH, length_item)

        self.table.setItem(row, COL_EPISODES, self._make_item(episodes))
        self.table.setItem(row, COL_RATING, self._make_item(imdb_rating))

        date_item = self._make_item(date, editable=True)
        date_item.setData(Qt.UserRole, self._date_sort_key(date))
        self.table.setItem(row, COL_DATE, date_item)

        days_item = self._make_item("")
        self._set_days_left(days_item, date)
        self.table.setItem(row, COL_DAYS_LEFT, days_item)

        self.table.setItem(row, COL_PLATFORM, self._make_item(platform))

        link_item = self._make_item(url)
        link_item.setForeground(QtGui.QColor("blue"))
        self.table.setItem(row, COL_LINK, link_item)

    def _insert_row(self, url, title, length, date, platform="", episodes="-", imdb_rating="-",
                    flagged=False):
        self.table.blockSignals(True)
        row = self.table.rowCount()
        self.table.insertRow(row)
        self._fill_row(row, url, title, length, date, platform, episodes, imdb_rating, flagged)
        self.table.blockSignals(False)

    def _check_day_rollover(self):
        today = QDate.currentDate()
        if today == self._today:
            return
        self._today = today
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            date_item = self.table.item(row, COL_DATE)
            days_item = self.table.item(row, COL_DAYS_LEFT)
            if date_item and days_item:
                self._set_days_left(days_item, date_item.text())
        self.table.blockSignals(False)
        self._apply_sort()

    def on_item_changed(self, item):
        if item.column() != COL_DATE:
            return
        self.table.blockSignals(True)
        date_str = item.text()
        item.setData(Qt.UserRole, self._date_sort_key(date_str))
        days_item = self.table.item(item.row(), COL_DAYS_LEFT)
        if days_item:
            self._set_days_left(days_item, date_str)
        self.table.blockSignals(False)
        # Re-sort after the editor has finished committing
        QTimer.singleShot(0, self._apply_sort)

    # --- background fetching ---
    def _start_fetch(self, url, ctx):
        """Fetch IMDb info in a worker thread; _on_fetch_result handles ctx."""
        self._fetch_ctx = ctx
        self._set_busy(True)
        self._fetch_worker = FetchWorker(url)
        self._fetch_worker.result.connect(self._on_fetch_result)
        self._fetch_worker.finished.connect(self._on_fetch_finished)
        self._fetch_worker.start()

    def _set_busy(self, busy):
        # Buttons that add, replace or reorder rows stay disabled while a
        # fetch is in flight so the target row can't disappear under it.
        for btn in (self.add_button, self.edit_button, self.remove_button,
                    self.up_button, self.down_button):
            btn.setEnabled(not busy)
        self.add_button.setText("Fetching…" if busy else "Add")

    def _on_fetch_finished(self):
        self._set_busy(False)
        self._fetch_worker = None

    def _on_fetch_result(self, info):
        ctx, self._fetch_ctx = self._fetch_ctx, None
        if ctx is None:
            return
        title, length, episodes, imdb_rating = info
        ok = bool(title and length)
        if ctx["kind"] == "add":
            if ok:
                self._insert_row(ctx["url"], title, length, ctx["date"], ctx["platform"],
                                 episodes, imdb_rating)
                self._apply_sort()
                self._clear_inputs()
            else:
                QMessageBox.critical(self, "Error", "Failed to fetch movie data.")
        else:  # edit
            if not ok:
                QMessageBox.warning(self, "Error", "Failed to fetch movie info.")
                return
            try:
                row = self.table.row(ctx["anchor"])  # row may have moved by sorting
            except RuntimeError:
                row = -1
            if row < 0:
                return
            self.table.blockSignals(True)
            # Read the flag now, not at edit start — it may have been toggled meanwhile
            self._fill_row(row, ctx["url"], title, length, ctx["date"], ctx["platform"],
                           episodes, imdb_rating, self._is_flagged(row))
            self.table.blockSignals(False)
            self._apply_sort()

    def add_movie(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Warning", "Please enter an IMDB URL.")
            return
        if not _IMDB_URL_RE.match(url):
            QMessageBox.warning(self, "Warning", "Please enter a valid IMDB URL.\nExample: https://www.imdb.com/title/tt1234567/")
            return

        date = ""
        if self.date_input.date() != _NULL_DATE:
            date = self.date_input.date().toString(DATE_FORMAT)
        platform = self.platform_input.currentText()
        self._start_fetch(url, {"kind": "add", "url": url, "date": date, "platform": platform})

    def _clear_inputs(self):
        self.url_input.clear()
        self.date_input.setDate(_NULL_DATE)
        self.platform_input.setCurrentIndex(0)
        self.url_input.setFocus()

    def remove_movie(self):
        selected = self.table.currentRow()
        if selected < 0:
            return
        title = self.table.item(selected, COL_TITLE).text()
        answer = QMessageBox.question(self, "Remove", f'Remove "{title}" from the list?')
        if answer == QMessageBox.StandardButton.Yes:
            self.table.removeRow(selected)

    def edit_movie(self):
        selected = self.table.currentRow()
        if selected < 0:
            return
        current_url = self.table.item(selected, COL_LINK).text()
        current_date = self.table.item(selected, COL_DATE).text()
        current_platform = self.table.item(selected, COL_PLATFORM).text()

        dialog = EditDialog(current_url, current_date, current_platform, self)
        if not dialog.exec():
            return
        new_url, new_date, new_platform = dialog.get_data()
        if not _IMDB_URL_RE.match(new_url):
            QMessageBox.warning(self, "Warning", "Please enter a valid IMDB URL.\nExample: https://www.imdb.com/title/tt1234567/")
            return
        self._start_fetch(new_url, {
            "kind": "edit",
            "anchor": self.table.item(selected, COL_TITLE),
            "url": new_url, "date": new_date, "platform": new_platform,
        })

    def move_up(self):
        row = self.table.currentRow()
        if row > 0:
            self.swap_rows(row, row - 1)
            self.table.selectRow(row - 1)

    def move_down(self):
        row = self.table.currentRow()
        if 0 <= row < self.table.rowCount() - 1:
            self.swap_rows(row, row + 1)
            self.table.selectRow(row + 1)

    def swap_rows(self, row1, row2):
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
            new1.setFont(item2.font())
            new1.setData(Qt.UserRole, key2)

            new2 = SortableItem(text1)
            new2.setTextAlignment(Qt.AlignCenter)
            new2.setForeground(fg1)
            new2.setBackground(bg1)
            new2.setFlags(flags1)
            new2.setFont(item1.font())
            new2.setData(Qt.UserRole, key1)

            self.table.setItem(row1, col, new1)
            self.table.setItem(row2, col, new2)
        self.table.blockSignals(False)
        # Manual reorder clears the active sort so re-sort doesn't undo the move
        self._sort_col = -1
        self.table.horizontalHeader().setSortIndicator(-1, Qt.AscendingOrder)

    def on_cell_clicked(self, row, column):
        if column == COL_FLAG:
            self.toggle_flag(row)
        elif column == COL_LINK:
            self.open_link(row, column)

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
            try:
                export_to_json(self._movies_from_table(), filepath)
                QMessageBox.information(self, "Success", "Movies exported successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export: {e}")

    def import_movies(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Import Movies", "", "JSON Files (*.json)")
        if filepath:
            try:
                imported = import_from_json(filepath)
                for row_data in imported:
                    self._insert_row(*row_data)
                self._apply_sort()
                QMessageBox.information(self, "Success", f"Imported {len(imported)} movies.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to import: {e}")

    def _movies_from_table(self):
        """The table is the single source of truth, in its current row order."""
        def text(row, col):
            item = self.table.item(row, col)
            return item.text() if item else ""
        return [
            Movie(text(r, COL_LINK), text(r, COL_TITLE), text(r, COL_LENGTH),
                  text(r, COL_DATE), text(r, COL_PLATFORM), text(r, COL_EPISODES),
                  text(r, COL_RATING), self._is_flagged(r))
            for r in range(self.table.rowCount())
        ]

    def closeEvent(self, event):
        # Don't destroy a running fetch thread (Qt aborts the process if a
        # QThread is destroyed while running)
        if self._fetch_worker is not None:
            self._fetch_worker.wait()
        save_movies(self._movies_from_table())
        self._save_settings()

        # Push updated db to Google Drive (silent if not configured)
        try:
            if is_configured():
                upload_db(DB_PATH)
        except Exception as e:
            print(f"Cloud sync upload skipped: {e}")

        event.accept()
        # If a staged update is waiting, rename-swap and relaunch now that
        # all data is saved. Windows allows renaming a running exe safely.
        do_staged_update()


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
        return self.url_input.text().strip(), date, self.platform_input.currentText()


def run_app():
    # Remove _old_version.exe left over from a previous update (if any)
    cleanup_old_version()

    # Move a db left in the working directory by older builds to its fixed home
    try:
        migrate_legacy_db()
    except Exception as e:
        print(f"Legacy db migration skipped: {e}")

    # Pull db from Google Drive if it's newer than the local copy (silent if not configured)
    try:
        if is_configured():
            download_db(DB_PATH)
    except Exception as e:
        print(f"Cloud sync download skipped: {e}")

    init_db()
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLE)
    window = MovieWatchlistApp()
    window.show()

    # Background update check — fires 2 s after startup so it never blocks the UI
    _checker = UpdateCheckWorker()
    _checker.update_available.connect(
        lambda tag, url: UpdateDialog(tag, url, window).exec()
    )
    QTimer.singleShot(2000, _checker.start)

    sys.exit(app.exec())
