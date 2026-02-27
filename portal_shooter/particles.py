from __future__ import annotations

import math
import random
from typing import Any

import pygame
from pyglm import glm


class Particle:
    __slots__ = ["pos", "vel", "age", "lifetime", "color", "speed"]

    def __init__(self, pos: glm.vec2, vel: glm.vec2) -> None:
        self.pos: glm.vec2 = glm.vec2(pos)
        self.vel: glm.vec2 = glm.vec2(vel)
        self.age: float = 0
        self.lifetime: float = 3
        self.color: list[int] = [0, 200, 0, 255]
        self.speed: int = random.randint(5, 10)

    @property
    def alive(self) -> bool:
        return self.age < self.lifetime

    def update(self, dt: float) -> None:
        self.pos += self.vel * self.speed * dt
        self.age += dt

    def draw(self, surface: pygame.Surface) -> None:
        surface.set_at([*map(int, self.pos)], self.color)


class FadeOutParticle(Particle):
    def __init__(
        self, pos: glm.vec2, vel: glm.vec2, color: tuple[int, int, int]
    ) -> None:
        super().__init__(pos, vel)
        self.color: list[int] = list(color)
        self.lifetime = 0.5
        self.speed = random.randint(1, 3)
        self.surf: pygame.Surface = pygame.Surface((1, 1))
        self.surf.fill(self.color)

    def update(self, dt: float) -> None:
        super().update(dt)
        self.surf.set_alpha(int(max(0, (1 - (self.age / self.lifetime)) * 255)))

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self.surf, self.pos)


class ParticleEmitter:
    __slots__ = [
        "pos",
        "vel",
        "speed",
        "particles",
        "age",
        "spawn_rate",
        "last_spawn",
        "shape",
        "particle_class",
        "particle_kwargs",
        "active",
        "deactivate_after_burst",
        "debug",
    ]

    class Shape:
        pass

    class Point(Shape):
        def __init__(self, spread: float = 0) -> None:
            self.spread: float = spread

    class Line(Shape):
        def __init__(self, vec: glm.vec2) -> None:
            self.vec: glm.vec2 = glm.vec2(vec)

    class Circle(Shape):
        def __init__(self, radius: float) -> None:
            self.radius: float = radius

    class Rectangle(Shape):
        def __init__(self, size: glm.vec2) -> None:
            self.size: glm.vec2 = glm.vec2(size)

    def __init__(
        self,
        pos: glm.vec2,
        vel: glm.vec2 | None = None,
        speed: float | None = None,
        spawn_rate: float | None = None,
        shape: Shape | None = None,
        particle_class: type[Particle] | None = None,
        particle_kwargs: dict[str, Any] | None = None,
        debug: bool = False,
    ) -> None:
        self.pos: glm.vec2 = glm.vec2(pos)
        self.vel: glm.vec2 | None = glm.normalize(glm.vec2(vel)) if vel else None
        self.speed: float | None = speed
        self.spawn_rate: float = spawn_rate if spawn_rate is not None else 10
        self.last_spawn: float = 0
        self.shape: ParticleEmitter.Shape = (
            shape
            if shape is not None and isinstance(shape, self.Shape)
            else self.Point()
        )
        self.particle_class: type[Particle] = particle_class or Particle
        self.particle_kwargs: dict[str, Any] = particle_kwargs or {}
        self.active: bool = True
        self.deactivate_after_burst: bool = False
        self.debug: bool = debug
        self.particles: list[Particle] = []
        self.age: float = 0

    def update(self, dt: float) -> None:
        self.last_spawn += dt

        spawn_rate = (1 / self.spawn_rate) if self.spawn_rate > 0 else 0
        if spawn_rate and self.last_spawn >= spawn_rate:
            for _ in range(max(1, int(dt / spawn_rate))):
                self.create_particle()
            self.last_spawn = 0

        for particle in self.particles:
            particle.update(dt)
        self.particles = [p for p in self.particles if p.alive]

        if self.deactivate_after_burst and not self.particles:
            self.active = False

        self.age += dt

    def create_particle(self) -> None:
        vel = self.vel
        if not vel:
            vel = glm.normalize(glm.vec2(random.random() - 0.5, random.random() - 0.5))
        speed = self.speed or random.randint(5, 10)

        pos = self.pos

        if isinstance(self.shape, self.Point):
            # alter the velocity angle +/- point spread
            vel = glm.vec2(
                glm.rotate(
                    vel,
                    math.radians(random.uniform(-self.shape.spread, self.shape.spread)),
                )
            )

        if isinstance(self.shape, self.Line):
            length = glm.length(self.shape.vec)
            particle_pos = glm.normalize(self.shape.vec) * (random.random() * length)
            half = self.shape.vec / 2
            pos = pos - half + particle_pos

        elif isinstance(self.shape, self.Circle):
            pos = (
                pos
                + glm.normalize(glm.vec2(random.random() - 0.5, random.random() - 0.5))
                * random.random()
                * self.shape.radius
            )

        elif isinstance(self.shape, self.Rectangle):
            center = self.shape.size / 2
            point = glm.vec2(
                random.random() * self.shape.size.x, random.random() * self.shape.size.y
            )
            pos = pos - center + point

        self.particles.append(
            self.particle_class(pos, glm.vec2(vel * speed), **self.particle_kwargs)
        )

    def burst(
        self, count: int | list[int] | None = None, deactivate_after: bool = False
    ) -> None:
        if isinstance(count, list):
            iterations = range(*count) if len(count) == 2 else range(count[0])
        elif count is None:
            iterations = range(random.randint(5, 10))
        else:
            iterations = range(count)
        for _ in iterations:
            self.create_particle()
            self.deactivate_after_burst = deactivate_after

    def draw(self, surface: pygame.Surface) -> None:
        if self.debug:
            c = (0, 200, 200)
            if isinstance(self.shape, self.Point):
                surface.set_at([*map(int, self.pos)], c)
            elif isinstance(self.shape, self.Line):
                half = self.shape.vec / 2
                start = self.pos - half
                end = self.pos + half
                pygame.draw.line(surface, c, start, end)
            elif isinstance(self.shape, self.Circle):
                pygame.draw.circle(surface, c, self.pos, self.shape.radius, 1)
            elif isinstance(self.shape, self.Rectangle):
                center = self.shape.size / 2
                pygame.draw.rect(surface, c, (self.pos - center, self.shape.size), 1)

        for particle in self.particles:
            particle.draw(surface)
