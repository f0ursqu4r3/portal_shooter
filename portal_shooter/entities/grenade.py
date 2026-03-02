from __future__ import annotations

import math

import pygame
from pyglm import glm

from portal_shooter.entities.entity import Entity
from portal_shooter.particles import FadeOutParticle, ParticleEmitter

GRENADE_SPEED = 120
GRENADE_FUSE = 2.0
GRENADE_RADIUS = 40
GRENADE_DAMAGE = 50
GRENADE_BOUNCE = 0.5


class Grenade(Entity):
    __slots__ = ["speed", "fuse", "damage", "radius", "bounce", "detonated", "age", "emitter"]

    def __init__(self, pos: glm.vec2, direction: glm.vec2) -> None:
        super().__init__(pos, direction)
        self.speed: float = float(GRENADE_SPEED)
        self.fuse: float = GRENADE_FUSE
        self.damage: int = GRENADE_DAMAGE
        self.radius: int = GRENADE_RADIUS
        self.bounce: float = GRENADE_BOUNCE
        self.detonated: bool = False
        self.age: float = 0.0

        self.emitter: ParticleEmitter = ParticleEmitter(
            pos=self.pos,
            vel=glm.vec2(),
            spawn_rate=15,
            shape=ParticleEmitter.Point(20),
            particle_class=FadeOutParticle,
            particle_kwargs={"color": (220, 200, 60)},
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

        self.age += dt
        self.fuse -= dt

        # Move with friction
        self.pos += self.vel * self.speed * dt
        self.speed *= 0.97

        self.emitter.pos = self.pos
        self.emitter.update(dt)

        if self.fuse <= 0:
            self.detonated = True

    def draw(self, surface: pygame.Surface, offset: glm.vec2 = glm.vec2()) -> None:
        self.emitter.draw(surface, offset)
        if self.detonated:
            return
        p = self.pos - offset
        px, py = int(p.x), int(p.y)

        # Blink during last 0.5s
        if self.fuse < 0.5 and int(self.age * 10) % 2 == 0:
            color = (255, 100, 60)
        else:
            color = (180, 200, 60)

        # Small circle body
        pygame.draw.circle(surface, color, (px, py), 2)
        # Fuse line
        fuse_angle = math.radians(45)
        fx = px + int(math.cos(fuse_angle) * 3)
        fy = py - int(math.sin(fuse_angle) * 3)
        pygame.draw.line(surface, (200, 180, 100), (px, py - 1), (fx, fy), 1)
