from __future__ import annotations

import random
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

        # Build variant groups: "Shoot" -> ["Shoot1", "Shoot2", ...]
        self._variants: dict[str, list[str]] = {}
        for name in self.cache:
            # Strip trailing digits to find the base name
            base = name.rstrip("0123456789")
            if base not in self._variants:
                self._variants[base] = []
            self._variants[base].append(name)

    def play(self, sound_name: str, volume: float = 1, pan: float = 0.0) -> None:
        sound = self.cache[sound_name]
        channel = sound.play()
        if channel:
            left = volume * min(1.0, 1.0 - pan)
            right = volume * min(1.0, 1.0 + pan)
            channel.set_volume(left, right)

    def play_random(self, base_name: str, volume: float = 1, pan: float = 0.0) -> None:
        """Play a random variant of a sound (e.g. 'Ricochet' picks from Ricochet1, Ricochet2)."""
        variants = self._variants.get(base_name)
        if variants:
            self.play(random.choice(variants), volume=volume, pan=pan)
        elif base_name in self.cache:
            self.play(base_name, volume=volume, pan=pan)
