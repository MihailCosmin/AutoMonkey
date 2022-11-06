from os import listdir
from os.path import join
from os.path import isfile
from os.path import dirname
from moviepy.editor import VideoFileClip

current_file_path = dirname(__file__)

for movie in listdir(current_file_path):
    if movie.endswith('.wmv') and not isfile(join(current_file_path, movie[:-4] + '.gif')):
        movie = join(current_file_path, movie)
        clip = VideoFileClip(movie)
        clip.write_gif(movie[:-4] + '.gif')