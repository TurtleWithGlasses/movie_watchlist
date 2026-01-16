import sqlite3
import json

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

def export_to_json(movies, filepath):
    data = [
        {
            "url": movie.url,
            "title": movie.title,
            "length": movie.length,
            "watch_date": movie.watch_date
        }
        for movie in movies
    ]
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def import_from_json(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return [(item['url'], item['title'], item['length'], item['watch_date']) for item in data]
