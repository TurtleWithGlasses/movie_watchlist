import requests
import re
from bs4 import BeautifulSoup

def fetch_movie_info(imdb_url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9"
        }
        response = requests.get(imdb_url, headers=headers)
        soup = BeautifulSoup(response.content, 'html.parser')

        # Title selector
        title_tag = soup.find("span", {"data-testid": "hero__primary-text"})
        title = title_tag.text.strip() if title_tag else "Unknown Title"

        # Runtime - look in the inline list near the title (format: "1h 51m" or "2h 8m")
        runtime = "Unknown Length"

        # Method 1: Find from inline list items containing hour/minute pattern
        inline_items = soup.find_all("li", class_="ipc-inline-list__item")
        for item in inline_items:
            text = item.get_text(strip=True)
            if re.match(r'^\d+h(\s*\d+m)?$|^\d+m$', text):
                runtime = text
                break

        # Method 2: Fallback to tech specs if available
        if runtime == "Unknown Length":
            runtime_tag = soup.find("li", {"data-testid": "title-techspec_runtime"})
            if runtime_tag:
                div = runtime_tag.find("div")
                if div:
                    runtime = div.text.strip()

        return title, runtime

    except Exception as e:
        print(f"Error fetching from IMDB: {e}")
        return None, None
