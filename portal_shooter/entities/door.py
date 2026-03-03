from __future__ import annotations

import math

import pygame
from pyglm import glm

from portal_shooter.entities.entity import Entity
from portal_shooter.map.types import Wall


class Door(Entity):
    """A wall segment that can be opened/closed. When closed, blocks movement."""

    __slots__ = ["wall", "_wall_key", "is_open", "color", "age"]

    def __init__(self, p1: glm.vec2, p2: glm.vec2, color: tuple[int, int, int] = (180, 100, 50)) -> None:
        mid = (p1 + p2) * 0.5
        super().__init__(mid)
        self.wall: Wall = (glm.vec2(p1), glm.vec2(p2))
        self._wall_key: tuple[float, float, float, float] = (
            self.wall[0].x, self.wall[0].y, self.wall[1].x, self.wall[1].y,
        )
        self.is_open: bool = False
        self.color: tuple[int, int, int] = color
        self.age: float = 0.0

    def update(self, dt: float) -> None:
        self.age += dt

    def draw(self, surface: pygame.Surface, offset: glm.vec2 = glm.vec2()) -> None:
        if self.is_open:
            return
        p1 = self.wall[0] - offset
        p2 = self.wall[1] - offset
        # Thick colored line for the door
        pygame.draw.line(surface, self.color, (int(p1.x), int(p1.y)), (int(p2.x), int(p2.y)), 2)


class Switch(Entity):
    """Pressure plate that opens a linked door when stepped on."""

    __slots__ = ["door", "activated", "color", "age"]

    def __init__(self, pos: glm.vec2, door: Door, color: tuple[int, int, int] = (180, 100, 50)) -> None:
        super().__init__(pos)
        self.door: Door = door
        self.activated: bool = False
        self.color: tuple[int, int, int] = color
        self.age: float = 0.0

    def check_activate(self, player_pos: glm.vec2) -> bool:
        """Check if player is on the switch. Returns True if newly activated."""
        if self.activated:
            return False
        if glm.distance(self.pos, player_pos) < 8:
            self.activated = True
            self.door.is_open = True
            return True
        return False

    def update(self, dt: float) -> None:
        self.age += dt

    def draw(self, surface: pygame.Surface, offset: glm.vec2 = glm.vec2()) -> None:
        p = self.pos - offset
        px, py = int(p.x), int(p.y)
        if self.activated:
            # Pressed plate — darker, flat
            pygame.draw.rect(surface, (60, 40, 25), (px - 4, py - 4, 8, 8))
        else:
            # Raised plate — bright colored square
            r, g, b = self.color
            pulse = 0.7 + 0.3 * math.sin(self.age * 3)
            cr = int(r * pulse)
            cg = int(g * pulse)
            cb = int(b * pulse)
            pygame.draw.rect(surface, (cr, cg, cb), (px - 4, py - 4, 8, 8))
            pygame.draw.rect(surface, (r, g, b), (px - 4, py - 4, 8, 8), 1)
