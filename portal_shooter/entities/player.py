from __future__ import annotations

import pygame
from pyglm import glm

from portal_shooter.entities.entity import Entity
from portal_shooter.particles import FadeOutParticle, ParticleEmitter


class Player(Entity):
    __slots__ = ["speed", "max_health", "health", "emitter", "aim_target"]

    def __init__(self, pos: glm.vec2, vel: glm.vec2) -> None:
        super().__init__(pos, vel)
        self.speed: int = 50
        self.max_health: int = 100
        self.health: int = 100
        self.aim_target: glm.vec2 = glm.vec2()

        self.emitter: ParticleEmitter = ParticleEmitter(
            pos=self.pos,
            vel=glm.vec2(),
            spawn_rate=0,
            shape=ParticleEmitter.Point(30),
            particle_class=FadeOutParticle,
            particle_kwargs={"color": (200, 0, 0)},
        )

    def update(self, dt: float) -> None:
        self.pos += self.vel * dt
        self.emitter.pos = self.pos
        self.emitter.update(dt)

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(self.pos - glm.vec2(2), (4, 4))

    def draw(self, surface: pygame.Surface, offset: glm.vec2 = glm.vec2()) -> None:
        vec = glm.normalize(self.aim_target - self.pos)
        p = self.pos - offset
        # draw the particles
        self.emitter.draw(surface, offset)

        # draw the "gun"
        pygame.draw.line(
            surface, (0, 200, 200), p + vec * 4, p + vec * 10, 1
        )
        # draw the player
        pygame.draw.circle(surface, (0, 200, 0), p, 2)
