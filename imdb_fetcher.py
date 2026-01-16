import requests
from bs4 import BeautifulSoup

def fetch_movie_info(imdb_url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9"
        }
        response = requests.get(imdb_url, headers=headers)
        soup = BeautifulSoup(response.content, 'html.parser')

        # ✅ Updated title selector
        title_tag = soup.find("span", {"data-testid": "hero__primary-text"})
        title = title_tag.text.strip() if title_tag else "Unknown Title"

        # ✅ Runtime selector (still works)
        runtime_tag = soup.find("li", {"data-testid": "title-techspec_runtime"})
        if runtime_tag:
            runtime = runtime_tag.find("div").text.strip()
        else:
            runtime = "Unknown Length"

        return title, runtime

    except Exception as e:
        print(f"Error fetching from IMDB: {e}")
        return None, None
