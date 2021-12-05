import math
import random

import pygame
from pygame import Vector2


class Player:
    __slots__ = [
        'pos', 'vel', 'speed',
        'max_health', 'health',
        'emitter'
    ]

    def __init__(self, pos, vel):
        self.pos = Vector2(pos)
        self.vel = Vector2(vel)
        self.speed = 50
        self.max_health = 100
        self.health = 100

        self.emitter = ParticleEmitter(
            self.pos,
            Vector2(),
            self.vel,
            spawn_rate=0,
            shape=ParticleEmitter.Point(30),
            particle_class=FadeOutParticle,
            particle_kwargs={'color': (200, 0, 0)},
        )

    def update(self, dt):
        self.pos += self.vel * dt
        self.emitter.pos = self.pos
        self.emitter.update(dt)

    @property
    def rect(self):
        return pygame.Rect(self.pos-Vector2(2), (4, 4))

    def draw(self, surface, mpos):
        vec = (mpos - self.pos).normalize()
        # draw the particles
        self.emitter.draw(surface)

        # draw the "gun"
        pygame.draw.line(surface, (0, 200, 200), self.pos +
                         vec * 4, self.pos + vec * 10, 1)
        # draw the player
        pygame.draw.circle(surface, (0, 200, 0), self.pos, 2)


class Bullet:
    __slots__ = [
        'pos', 'vel', 'speed', '_speed',
        '_surf', 'life'
    ]

    def __init__(self, pos, vel):
        self.pos = Vector2(pos)
        self.vel = Vector2(vel)
        self.speed = 100
        self._speed = 100
        self.life = 5
        surf = pygame.Surface(Vector2(4, 2))
        pygame.draw.rect(surf, (100, 100, 100), (0, 0, 4, 2))
        self._surf = surf

    @property
    def rect(self):
        return pygame.Rect(self.pos-Vector2(1), (2, 2))

    @property
    def surf(self):
        if not self.vel:
            return self._surf
        vel = self.vel.normalize()
        degrees = math.degrees(math.atan2(vel.y, vel.x))
        angle = (360 + degrees) % 360
        return pygame.transform.rotozoom(self._surf, -angle, self.life / 5)

    def update(self, dt):
        self.pos += self.vel * self.speed * dt
        self.life -= dt

    def draw(self, surface):
        surface.blit(self.surf, self.pos - Vector2(self.surf.get_size())/2)


class Shell:
    __slots__ = [
        'pos', 'vel', 'speed', '_speed',
        '_surf', 'life', 'rot_speed'
    ]

    def __init__(self, pos, vel):
        self.pos = Vector2(pos)
        self.vel = Vector2(vel)
        self.speed = random.randint(20, 40)
        self._speed = int(self.speed)
        self.life = 5
        self.rot_speed = random.random()
        surf = pygame.Surface(Vector2(4, 2))
        pygame.draw.rect(surf, (200, 200, 0), (0, 0, 1, 2))
        pygame.draw.rect(surf, (200, 0, 0), (1, 0, 3, 2))
        self._surf = surf

    @property
    def rect(self):
        return pygame.Rect(self.pos-Vector2(1), (2, 2))

    @property
    def surf(self):
        if not self.vel:
            return self._surf
        vel = self.vel.normalize()
        degrees = math.degrees(math.atan2(vel.y, vel.x))
        angle = (360 + degrees - 90 -
                 (360 * ((self.speed/self._speed)*self.rot_speed))) % 360
        return pygame.transform.rotozoom(self._surf, -angle, self.life / 5)

    def update(self, dt):
        self.pos += self.vel * self.speed * dt
        self.life -= dt
        self.speed *= 1 - dt * 1.8

    def draw(self, surface):
        surface.blit(self.surf, self.pos - Vector2(self.surf.get_size())/2)


class Portal:
    __slots__ = [
        'pos', 'normal', 'width', '_surf',
        'color', 'particle_emitter', 'active',
        'deactivate_when_empty'
    ]

    def __init__(self, pos, vec, color):
        self.pos = Vector2(pos)
        self.normal = Vector2(-vec).normalize()
        self.width = 12
        self._surf = pygame.Surface(Vector2(self.width, 1))
        self.color = list(color)
        self._surf.fill(self.color)

        self.active = False
        self.deactivate_when_empty = False
        self.particle_emitter = ParticleEmitter(
            pos=self.pos,
            vel=self.normal,
            spawn_rate=10,
            shape=ParticleEmitter.Line(self.perp * (self.width-4)),
            particle_class=FadeOutParticle,
            particle_kwargs={'color': self.color}
        )

    @property
    def perp(self):
        return Vector2(-self.normal.y, self.normal.x).normalize()

    @property
    def exit(self):
        return self.pos + self.normal * 2

    @property
    def line(self):
        start = self.pos - self.perp * self.width / 2
        end = self.pos + self.perp * self.width / 2
        return (start, end)

    def burst(self):
        self.particle_emitter.burst()

    def update(self, dt):
        if self.active:
            self.particle_emitter.update(dt)

    @property
    def surf(self):
        degrees = math.degrees(math.atan2(self.perp.y, self.perp.x))
        angle = (360 + degrees) % 360
        surf = pygame.transform.rotate(self._surf, -angle)
        surf.set_alpha(100 if not self.active else 200)
        return surf

    def draw(self, surface):
        self.particle_emitter.draw(surface)
        surface.blit(self.surf, self.pos - Vector2(self.surf.get_size())/2)


