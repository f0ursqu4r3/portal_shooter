from __future__ import annotations

import pygame
from pyglm import glm

from portal_shooter.entities.entity import Entity
from portal_shooter.particles import FadeOutParticle, ParticleEmitter


DASH_SPEED = 200
DASH_DURATION = 0.12
DASH_COOLDOWN = 0.6


class Player(Entity):
    __slots__ = [
        "speed",
        "max_health",
        "health",
        "armor",
        "max_armor",
        "emitter",
        "aim_target",
        "is_dashing",
        "dash_timer",
        "dash_cooldown",
        "dash_direction",
        "invincible",
    ]

    def __init__(self, pos: glm.vec2, vel: glm.vec2) -> None:
        super().__init__(pos, vel)
        self.speed: int = 50
        self.max_health: int = 100
        self.health: int = 100
        self.armor: int = 0
        self.max_armor: int = 50
        self.aim_target: glm.vec2 = glm.vec2()

        self.is_dashing: bool = False
        self.dash_timer: float = 0.0
        self.dash_cooldown: float = 0.0
        self.dash_direction: glm.vec2 = glm.vec2()
        self.invincible: bool = False

        self.emitter: ParticleEmitter = ParticleEmitter(
            pos=self.pos,
            vel=glm.vec2(),
            spawn_rate=0,
            shape=ParticleEmitter.Point(30),
            particle_class=FadeOutParticle,
            particle_kwargs={"color": (200, 0, 0)},
        )

    def start_dash(self) -> bool:
        if self.dash_cooldown > 0 or self.is_dashing:
            return False
        if glm.length(self.vel) < 1:
            return False
        self.is_dashing = True
        self.dash_timer = DASH_DURATION
        self.dash_direction = glm.normalize(self.vel)
        self.invincible = True
        return True

    def update(self, dt: float) -> None:
        self.dash_cooldown = max(0.0, self.dash_cooldown - dt)

        if self.is_dashing:
            self.dash_timer -= dt
            self.pos += self.dash_direction * DASH_SPEED * dt
            if self.dash_timer <= 0:
                self.is_dashing = False
                self.invincible = False
                self.dash_cooldown = DASH_COOLDOWN
        else:
            self.pos += self.vel * dt
            self.invincible = False

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
        pygame.draw.line(surface, (0, 200, 200), p + vec * 4, p + vec * 10, 1)
        # draw the player
        pygame.draw.circle(surface, (0, 200, 0), p, 2)
