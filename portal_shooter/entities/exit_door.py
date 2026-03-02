from __future__ import annotations

import math

import pygame
from pyglm import glm

from portal_shooter.entities.entity import Entity


class ExitDoor(Entity):
    __slots__ = ["active", "age", "_interact_range"]

    def __init__(self, pos: glm.vec2) -> None:
        super().__init__(pos)
        self.active: bool = False
        self.age: float = 0.0
        self._interact_range: float = 16.0

    def in_range(self, player_pos: glm.vec2) -> bool:
        return glm.distance(self.pos, player_pos) < self._interact_range

    def update(self, dt: float) -> None:
        self.age += dt

    def draw(self, surface: pygame.Surface, offset: glm.vec2 = glm.vec2()) -> None:
        p = self.pos - offset
        px, py = int(p.x), int(p.y)

        if self.active:
            # Pulsing green door
            pulse = 0.6 + 0.4 * math.sin(self.age * 4)
            g = int(180 * pulse)
            color = (40, g, 60)
            border_color = (60, 220, 80)
        else:
            # Dim gray locked door
            color = (40, 40, 45)
            border_color = (70, 70, 75)

        # Door frame
        pygame.draw.rect(surface, color, (px - 5, py - 6, 10, 12))
        pygame.draw.rect(surface, border_color, (px - 5, py - 6, 10, 12), 1)

        # Door handle dot
        if self.active:
            pygame.draw.circle(surface, (220, 255, 220), (px + 3, py), 1)