class Camera:
    __slots__ = ['pos', 'offset', 'target']

    def __init__(self, pos, target=None, offset=None):
        self.pos = Vector2(pos)
        self.target = target
        self.offset = Vector2(offset) if offset else Vector2()

    def update(self):
        if not self.target:
            return
        if hasattr(self.target, 'vel') and hasattr(self.target, 'speed'):
            self.pos = self.pos.lerp(
                self.target.pos + (self.target.vel * self.target.speed), .1) + self.offset
        else:
            self.pos = self.pos.lerp(self.target.pos, .1) + self.offset


class ParticleEmitter:
    __slots__ = [
        'pos', 'vel', 'speed',
        'particles', 'age', 'spawn_rate',
        'last_spawn', 'shape', 'particle_class',
        'particle_kwargs', 'active',
        'deactivate_after_burst', 'debug'
    ]

    class Shape:
        pass

    class Point(Shape):
        def __init__(self, spread=0):
            self.spread = spread

    class Line(Shape):
        def __init__(self, vec):
            self.vec = Vector2(vec)

    class Circle(Shape):
        def __init__(self, radius):
            self.radius = radius

    class Rectangle(Shape):
        def __init__(self, size):
            self.size = Vector2(size)

    def __init__(self, pos, vel=None, speed=None,
                 spawn_rate=None, shape=None,
                 particle_class=None, particle_kwargs=None,
                 debug=False):
        self.pos = Vector2(pos)
        self.vel = Vector2(vel).normalize() if vel else None
        self.speed = speed
        self.spawn_rate = spawn_rate if spawn_rate is not None else 10
        self.last_spawn = 0
        self.shape = shape if shape is not None and isinstance(
            shape, self.Shape) else self.Point()
        self.particle_class = particle_class or Particle
        self.particle_kwargs = particle_kwargs or {}
        self.active = True
        self.deactivate_after_burst = False
        self.debug = debug
        self.particles = []
        self.age = 0

    def update(self, dt):
        self.last_spawn += dt

        spawn_rate = (1/self.spawn_rate) if self.spawn_rate > 0 else 0
        if spawn_rate and self.last_spawn >= spawn_rate:
            for _ in range(max(1, int(dt/spawn_rate))):
                self.create_particle()
            self.last_spawn = 0

        for particle in self.particles[:]:
            particle.update(dt)
            if not particle.alive:
                self.particles.remove(particle)

        if self.deactivate_after_burst and not self.particles:
            self.active = False

        self.age += dt

    def create_particle(self):
        vel = self.vel
        if not vel:
            vel = Vector2(
                random.random() - .5,
                random.random() - .5
            ).normalize()
        speed = self.speed or random.randint(5, 10)

        pos = self.pos

        if isinstance(self.shape, self.Point):
            # alter the velocity angle +/- point spread
            vel = vel.rotate(
                random.uniform(-self.shape.spread, self.shape.spread))

        if isinstance(self.shape, self.Line):
            length = self.shape.vec.length()
            particle_pos = self.shape.vec.normalize() * (random.random() * length)
            half = self.shape.vec / 2
            pos = pos - half + particle_pos

        elif isinstance(self.shape, self.Circle):
            pos = pos + Vector2(
                random.random() - .5,
                random.random() - .5
            ).normalize() * random.random() * self.shape.radius

        elif isinstance(self.shape, self.Rectangle):
            center = self.shape.size/2
            point = Vector2(
                random.random() * self.shape.size.x,
                random.random() * self.shape.size.y
            )
            pos = pos - center + point

        self.particles.append(
            self.particle_class(pos, vel * speed, **self.particle_kwargs)
        )

    def burst(self, count=None, deactivate_after=False):
        if isinstance(count, list):
            count = range(*count) if len(count) == 2 else count[0]
        else:
            count = range(random.randint(5, 10)
                          ) if count is None else range(count)
        for _ in count:
            self.create_particle()
            self.deactivate_after_burst = deactivate_after

    def draw(self, surface):

        if self.debug:
            c = (0, 200, 200)
            if isinstance(self.shape, self.Point):
                surface.set_at([*map(int, self.pos)], c)
            elif isinstance(self.shape, self.Line):
                half = self.shape.vec/2
                start = self.pos - half
                end = self.pos + half
                pygame.draw.line(surface, c, start, end)
            elif isinstance(self.shape, self.Circle):
                pygame.draw.circle(surface, c, self.pos, self.shape.radius, 1)
            elif isinstance(self.shape, self.Rectangle):
                center = self.shape.size/2
                pygame.draw.rect(
                    surface, c, (self.pos - center, self.shape.size), 1)

        for particle in self.particles:
            particle.draw(surface)


class Particle:
    __slots__ = [
        'pos', 'vel', 'age',
        'lifetime', 'color', 'speed'
    ]

    def __init__(self, pos, vel):
        self.pos = Vector2(pos)
        self.vel = Vector2(vel)
        self.age = 0
        self.lifetime = 3
        self.color = [0, 200, 0, 255]
        self.speed = random.randint(5, 10)

    @property
    def alive(self):
        return self.age < self.lifetime

    def update(self, dt):
        self.pos += self.vel * self.speed * dt
        self.age += dt

    def draw(self, surface):
        surface.set_at([*map(int, self.pos)], self.color)


class FadeOutParticle(Particle):
    def __init__(self, pos, vel, color):
        super().__init__(pos, vel)
        self.color = color
        self.lifetime = .5
        self.speed = random.randint(1, 3)
        self.surf = pygame.Surface((1, 1))
        self.surf.fill(self.color)

    def update(self, dt):
        super().update(dt)
        self.surf.set_alpha(max(0, (1 - (self.age / self.lifetime)) * 255))

    def draw(self, surface):
        surface.blit(self.surf, self.pos)
