from __future__ import annotations

import enum
import math

import pygame
from pyglm import glm

from portal_shooter.entities.entity import Entity


class PickupKind(enum.Enum):
    HEALTH = "health"
    SPEED = "speed"


_COLORS: dict[PickupKind, tuple[int, int, int]] = {
    PickupKind.HEALTH: (0, 200, 80),
    PickupKind.SPEED: (220, 200, 40),
}

_SIZE = 4  # half-size for collision rect


class Pickup(Entity):
    __slots__ = ["kind", "color", "age"]

    def __init__(self, pos: glm.vec2, kind: PickupKind) -> None:
        super().__init__(pos)
        self.kind: PickupKind = kind
        self.color: tuple[int, int, int] = _COLORS[kind]
        self.age: float = 0.0

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(self.pos.x - _SIZE, self.pos.y - _SIZE, _SIZE * 2, _SIZE * 2)

    def update(self, dt: float) -> None:
        self.age += dt

    def draw(self, surface: pygame.Surface, offset: glm.vec2 = glm.vec2()) -> None:
        bob = math.sin(self.age * 3) * 2
        p = self.pos - offset + glm.vec2(0, bob)

        if self.kind == PickupKind.HEALTH:
            # Draw a + cross
            pygame.draw.line(surface, self.color, (p.x - 3, p.y), (p.x + 3, p.y), 1)
            pygame.draw.line(surface, self.color, (p.x, p.y - 3), (p.x, p.y + 3), 1)
        else:
            # Draw a diamond
            pts = [
                (p.x, p.y - 3),
                (p.x + 3, p.y),
                (p.x, p.y + 3),
                (p.x - 3, p.y),
            ]
            pygame.draw.polygon(surface, self.color, pts, 1)
