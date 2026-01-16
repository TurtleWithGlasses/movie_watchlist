from models import Movie

class MovieManager:
    def __init__(self):
        self.movies = []

    def add_movie(self, movie):
        self.movies.append(movie)

    def remove_movie(self, index):
        if 0 <= index < len(self.movies):
            self.movies.pop(index)

    def move_up(self, index):
        if index > 0:
            self.movies[index - 1], self.movies[index] = self.movies[index], self.movies[index - 1]

    def move_down(self, index):
        if index < len(self.movies) - 1:
            self.movies[index + 1], self.movies[index] = self.movies[index], self.movies[index + 1]

    def edit_movie(self, index, new_movie):
        if 0 <= index < len(self.movies):
            self.movies[index] = new_movie
