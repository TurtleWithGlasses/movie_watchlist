import os
import shutil
import sqlite3
import json

from paths import DB_PATH


def migrate_legacy_db():
    """Older builds stored watchlist.db in the working directory. If the db
    isn't at its fixed location yet but exists in the working directory,
    copy it over so no data is lost."""
    legacy = os.path.abspath("watchlist.db")
    if legacy != os.path.abspath(DB_PATH) and os.path.exists(legacy) and not os.path.exists(DB_PATH):
        shutil.copy2(legacy, DB_PATH)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT,
            title TEXT,
            length TEXT,
            date TEXT,
            platform TEXT DEFAULT '',
            episodes TEXT DEFAULT '-',
            imdb_rating TEXT DEFAULT '-',
            flagged INTEGER DEFAULT 0
        )
    """)
    # Migrate existing databases that don't have these columns yet
    for col, default in [("platform", "''"), ("episodes", "'-'"), ("imdb_rating", "'-'")]:
        try:
            cursor.execute(f"ALTER TABLE movies ADD COLUMN {col} TEXT DEFAULT {default}")
        except sqlite3.OperationalError:
            pass  # column already exists
    try:
        cursor.execute("ALTER TABLE movies ADD COLUMN flagged INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass  # column already exists
    conn.commit()
    conn.close()

def save_movies(movies):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM movies")
    for movie in movies:
        cursor.execute(
            "INSERT INTO movies (url, title, length, date, platform, episodes, imdb_rating, flagged) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (movie.url, movie.title, movie.length, movie.watch_date, movie.platform, movie.episodes,
             movie.imdb_rating, int(movie.flagged))
        )
    conn.commit()
    conn.close()

def load_movies():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT url, title, length, date, platform, episodes, imdb_rating, flagged "
                   "FROM movies ORDER BY id")
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
            "imdb_rating": movie.imdb_rating,
            "flagged": movie.flagged,
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
         item.get('platform', ''), item.get('episodes', '-'), item.get('imdb_rating', '-'),
         bool(item.get('flagged', False)))
        for item in data
    ]
