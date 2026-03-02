from __future__ import annotations

from pathlib import Path

import pygame
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

    def play(self, sound_name: str, volume: float = 1, pan: float = 0.0) -> None:
        sound = self.cache[sound_name]
        channel = sound.play()
        if channel:
            left = volume * min(1.0, 1.0 - pan)
            right = volume * min(1.0, 1.0 + pan)
            channel.set_volume(left, right)
