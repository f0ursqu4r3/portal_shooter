import random

import pygame
from pygame import Vector2

from .sound import SoundPlayer

from .entities import Bullet
from .entities import Player
from .entities import Portal
from .entities import Shell
from .util import intersect
from .util import point_dist_to_line
from .util import get_collisions
from .util import remap

import cProfile
import pstats

pygame.init()


class Game:
    def __init__(self):
        self.window_size = Vector2(720)
        self.window = pygame.display.set_mode(
            self.window_size, pygame.DOUBLEBUF)
        pygame.display.set_caption('playground')

        self.screen_scale = 3
        self.screen = pygame.Surface(self.window_size/self.screen_scale)
        self.screen_size = Vector2(self.screen.get_size())
        self.running = True

        self.sound_payer = SoundPlayer('./assets/sounds', 'wav')

        self.clock = pygame.time.Clock()
        self.mpos = Vector2(pygame.mouse.get_pos()) / self.screen_scale

        self.player = Player(self.screen_size / 2, Vector2())
        self.player_walk_timer = 0

        self.entities = []

        self.portals = [None, None]

        self.time_scale = 1
        self.shot_timer = 0
        self.fire_rate = 1/40

        self.screen_shake = Vector2()

    def run(self):
        with cProfile.Profile() as p:
            while self.running:
                self.process_events()
                self.update()
                self.draw()

        stats = pstats.Stats(p)
        stats.sort_stats(pstats.SortKey.TIME)
        stats.dump_stats('profile.prof')

    def process_events(self):
        mpos = Vector2(pygame.mouse.get_pos()) / self.screen_scale

        self.process_pygame_events()

        self.player.vel = Vector2()
        pressed = pygame.key.get_pressed()
        if pressed[pygame.K_w]:
            self.player.vel.y -= self.player.speed
        if pressed[pygame.K_s]:
            self.player.vel.y += self.player.speed
        if pressed[pygame.K_a]:
            self.player.vel.x -= self.player.speed
        if pressed[pygame.K_d]:
            self.player.vel.x += self.player.speed
        if any([
            pressed[pygame.K_w],
            pressed[pygame.K_s],
            pressed[pygame.K_a],
            pressed[pygame.K_d]
        ]) and self.player_walk_timer >= .1:
            self.sound_payer.play('Step1', volume=.2)
            self.player_walk_timer = 0

        if pygame.mouse.get_pressed()[0] and not self.shot_timer:
            fire_vec = (mpos - self.player.pos).normalize()
            self.entities.append(
                Bullet(self.player.pos + fire_vec * 15, fire_vec))

            eject_vec = Vector2(-fire_vec.y, fire_vec.x)
            self.entities.append(
                Shell(self.player.pos + (fire_vec * 4) + (eject_vec * 4), eject_vec))

            shake = fire_vec * -(random.random() * 4 + 4)
            self.player.vel = shake * 10
            self.sound_payer.play('Shoot1')

            self.screen_shake = shake

            self.shot_timer = self.fire_rate
            self.time_scale = 0.2

    def process_pygame_events(self):
        mpos = Vector2(pygame.mouse.get_pos()) / self.screen_scale
        for event in pygame.event.get():
            if (event.type == pygame.QUIT or
                (event.type == pygame.KEYDOWN and
                 event.key == pygame.K_ESCAPE)):
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    self.portals[0] = Portal(
                        mpos, (mpos - self.player.pos), (255, 127, 0))
                elif event.key == pygame.K_e:
                    self.portals[1] = Portal(
                        mpos, (mpos - self.player.pos), (41, 174, 255))
                elif event.key == pygame.K_z:
                    self.portals[0] = None
                elif event.key == pygame.K_x:
                    self.portals[1] = None

                elif event.key == pygame.K_SPACE:
                    print(f'{self.player.health=} {self.clock.get_fps()=}')

            elif event.type == pygame.MOUSEWHEEL:
                self.screen_scale = min(
                    6, max(self.screen_scale + event.y * .05, 1))
                self.screen = pygame.Surface(
                    self.window_size/self.screen_scale)
                self.screen_size = Vector2(self.screen.get_size())

    def update(self):
        tdt = self.clock.tick() * 0.001

        if self.player.health > 0:
            self.time_scale = min(1, self.time_scale + tdt * 2)

        self.screen_shake = self.screen_shake * 0.9

        dt = tdt * self.time_scale
        self.shot_timer = max(0, self.shot_timer - dt)

        self.mpos = Vector2(pygame.mouse.get_pos()) / self.screen_scale

        self.player_walk_timer += dt

        self.player.update(dt)

        if self.player.pos.x < 0:
            self.player.pos.x = 0
        elif self.player.pos.x > self.screen_size.x:
            self.player.pos.x = self.screen_size.x

        if self.player.pos.y < 0:
            self.player.pos.y = 0
        elif self.player.pos.y > self.screen_size.y:
            self.player.pos.y = self.screen_size.y

        self.do_portal(self.player)
        self.player.update(dt)

        for entity in self.entities[:]:
            entity.update(dt)

            if entity.life < 0:
                self.entities.remove(entity)
                continue

            if not (0 < entity.pos.x < self.screen_size.x):
                entity.pos.x = 0 if entity.pos.x < 0 else self.screen_size.x
                entity.vel.x *= -1
                volume = remap(
                    self.player.pos.distance_to(entity.pos),
                    200, 0, 0, 1
                )
                if volume:
                    self.sound_payer.play('Ricochet1', volume=volume)
            if not (0 < entity.pos.y < self.screen_size.y):
                entity.pos.y = 0 if entity.pos.y < 0 else self.screen_size.y
                entity.vel.y *= -1
                volume = remap(
                    self.player.pos.distance_to(entity.pos),
                    200, 0, 0, 1
                )
                if volume:
                    self.sound_payer.play('Ricochet1', volume=volume)

            self.do_portal(entity)

        for collision in get_collisions(self.player, [e for e in self.entities if isinstance(e, Bullet)]):
            self.player.health -= 10
            self.entities.remove(collision)
            if self.player.health > 0:
                vel = Vector2(-entity.vel.y, entity.vel.x)
                self.player.emitter.vel = vel
                self.player.emitter.burst()
                self.sound_payer.play('Hurt1')
            else:
                self.player.emitter.vel = None
                self.player.emitter.burst(50)
                self.time_scale = 0.05
        for portal in self.portals:
            if portal:
                portal.update(dt)
                portal.active = all(self.portals)

    def do_portal(self, entity):
        if not (all(self.portals) and entity.vel):
            return
        for i, portal in enumerate(self.portals):
            intersects = intersect(
                entity.pos, entity.pos + entity.vel.normalize() * 10, *portal.line)
            dist = point_dist_to_line(entity.pos, portal.line)
            if intersects and dist <= 3:
                dest = self.portals[(i+1) % 2]
                entity.pos = dest.exit
                entity.vel = (entity.vel + portal.normal +
                              dest.normal).normalize()
                portal.burst()
                dest.burst()
                volume = remap(
                    self.player.pos.distance_to(entity.pos),
                    200, 0, 0, 1
                )
                self.sound_payer.play('Portal1', volume=volume)

    def draw(self):
        self.screen.fill((60, 50, 60))
        layer = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)

        [entity.draw(layer) for entity in self.entities]

        self.player.draw(layer, self.mpos)

        [portal.draw(layer) for portal in self.portals if portal]

        self.screen.blit(layer, self.screen_shake)
        pygame.transform.scale(self.screen, self.window_size, self.window)
        pygame.display.flip()
