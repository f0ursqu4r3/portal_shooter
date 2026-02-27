from __future__ import annotations

from pathlib import Path

import pygame
from pyglm import glm
from tqdm import tqdm


class SoundPlayer:
    def __init__(self, directory: str, extension: str) -> None:
        pygame.mixer.init(buffer=1024)
        self.cache: dict[str, pygame.mixer.Sound] = {}
        self.directory: str = directory
        self.extension: str = extension
        for file_name in tqdm(
            Path(directory).rglob(f"*.{extension}"), desc="Loading sounds"
        ):
            self.cache[file_name.stem] = pygame.mixer.Sound(str(file_name))
        self.sounds: list[pygame.mixer.Sound] = []

    def play(self, sound_name: str, volume: float = 1) -> None:
        vol = glm.vec2(volume)
        sound = self.cache[sound_name]
        channel = sound.play()
        if channel:
            channel.set_volume(vol.x, vol.y)
