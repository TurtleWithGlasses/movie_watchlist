import sys
import os
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QMessageBox, QDialog,
    QFileDialog, QDateEdit, QStyledItemDelegate, QComboBox
)
from PySide6.QtCore import Qt, QDate, QTimer
from PySide6 import QtGui
from PySide6.QtGui import QIcon
import webbrowser
import re
from imdb_fetcher import fetch_movie_info
from movie_manager import MovieManager
from models import Movie
from database import init_db, save_movies, load_movies, export_to_json, import_from_json

DATE_FORMAT = "dd/MM/yyyy"
_NULL_DATE = QDate(2000, 1, 1)  # sentinel for "no date selected"

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

        input_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("IMDB URL")

        self.date_input = SmartDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat(DATE_FORMAT)
        self.date_input.setMinimumDate(_NULL_DATE)
        self.date_input.setSpecialValueText("Date to watch")
        self.date_input.setDate(_NULL_DATE)

        self.platform_input = QComboBox()
        self.platform_input.addItems(PLATFORMS)

        input_layout.addWidget(self.url_input)
        input_layout.addWidget(self.date_input)
        input_layout.addWidget(self.platform_input)
        layout.addLayout(input_layout)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Title", "Length", "Date", "Days Left", "Platform", "Link"])
        self.table.setItemDelegateForColumn(COL_DATE, DateDelegate(self))
        self.table.setSortingEnabled(True)
        self.table.setColumnWidth(COL_TITLE, 220)
        self.table.setColumnWidth(COL_LENGTH, 120)
        self.table.setColumnWidth(COL_DATE, 95)
        self.table.setColumnWidth(COL_DAYS_LEFT, 75)
        self.table.setColumnWidth(COL_PLATFORM, 130)
        self.table.setColumnWidth(COL_LINK, 160)
        layout.addWidget(self.table)

        button_layout = QHBoxLayout()
        self.add_button = QPushButton("Add")
        self.remove_button = QPushButton("Remove")
        self.edit_button = QPushButton("Edit")
        self.up_button = QPushButton("↑")
        self.down_button = QPushButton("↓")
        self.export_button = QPushButton("Export")
        self.import_button = QPushButton("Import")

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

        days_item = self._make_item(self._days_left_text(date))
        days_item.setData(Qt.UserRole, self._days_left_sort_key(date))
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
            days_item.setText(self._days_left_text(date_str))
            days_item.setData(Qt.UserRole, self._days_left_sort_key(date_str))
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

                days_item = self._make_item(self._days_left_text(new_date))
                days_item.setData(Qt.UserRole, self._days_left_sort_key(new_date))
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
            flags1, flags2 = item1.flags(), item2.flags()
            key1, key2 = item1.data(Qt.UserRole), item2.data(Qt.UserRole)

            new1 = SortableItem(text2)
            new1.setTextAlignment(Qt.AlignCenter)
            new1.setForeground(fg2)
            new1.setFlags(flags2)
            new1.setData(Qt.UserRole, key2)

            new2 = SortableItem(text1)
            new2.setTextAlignment(Qt.AlignCenter)
            new2.setForeground(fg1)
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
        layout.addWidget(self.url_input)

        date_platform_layout = QHBoxLayout()
        date_platform_layout.addWidget(self.date_input)
        date_platform_layout.addWidget(self.platform_input)
        layout.addLayout(date_platform_layout)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
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
    init_db()
    app = QApplication(sys.argv)
    window = MovieWatchlistApp()
    window.resize(900, 700)
    window.show()
    sys.exit(app.exec())
