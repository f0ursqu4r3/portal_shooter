from __future__ import annotations

import random

import pygame
from pyglm import glm

from portal_shooter.map.types import Wall
from portal_shooter.particles import FadeOutParticle, ParticleEmitter


class Crate:
    """Destructible box obstacle that blocks movement and bullets."""

    __slots__ = [
        "pos",
        "half_size",
        "health",
        "max_health",
        "alive",
        "walls",
        "_wall_keys",
        "emitter",
    ]

    def __init__(self, pos: glm.vec2, size: float = 12, health: int = 30) -> None:
        self.pos: glm.vec2 = glm.vec2(pos)
        self.half_size: float = size / 2.0
        self.health: int = health
        self.max_health: int = health
        self.alive: bool = True

        hs = self.half_size
        tl = glm.vec2(pos.x - hs, pos.y - hs)
        tr = glm.vec2(pos.x + hs, pos.y - hs)
        br = glm.vec2(pos.x + hs, pos.y + hs)
        bl = glm.vec2(pos.x - hs, pos.y + hs)
        self.walls: list[Wall] = [
            (tl, tr),
            (tr, br),
            (br, bl),
            (bl, tl),
        ]
        # Pre-compute float keys for wall hit lookup
        self._wall_keys: set[tuple[float, float, float, float]] = {
            (w[0].x, w[0].y, w[1].x, w[1].y) for w in self.walls
        }

        self.emitter: ParticleEmitter = ParticleEmitter(
            pos=self.pos,
            vel=None,
            spawn_rate=0,
            shape=ParticleEmitter.Circle(4),
            particle_class=FadeOutParticle,
            particle_kwargs={"color": (160, 130, 80)},
        )

    def take_damage(self, amount: int) -> None:
        self.health -= amount
        self.emitter.burst(random.randint(3, 5))
        if self.health <= 0:
            self.alive = False
            self.emitter.burst(15)

    def update(self, dt: float) -> None:
        self.emitter.update(dt)

    def draw(self, surface: pygame.Surface, offset: glm.vec2 = glm.vec2()) -> None:
        self.emitter.draw(surface, offset)
        if not self.alive:
            return
        p = self.pos - offset
        hs = self.half_size
        # Wooden crate rectangle
        hp_frac = self.health / self.max_health
        r = int(100 + 60 * hp_frac)
        g = int(80 + 50 * hp_frac)
        b = int(40 + 20 * hp_frac)
        rect = pygame.Rect(p.x - hs, p.y - hs, hs * 2, hs * 2)
        pygame.draw.rect(surface, (r, g, b), rect)
        pygame.draw.rect(surface, (80, 60, 30), rect, 1)
        # Cross pattern
        pygame.draw.line(
            surface, (80, 60, 30),
            (int(p.x - hs), int(p.y - hs)),
            (int(p.x + hs), int(p.y + hs)), 1,
        )
        pygame.draw.line(
            surface, (80, 60, 30),
            (int(p.x + hs), int(p.y - hs)),
            (int(p.x - hs), int(p.y + hs)), 1,
        )
