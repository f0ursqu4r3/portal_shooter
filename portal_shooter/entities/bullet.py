from __future__ import annotations

import math

import pygame
from pyglm import glm


class Bullet:
    __slots__ = [
        "pos",
        "vel",
        "speed",
        "_speed",
        "life",
        "_cached_surf",
        "_cached_angle",
        "_cached_scale",
    ]

    _base_surf: pygame.Surface | None = None

    @classmethod
    def _get_base_surf(cls) -> pygame.Surface:
        if cls._base_surf is None:
            cls._base_surf = pygame.Surface((4, 2))
            pygame.draw.rect(cls._base_surf, (100, 100, 100), (0, 0, 4, 2))
        return cls._base_surf

    def __init__(self, pos: glm.vec2, vel: glm.vec2) -> None:
        self.pos: glm.vec2 = glm.vec2(pos)
        self.vel: glm.vec2 = glm.vec2(vel)
        self.speed: int = 100
        self._speed: int = 100
        self.life: float = 5
        self._cached_angle: float = -1.0
        self._cached_scale: float = -1.0
        self._cached_surf: pygame.Surface = self._get_base_surf()

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(self.pos - glm.vec2(1), (2, 2))

    def update(self, dt: float) -> None:
        self.pos += self.vel * self.speed * dt
        self.life -= dt
        if self.vel:
            vel = glm.normalize(self.vel)
            angle = round((360 + math.degrees(math.atan2(vel.y, vel.x))) % 360)
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
