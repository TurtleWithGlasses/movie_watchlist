class Movie:
    def __init__(self, url, title, length, watch_date, platform="", episodes="-"):
        self.url = url
        self.title = title
        self.length = length
        self.watch_date = watch_date
        self.platform = platform
        self.episodes = episodes
