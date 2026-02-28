from __future__ import annotations

import math
import random

import pygame
from pyglm import glm

from portal_shooter.entities.entity import Entity
from portal_shooter.weapons import WeaponKind

# Per-weapon shell surfaces: (width, height, draw_func)
# Built once per kind and cached at class level.
_shell_cache: dict[WeaponKind, pygame.Surface] = {}


def _build_shell(kind: WeaponKind) -> pygame.Surface:
    if kind == WeaponKind.SHOTGUN:
        # 12-gauge hull: wide, red plastic body + brass base
        surf = pygame.Surface((3, 2), pygame.SRCALPHA)
        pygame.draw.rect(surf, (200, 180, 50), (0, 0, 1, 2))  # brass base
        pygame.draw.rect(surf, (180, 40, 30), (1, 0, 2, 2))  # red hull
        return surf
    if kind == WeaponKind.RIFLE:
        # .308 casing: long, narrow, all brass with copper neck
        surf = pygame.Surface((4, 1), pygame.SRCALPHA)
        pygame.draw.rect(surf, (200, 180, 50), (0, 0, 2, 1))  # brass body
        pygame.draw.rect(surf, (200, 140, 60), (2, 0, 2, 1))  # copper neck
        return surf
    # Pistol / SMG: small 9mm brass casing
    surf = pygame.Surface((2, 1), pygame.SRCALPHA)
    pygame.draw.rect(surf, (200, 180, 50), (0, 0, 2, 1))
    return surf


def _get_shell_surf(kind: WeaponKind) -> pygame.Surface:
    if kind not in _shell_cache:
        _shell_cache[kind] = _build_shell(kind)
    return _shell_cache[kind]


class Shell(Entity):
    __slots__ = [
        "speed",
        "_speed",
        "life",
        "rot_speed",
        "_base_surf",
        "_cached_surf",
        "_cached_angle",
        "_cached_scale",
    ]

    def __init__(
        self, pos: glm.vec2, vel: glm.vec2, kind: WeaponKind = WeaponKind.PISTOL
    ) -> None:
        super().__init__(pos, vel)
        self.speed: float = random.randint(20, 40)
        self._speed: int = int(self.speed)
        self.life: float = 5
        self.rot_speed: float = random.random()
        self._base_surf: pygame.Surface = _get_shell_surf(kind)
        self._cached_angle: float = -1.0
        self._cached_scale: float = -1.0
        self._cached_surf: pygame.Surface = self._base_surf

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
                    self._base_surf, -angle, max(scale, 0.1)
                )

    def draw(self, surface: pygame.Surface, offset: glm.vec2 = glm.vec2()) -> None:
        surf = self._cached_surf
        surface.blit(surf, self.pos - offset - glm.vec2(surf.get_size()) / 2)
