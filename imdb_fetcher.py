import re
import requests

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def _get_episode_count(imdb_id, imdb_url):
    """Return total episode count string, or '-' on failure.

    Tries TVMaze first (reliable, JS-free JSON API), then falls back to
    scraping the IMDB page for the numberOfEpisodes schema.org field.
    """
    # ── TVMaze (primary) ────────────────────────────────────────────────────
    try:
        r1 = requests.get(
            f"https://api.tvmaze.com/lookup/shows?imdb={imdb_id}",
            timeout=6,
        )
        if r1.status_code == 200:
            show_id = r1.json().get("id")
            if show_id:
                r2 = requests.get(
                    f"https://api.tvmaze.com/shows/{show_id}/episodes",
                    timeout=6,
                )
                if r2.status_code == 200:
                    count = len(r2.json())
                    if count:
                        return str(count)
    except Exception:
        pass

    # ── IMDB page scrape (fallback) ─────────────────────────────────────────
    try:
        resp = requests.get(imdb_url, headers=_HEADERS, timeout=10)
        html = resp.text
        # JSON-LD schema.org field — present in server-rendered HTML
        m = re.search(r'"numberOfEpisodes"\s*:\s*(\d+)', html)
        if m:
            return m.group(1)
        # hero subnav span — only present when JS-rendered, kept as last resort
        m = re.search(
            r'data-testid="hero-subnav-bar-series-episode-count"[^>]*>\s*(\d+)',
            html,
        )
        if m:
            return m.group(1)
    except Exception:
        pass

    return "-"


def fetch_movie_info(imdb_url):
    """Fetch title, runtime, episode count, and IMDb rating from an IMDB URL.

    Returns (title, runtime, episodes, imdb_rating).
    Returns (None, None, None, None) on failure.
    """
    try:
        match = re.search(r'(tt\d+)', imdb_url)
        if not match:
            return None, None, None

        imdb_id = match.group(1)
        api_keys = ["c7921dc6", "f84fc31d", "68fd98ab", "trilogy"]

        for api_key in api_keys:
            try:
                api_url = f"http://www.omdbapi.com/?i={imdb_id}&apikey={api_key}"
                response = requests.get(api_url, timeout=10)
                data = response.json()

                if data.get("Response") == "True":
                    title = data.get("Title", "Unknown Title")
                    runtime = data.get("Runtime", "N/A")

                    if runtime and runtime != "N/A":
                        min_match = re.match(r'(\d+)\s*min', runtime)
                        if min_match:
                            total_mins = int(min_match.group(1))
                            hours = total_mins // 60
                            mins = total_mins % 60
                            if hours and mins:
                                runtime = f"{hours}h {mins}m({total_mins} min)"
                            elif hours:
                                runtime = f"{hours}h({total_mins} min)"
                            else:
                                runtime = f"{mins}m({total_mins} min)"

                    episodes = "-"
                    if data.get("Type") == "series":
                        episodes = _get_episode_count(imdb_id, imdb_url)

                    imdb_rating = data.get("imdbRating") or "-"

                    return title, runtime, episodes, imdb_rating
            except Exception:
                continue

        return None, None, None, None

    except Exception as e:
        print(f"Error fetching movie info: {e}")
        return None, None, None, None
