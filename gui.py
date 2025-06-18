import sys
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QMessageBox, QDialog
)
from PySide6.QtCore import Qt
from PySide6 import QtGui
from PySide6.QtGui import QIcon
import webbrowser
from imdb_fetcher import fetch_movie_info
from movie_manager import MovieManager
from models import Movie
from database import init_db, save_movies, load_movies


class MovieWatchlistApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Movie Watchlist")
        self.setWindowIcon(QIcon("movie-icon-15134.png"))
        self.manager = MovieManager()        
        self.init_ui()
        init_db()
        self.table.cellClicked.connect(self.open_link)
    
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

        self.add_button.clicked.connect(self.add_movie)
        self.remove_button.clicked.connect(self.remove_movie)
        self.edit_button.clicked.connect(self.edit_movie)
        self.up_button.clicked.connect(self.move_up)
        self.down_button.clicked.connect(self.move_down)

        for btn in [self.add_button, self.remove_button, self.edit_button, self.up_button, self.down_button]:
            button_layout.addWidget(btn)

        layout.addLayout(button_layout)
        self.setLayout(layout)
    # Load saved movies
        for url, title, length, date in load_movies():
            self.manager.add_movie(Movie(url, title, length, date))
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(title))
            self.table.setItem(row, 1, QTableWidgetItem(length))
            self.table.setItem(row, 2, QTableWidgetItem(date))
            link_item = QTableWidgetItem("Link")
            link_item.setData(0, url)
            link_item.setForeground(QtGui.QColor("blue"))
            link_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 3, link_item)


    def add_movie(self):
        url = self.url_input.text()
        date = self.date_input.text()
        title, length = fetch_movie_info(url)

        if title and length:
            movie = Movie(url, title, length, date)
            self.manager.add_movie(movie)
            row = self.table.rowCount()
            self.table.insertRow(row)

            self.table.setItem(row, 0, QTableWidgetItem(title))
            self.table.setItem(row, 1, QTableWidgetItem(length))
            self.table.setItem(row, 2, QTableWidgetItem(date))

            # 🔹 Create the clickable "Link" cell
            link_item = QTableWidgetItem("Link")
            link_item.setData(0, url)  # Store the actual URL in the cell
            link_item.setForeground(QtGui.QColor("blue"))  # Make it look like a link
            link_item.setTextAlignment(Qt.AlignCenter)     # Center the text
            self.table.setItem(row, 3, link_item)  # Add to 4th column (index 3)

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
                    self.table.setItem(selected, 0, QTableWidgetItem(new_title))
                    self.table.setItem(selected, 1, QTableWidgetItem(new_length))
                    self.table.setItem(selected, 2, QTableWidgetItem(new_date))

                    link_item = QTableWidgetItem("Link")
                    link_item.setData(0, new_url)
                    link_item.setForeground(QtGui.QColor("blue"))
                    link_item.setTextAlignment(Qt.AlignCenter)
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
            temp = self.table.item(row1, col).text()
            self.table.setItem(row1, col, QTableWidgetItem(self.table.item(row2, col).text()))
            self.table.setItem(row2, col, QTableWidgetItem(temp))

    def open_link(self, row, column):
        if column == 3:  # Only act if 'Link' column
            item = self.table.item(row, column)
            if item:
                url = item.data(0)
                if url:
                    webbrowser.open(url)

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