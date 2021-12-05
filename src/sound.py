import pygame
from pygame import Vector2

from tqdm import tqdm
from pathlib import Path


class SoundPlayer:
    def __init__(self, directory, extension):
        pygame.mixer.init(buffer=1024)
        self.cache = {}
        self.directory = directory
        self.extension = extension
        for file_name in tqdm(Path(directory).rglob(f'*.{extension}'), desc='Loading sounds'):
            self.cache[file_name.stem] = pygame.mixer.Sound(str(file_name))
        self.sounds = []

    def play(self, sound_name, volume=1):
        vol = Vector2(volume)
        sound = self.cache[sound_name]
        channel = sound.play()
        if channel:
            channel.set_volume(*vol.xy)
