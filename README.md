# 🎬 Movie Watchlist App (PySide6)

A simple yet powerful desktop application to organize your movie watchlist, built with Python and PySide6. Add movies via IMDb links, set deadlines to watch them, and keep your list saved between sessions.

---

## ✨ Features

- 📥 **Paste IMDb URL** – Automatically fetches movie title and duration
- 🗓 **Set Watch Deadline** – Manually enter a "date to watch"
- 🖱 **Edit Movies** – Double-click or use the Edit button to modify details
- 🔗 **Clickable IMDb Links** – Opens the movie page in your default browser
- 🧭 **Reorder List** – Move movies up/down
- 🗃 **Persistent Storage** – Saves and loads from a local SQLite database
- 🧱 **Built with PySide6** – Native-looking GUI on Windows

---

## 🛠 Requirements

- Python 3.10+
- PySide6
- BeautifulSoup4
- requests

Install all requirements:
pip install -r requirements.txt

🚀 Run the App
python main.py
Or run the .exe from the /dist folder if you're using a compiled version (via PyInstaller or Nuitka).

🧱 Packaging into an Executable
You can build the app into a Windows .exe using:
pyinstaller main.py --onefile --windowed --icon=assets/icon.ico --collect-all PySide6

📂 Project Structure
movie_watchlist_app/
│
├── assets/                 # App icons or images
├── database.py             # SQLite database interface
├── gui.py                  # Main PySide6 GUI logic
├── imdb_fetcher.py         # IMDb scraper logic
├── main.py                 # Entry point
├── models.py               # Movie class
├── movie_manager.py        # Movie management logic
├── requirements.txt
└── README.md
