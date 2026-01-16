import sys
import os
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QMessageBox, QDialog,
    QFileDialog
)
from PySide6.QtCore import Qt
from PySide6 import QtGui
from PySide6.QtGui import QIcon
import webbrowser
import re
from imdb_fetcher import fetch_movie_info
from movie_manager import MovieManager
from models import Movie
from database import init_db, save_movies, load_movies, export_to_json, import_from_json


def get_resource_path(relative_path):
    """Get path to resource, works for dev and PyInstaller bundle."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)


class MovieWatchlistApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Movie Watchlist")
        icon_path = get_resource_path(os.path.join("assets", "movie-icon-15159.png"))
        self.setWindowIcon(QIcon(icon_path))
        self.manager = MovieManager()
        self.init_ui()
        self.table.cellClicked.connect(self.open_link)

    def create_centered_item(self, text):
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignCenter)
        return item
    
    def init_ui(self):
        layout = QVBoxLayout()

        input_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("IMDB URL")
        self.date_input = QLineEdit()
        self.date_input.setPlaceholderText("Date to watch")
        input_layout.addWidget(self.url_input)
        input_layout.addWidget(self.date_input)
        layout.addLayout(input_layout)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Title", "Length", "Date", "Link"])
        layout.addWidget(self.table)
        self.table.setColumnWidth(0, 280)  # Title column
        self.table.setColumnWidth(1, 150)   # Length column
        self.table.setColumnWidth(2, 100)  # Date column
        self.table.setColumnWidth(3, 150)  # Link column

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

        for btn in [self.add_button, self.remove_button, self.edit_button, self.up_button, self.down_button, self.export_button, self.import_button]:
            button_layout.addWidget(btn)

        layout.addLayout(button_layout)
        self.setLayout(layout)
    # Load saved movies
        for url, title, length, date in load_movies():
            self.manager.add_movie(Movie(url, title, length, date))
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, self.create_centered_item(title))
            self.table.setItem(row, 1, self.create_centered_item(length))
            self.table.setItem(row, 2, self.create_centered_item(date))
            link_item = self.create_centered_item("Link")
            link_item.setData(0, url)
            link_item.setForeground(QtGui.QColor("blue"))
            self.table.setItem(row, 3, link_item)


    def add_movie(self):
        url = self.url_input.text().strip()
        date = self.date_input.text().strip()

        if not url:
            QMessageBox.warning(self, "Warning", "Please enter an IMDB URL.")
            return

        if not re.match(r'https?://(www\.)?imdb\.com/title/tt\d+', url):
            QMessageBox.warning(self, "Warning", "Please enter a valid IMDB URL.\nExample: https://www.imdb.com/title/tt1234567/")
            return

        title, length = fetch_movie_info(url)

        if title and length:
            movie = Movie(url, title, length, date)
            self.manager.add_movie(movie)
            row = self.table.rowCount()
            self.table.insertRow(row)

            self.table.setItem(row, 0, self.create_centered_item(title))
            self.table.setItem(row, 1, self.create_centered_item(length))
            self.table.setItem(row, 2, self.create_centered_item(date))

            link_item = self.create_centered_item("Link")
            link_item.setData(0, url)
            link_item.setForeground(QtGui.QColor("blue"))
            self.table.setItem(row, 3, link_item)

            self.url_input.clear()
            self.date_input.clear()
        else:
            QMessageBox.critical(self, "Error", "Failed to fetch movie data.")


    def remove_movie(self):
        selected = self.table.currentRow()
        if selected >= 0:
            self.manager.remove_movie(selected)
            self.table.removeRow(selected)

    def edit_movie(self):
        selected = self.table.currentRow()
        if selected >= 0:
            current_url = self.table.item(selected, 3).data(0)
            current_date = self.table.item(selected, 2).text()
            
            dialog = EditDialog(current_url, current_date, self)
            if dialog.exec():
                # User clicked OK
                new_url, new_date = dialog.get_data()
                new_title, new_length = fetch_movie_info(new_url)

                if new_title and new_length:
                    # Update table
                    self.table.setItem(selected, 0, self.create_centered_item(new_title))
                    self.table.setItem(selected, 1, self.create_centered_item(new_length))
                    self.table.setItem(selected, 2, self.create_centered_item(new_date))

                    link_item = self.create_centered_item("Link")
                    link_item.setData(0, new_url)
                    link_item.setForeground(QtGui.QColor("blue"))
                    self.table.setItem(selected, 3, link_item)

                    # Update MovieManager
                    self.manager.edit_movie(selected, Movie(new_url, new_title, new_length, new_date))
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
        for col in range(self.table.columnCount()):
            item1 = self.table.item(row1, col)
            item2 = self.table.item(row2, col)

            text1 = item1.text()
            text2 = item2.text()
            data1 = item1.data(0)
            data2 = item2.data(0)

            new_item1 = self.create_centered_item(text2)
            new_item2 = self.create_centered_item(text1)

            if data2:
                new_item1.setData(0, data2)
                new_item1.setForeground(QtGui.QColor("blue"))
            if data1:
                new_item2.setData(0, data1)
                new_item2.setForeground(QtGui.QColor("blue"))

            self.table.setItem(row1, col, new_item1)
            self.table.setItem(row2, col, new_item2)

    def open_link(self, row, column):
        if column == 3:  # Only act if 'Link' column
            item = self.table.item(row, column)
            if item:
                url = item.data(0)
                if url:
                    webbrowser.open(url)

    def export_movies(self):
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "Warning", "No movies to export.")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export Movies", "", "JSON Files (*.json)"
        )
        if filepath:
            movies = []
            for row in range(self.table.rowCount()):
                title = self.table.item(row, 0).text()
                length = self.table.item(row, 1).text()
                date = self.table.item(row, 2).text()
                url = self.table.item(row, 3).data(0)
                movies.append(Movie(url, title, length, date))
            try:
                export_to_json(movies, filepath)
                QMessageBox.information(self, "Success", "Movies exported successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export: {e}")

    def import_movies(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Import Movies", "", "JSON Files (*.json)"
        )
        if filepath:
            try:
                imported = import_from_json(filepath)
                for url, title, length, date in imported:
                    movie = Movie(url, title, length, date)
                    self.manager.add_movie(movie)
                    row = self.table.rowCount()
                    self.table.insertRow(row)
                    self.table.setItem(row, 0, self.create_centered_item(title))
                    self.table.setItem(row, 1, self.create_centered_item(length))
                    self.table.setItem(row, 2, self.create_centered_item(date))
                    link_item = self.create_centered_item("Link")
                    link_item.setData(0, url)
                    link_item.setForeground(QtGui.QColor("blue"))
                    self.table.setItem(row, 3, link_item)
                QMessageBox.information(self, "Success", f"Imported {len(imported)} movies.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to import: {e}")

    def closeEvent(self, event):
        self.manager.movies.clear()

        for row in range(self.table.rowCount()):
            title = self.table.item(row, 0).text()
            length = self.table.item(row, 1).text()
            date = self.table.item(row, 2).text()
            url_item = self.table.item(row, 3)
            url = url_item.data(0) if url_item else ""

            movie = Movie(url, title, length, date)
            self.manager.add_movie(movie)
        
        save_movies(self.manager.movies)
        event.accept()

class EditDialog(QDialog):
    def __init__(self, current_url, current_date, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Movie")
        self.resize(600, 150)
        self.url_input = QLineEdit(current_url)
        self.date_input = QLineEdit(current_date)

        layout = QVBoxLayout()
        layout.addWidget(self.url_input)
        layout.addWidget(self.date_input)

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
        return self.url_input.text(), self.date_input.text()

def run_app():
    init_db()
    app = QApplication(sys.argv)
    window = MovieWatchlistApp()
    window.resize(800, 700)
    window.show()
    sys.exit(app.exec())