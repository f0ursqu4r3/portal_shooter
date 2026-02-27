from __future__ import annotations

import pygame
from pyglm import glm

from portal_shooter.particles import FadeOutParticle, ParticleEmitter


class Player:
    __slots__ = ["pos", "vel", "speed", "max_health", "health", "emitter"]

    def __init__(self, pos: glm.vec2, vel: glm.vec2) -> None:
        self.pos: glm.vec2 = glm.vec2(pos)
        self.vel: glm.vec2 = glm.vec2(vel)
        self.speed: int = 50
        self.max_health: int = 100
        self.health: int = 100

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

    def draw(
        self, surface: pygame.Surface, mpos: glm.vec2, offset: glm.vec2 = glm.vec2()
    ) -> None:
        vec = glm.normalize(mpos - self.pos)
        p = self.pos - offset
        # draw the particles
        self.emitter.draw(surface, offset)

        # draw the "gun"
        pygame.draw.line(
            surface, (0, 200, 200), p + vec * 4, p + vec * 10, 1
        )
        # draw the player
        pygame.draw.circle(surface, (0, 200, 0), p, 2)
