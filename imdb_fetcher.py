import re
import requests

def fetch_movie_info(imdb_url):
    """Fetch movie title and runtime from IMDB URL using OMDb API."""
    try:
        # Extract IMDB ID from URL (e.g., tt1265990)
        match = re.search(r'(tt\d+)', imdb_url)
        if not match:
            return None, None

        imdb_id = match.group(1)

        # Try multiple OMDb API keys (free tier)
        api_keys = ["c7921dc6", "f84fc31d", "68fd98ab", "trilogy"]

        for api_key in api_keys:
            try:
                api_url = f"http://www.omdbapi.com/?i={imdb_id}&apikey={api_key}"
                response = requests.get(api_url, timeout=10)
                data = response.json()

                if data.get("Response") == "True":
                    title = data.get("Title", "Unknown Title")
                    runtime = data.get("Runtime", "N/A")

                    # Convert "91 min" to "1h 31m(91 min)" format
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

                    return title, runtime
            except:
                continue

        return None, None

    except Exception as e:
        print(f"Error fetching movie info: {e}")
        return None, None
