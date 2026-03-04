from __future__ import annotations

import math

import pygame
from pyglm import glm

from portal_shooter.entities.entity import Entity
from portal_shooter.particles import FadeOutParticle, ParticleEmitter

ROCKET_SPEED = 200
ROCKET_DAMAGE = 70
ROCKET_RADIUS = 50


class Rocket(Entity):
    __slots__ = ["speed", "damage", "radius", "bounce", "detonated", "emitter"]

    def __init__(self, pos: glm.vec2, direction: glm.vec2) -> None:
        super().__init__(pos, direction)
        self.speed: float = float(ROCKET_SPEED)
        self.damage: int = ROCKET_DAMAGE
        self.radius: int = ROCKET_RADIUS
        self.bounce: float = 0.0  # no bounce — detonates on impact
        self.detonated: bool = False

        self.emitter: ParticleEmitter = ParticleEmitter(
            pos=self.pos,
            vel=glm.vec2(),
            spawn_rate=20,
            shape=ParticleEmitter.Point(15),
            particle_class=FadeOutParticle,
            particle_kwargs={"color": (200, 80, 60)},
        )

    @property
    def life(self) -> float:
        """Facade: compatible with entity.life < 0 cleanup."""
        return -1.0 if self.detonated else 0.1

    def update(self, dt: float) -> None:
        if self.detonated:
            self.emitter.pos = self.pos
            self.emitter.update(dt)
            return

        self.pos += self.vel * self.speed * dt

        self.emitter.pos = self.pos
        self.emitter.update(dt)

    def draw(self, surface: pygame.Surface, offset: glm.vec2 = glm.vec2()) -> None:
        self.emitter.draw(surface, offset)
        if self.detonated:
            return
        p = self.pos - offset
        px, py = int(p.x), int(p.y)

        # Elongated body along velocity
        if self.vel:
            angle = math.atan2(float(self.vel.y), float(self.vel.x))
            dx = int(math.cos(angle) * 3)
            dy = int(math.sin(angle) * 3)
            pygame.draw.line(surface, (200, 80, 60), (px - dx, py - dy), (px + dx, py + dy), 2)
        else:
            pygame.draw.circle(surface, (200, 80, 60), (px, py), 2)
