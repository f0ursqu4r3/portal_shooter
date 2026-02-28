from __future__ import annotations

import math
import random

import pygame
from pyglm import glm

from portal_shooter.entities.entity import Entity


class Shell(Entity):
    __slots__ = [
        "speed",
        "_speed",
        "life",
        "rot_speed",
        "_cached_surf",
        "_cached_angle",
        "_cached_scale",
    ]

    _base_surf: pygame.Surface | None = None

    @classmethod
    def _get_base_surf(cls) -> pygame.Surface:
        if cls._base_surf is None:
            cls._base_surf = pygame.Surface((4, 2))
            pygame.draw.rect(cls._base_surf, (200, 200, 0), (0, 0, 1, 2))
            pygame.draw.rect(cls._base_surf, (200, 0, 0), (1, 0, 3, 2))
        return cls._base_surf

    def __init__(self, pos: glm.vec2, vel: glm.vec2) -> None:
        super().__init__(pos, vel)
        self.speed: float = random.randint(20, 40)
        self._speed: int = int(self.speed)
        self.life: float = 5
        self.rot_speed: float = random.random()
        self._cached_angle: float = -1.0
        self._cached_scale: float = -1.0
        self._cached_surf: pygame.Surface = self._get_base_surf()

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(self.pos - glm.vec2(1), (2, 2))

    def update(self, dt: float) -> None:
        self.pos += self.vel * self.speed * dt
        self.life -= dt
        self.speed *= 1 - dt * 1.8
        if self.vel and self.speed > 0.01:
            vel = glm.normalize(self.vel)
            degrees = math.degrees(math.atan2(vel.y, vel.x))
            angle = round(
                (
                    360
                    + degrees
                    - 90
                    - (360 * ((self.speed / self._speed) * self.rot_speed))
                )
                % 360
            )
            scale = round(self.life / 5, 1)
            if angle != self._cached_angle or scale != self._cached_scale:
                self._cached_angle = angle
                self._cached_scale = scale
                self._cached_surf = pygame.transform.rotozoom(
                    self._get_base_surf(), -angle, max(scale, 0.1)
                )

    def draw(self, surface: pygame.Surface, offset: glm.vec2 = glm.vec2()) -> None:
        surf = self._cached_surf
        surface.blit(surf, self.pos - offset - glm.vec2(surf.get_size()) / 2)
