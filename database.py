import sqlite3

def init_db():
    conn = sqlite3.connect("watchlist.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT,
            title TEXT,
            length TEXT,
            date TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_movies(movies):
    conn = sqlite3.connect("watchlist.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM movies")  # Clear previous data
    for movie in movies:
        cursor.execute(
            "INSERT INTO movies (url, title, length, date) VALUES (?, ?, ?, ?)",
            (movie.url, movie.title, movie.length, movie.watch_date)
        )
    conn.commit()
    conn.close()

def load_movies():
    conn = sqlite3.connect("watchlist.db")
    cursor = conn.cursor()
    cursor.execute("SELECT url, title, length, date FROM movies")
    rows = cursor.fetchall()
    conn.close()
    return rows
