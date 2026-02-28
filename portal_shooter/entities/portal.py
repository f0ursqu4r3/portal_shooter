from __future__ import annotations

import math

import pygame
from pyglm import glm

from portal_shooter.particles import FadeOutParticle, ParticleEmitter


class Portal:
    __slots__ = [
        "pos",
        "normal",
        "width",
        "_surf",
        "color",
        "particle_emitter",
        "_active",
        "deactivate_when_empty",
        "perp",
        "exit",
        "line",
        "_cached_surf_active",
        "_cached_surf_inactive",
    ]

    def __init__(
        self, pos: glm.vec2, normal: glm.vec2, color: tuple[int, int, int]
    ) -> None:
        self.pos: glm.vec2 = glm.vec2(pos)
        self.normal: glm.vec2 = glm.normalize(glm.vec2(normal))
        self.width: int = 12
        self._surf: pygame.Surface = pygame.Surface((self.width, 1))
        self.color: list[int] = list(color)
        self._surf.fill(self.color)

        self._active: bool = False
        self.deactivate_when_empty: bool = False

        # Cache computed properties (portal never moves)
        self.perp: glm.vec2 = glm.normalize(glm.vec2(-self.normal.y, self.normal.x))
        self.exit: glm.vec2 = self.pos + self.normal * 2
        start = self.pos - self.perp * self.width / 2
        end = self.pos + self.perp * self.width / 2
        self.line: tuple[glm.vec2, glm.vec2] = (start, end)

        # Cache rotated surfaces for active/inactive states
        degrees = math.degrees(math.atan2(self.perp.y, self.perp.x))
        angle = (360 + degrees) % 360
        rotated = pygame.transform.rotate(self._surf, -angle)
        self._cached_surf_inactive: pygame.Surface = rotated.copy()
        self._cached_surf_inactive.set_alpha(100)
        self._cached_surf_active: pygame.Surface = rotated.copy()
        self._cached_surf_active.set_alpha(200)

        self.particle_emitter: ParticleEmitter = ParticleEmitter(
            pos=self.pos,
            vel=self.normal,
            spawn_rate=10,
            shape=ParticleEmitter.Line(self.perp * (self.width - 4)),
            particle_class=FadeOutParticle,
            particle_kwargs={"color": self.color},
        )

    @property
    def active(self) -> bool:
        return self._active

    @active.setter
    def active(self, value: bool) -> None:
        self._active = value

    def burst(self) -> None:
        self.particle_emitter.burst()

    def update(self, dt: float) -> None:
        if self._active:
            self.particle_emitter.update(dt)

    def draw(self, surface: pygame.Surface, offset: glm.vec2 = glm.vec2()) -> None:
        self.particle_emitter.draw(surface, offset)
        surf = self._cached_surf_active if self._active else self._cached_surf_inactive
        surface.blit(surf, self.pos - offset - glm.vec2(surf.get_size()) / 2)
