from __future__ import annotations

import math
import random
from typing import Any

import pygame
from pyglm import glm


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

    def draw(self, surface: pygame.Surface, mpos: glm.vec2) -> None:
        vec = glm.normalize(mpos - self.pos)
        # draw the particles
        self.emitter.draw(surface)

        # draw the "gun"
        pygame.draw.line(
            surface, (0, 200, 200), self.pos + vec * 4, self.pos + vec * 10, 1
        )
        # draw the player
        pygame.draw.circle(surface, (0, 200, 0), self.pos, 2)


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

    def draw(self, surface: pygame.Surface) -> None:
        surf = self._cached_surf
        surface.blit(surf, self.pos - glm.vec2(surf.get_size()) / 2)


class Shell:
    __slots__ = [
        "pos",
        "vel",
        "speed",
        "_speed",
        "life",
        "rot_speed",
        "_cached_surf",
        "_cached_angle",
        "_cached_scale",
    ]

    _base_surf: pygame.Surface | None = None

    @classmethod
    def _get_base_surf(cls) -> pygame.Surface:
        if cls._base_surf is None:
            cls._base_surf = pygame.Surface((4, 2))
            pygame.draw.rect(cls._base_surf, (200, 200, 0), (0, 0, 1, 2))
            pygame.draw.rect(cls._base_surf, (200, 0, 0), (1, 0, 3, 2))
        return cls._base_surf

    def __init__(self, pos: glm.vec2, vel: glm.vec2) -> None:
        self.pos: glm.vec2 = glm.vec2(pos)
        self.vel: glm.vec2 = glm.vec2(vel)
        self.speed: float = random.randint(20, 40)
        self._speed: int = int(self.speed)
        self.life: float = 5
        self.rot_speed: float = random.random()
        self._cached_angle: float = -1.0
        self._cached_scale: float = -1.0
        self._cached_surf: pygame.Surface = self._get_base_surf()

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(self.pos - glm.vec2(1), (2, 2))

    def update(self, dt: float) -> None:
        self.pos += self.vel * self.speed * dt
        self.life -= dt
        self.speed *= 1 - dt * 1.8
        if self.vel:
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
                    self._get_base_surf(), -angle, max(scale, 0.1)
                )

    def draw(self, surface: pygame.Surface) -> None:
        surf = self._cached_surf
        surface.blit(surf, self.pos - glm.vec2(surf.get_size()) / 2)


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
        self, pos: glm.vec2, vec: glm.vec2, color: tuple[int, int, int]
    ) -> None:
        self.pos: glm.vec2 = glm.vec2(pos)
        self.normal: glm.vec2 = glm.normalize(-glm.vec2(vec))
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

    def draw(self, surface: pygame.Surface) -> None:
        self.particle_emitter.draw(surface)
        surf = self._cached_surf_active if self._active else self._cached_surf_inactive
        surface.blit(surf, self.pos - glm.vec2(surf.get_size()) / 2)


class Camera:
    __slots__ = ["pos", "offset", "target"]

    def __init__(
        self,
        pos: glm.vec2,
        target: Player | None = None,
        offset: glm.vec2 | None = None,
    ) -> None:
        self.pos: glm.vec2 = glm.vec2(pos)
        self.target: Player | None = target
        self.offset: glm.vec2 = glm.vec2(offset) if offset else glm.vec2()

    def update(self) -> None:
        if not self.target:
            return
        if hasattr(self.target, "vel") and hasattr(self.target, "speed"):
            self.pos = (
                glm.lerp(
                    self.pos,
                    self.target.pos + (self.target.vel * self.target.speed),
                    0.1,
                )
                + self.offset
            )
        else:
            self.pos = glm.lerp(self.pos, self.target.pos, 0.1) + self.offset


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
