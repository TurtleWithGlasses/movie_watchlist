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
            date TEXT,
            platform TEXT DEFAULT '',
            episodes TEXT DEFAULT '-'
        )
    """)
    # Migrate existing databases that don't have these columns yet
    for col, default in [("platform", "''"), ("episodes", "'-'")]:
        try:
            cursor.execute(f"ALTER TABLE movies ADD COLUMN {col} TEXT DEFAULT {default}")
        except sqlite3.OperationalError:
            pass  # column already exists
    conn.commit()
    conn.close()

def save_movies(movies):
    conn = sqlite3.connect("watchlist.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM movies")
    for movie in movies:
        cursor.execute(
            "INSERT INTO movies (url, title, length, date, platform, episodes) VALUES (?, ?, ?, ?, ?, ?)",
            (movie.url, movie.title, movie.length, movie.watch_date, movie.platform, movie.episodes)
        )
    conn.commit()
    conn.close()

def load_movies():
    conn = sqlite3.connect("watchlist.db")
    cursor = conn.cursor()
    cursor.execute("SELECT url, title, length, date, platform, episodes FROM movies")
    rows = cursor.fetchall()
    conn.close()
    return rows

def export_to_json(movies, filepath):
    data = [
        {
            "url": movie.url,
            "title": movie.title,
            "length": movie.length,
            "watch_date": movie.watch_date,
            "platform": movie.platform,
            "episodes": movie.episodes,
        }
        for movie in movies
    ]
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def import_from_json(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return [
        (item['url'], item['title'], item['length'], item['watch_date'],
         item.get('platform', ''), item.get('episodes', '-'))
        for item in data
    ]
