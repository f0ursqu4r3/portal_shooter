from __future__ import annotations

import cProfile
import pstats
import random

import pygame
from pyglm import glm

from portal_shooter.entities import Bullet, Camera, Pickup, PickupKind, Player, Portal, Shell
from portal_shooter.hud import HUD
from portal_shooter.map import GameMap, compute_visibility
from portal_shooter.sound import SoundPlayer
from portal_shooter.util import get_collisions, intersect, point_dist_to_line, remap

pygame.init()


class Game:
    def __init__(self) -> None:
        self.window_size: glm.vec2 = glm.vec2(720)
        self.window: pygame.Surface = pygame.display.set_mode(
            self.window_size, pygame.DOUBLEBUF
        )
        pygame.display.set_caption("playground")
        pygame.mouse.set_visible(False)

        self.screen_scale: float = 3
        self.screen: pygame.Surface = pygame.Surface(
            self.window_size / self.screen_scale
        )
        self.screen_size: glm.vec2 = glm.vec2(self.screen.get_size())
        self.running: bool = True

        self.sound_payer: SoundPlayer = SoundPlayer("./assets/sounds", "wav")

        self.clock: pygame.time.Clock = pygame.time.Clock()
        self.mpos: glm.vec2 = glm.vec2(pygame.mouse.get_pos()) / self.screen_scale

        self.game_map: GameMap = GameMap()
        self.player: Player = Player(self.game_map.spawn_pos, glm.vec2())
        self.camera: Camera = Camera(
            self.player.pos,
            target=self.player,
            map_bounds=self.game_map.bounds,
        )
        self.player_walk_timer: float = 0
        self.mpos_world: glm.vec2 = glm.vec2()

        self.entities: list[Bullet | Shell] = []
        self.bullets: list[Bullet] = []

        self.portals: list[Portal | None] = [None, None]

        self.pickups: list[Pickup] = [
            Pickup(pos, PickupKind(kind))
            for pos, kind in self.game_map.pickup_positions
        ]

        self.time_scale: float = 1
        self.shot_timer: float = 0
        self.fire_rate: float = 1 / 40
        self.speed_buff_timer: float = 0

        self.hud: HUD = HUD()

        self.layer: pygame.Surface = pygame.Surface(
            self.screen.get_size(), pygame.SRCALPHA
        )
        self.fog: pygame.Surface = pygame.Surface(
            self.screen.get_size(), pygame.SRCALPHA
        )
        self._layer_size: tuple[int, int] = self.screen.get_size()

    def run(self) -> None:
        with cProfile.Profile() as p:
            while self.running:
                self.process_events()
                self.update()
                self.draw()

        stats = pstats.Stats(p)
        stats.sort_stats(pstats.SortKey.TIME)
        stats.dump_stats("profile.prof")

    def process_events(self) -> None:
        self.mpos = glm.vec2(pygame.mouse.get_pos()) / self.screen_scale
        cam_offset = self.camera.pos - self.screen_size / 2
        self.mpos_world = self.mpos + cam_offset

        self.process_pygame_events()

        self.player.vel = glm.vec2()
        pressed = pygame.key.get_pressed()
        if pressed[pygame.K_w]:
            self.player.vel.y -= self.player.speed
        if pressed[pygame.K_s]:
            self.player.vel.y += self.player.speed
        if pressed[pygame.K_a]:
            self.player.vel.x -= self.player.speed
        if pressed[pygame.K_d]:
            self.player.vel.x += self.player.speed
        if (
            any(
                [
                    pressed[pygame.K_w],
                    pressed[pygame.K_s],
                    pressed[pygame.K_a],
                    pressed[pygame.K_d],
                ]
            )
            and self.player_walk_timer >= 0.1
        ):
            self.sound_payer.play("Step1", volume=0.2)
            self.player_walk_timer = 0

        if pygame.mouse.get_pressed()[0] and not self.shot_timer:
            fire_vec = glm.normalize(self.mpos_world - self.player.pos)
            bullet = Bullet(self.player.pos + fire_vec * 15, fire_vec)
            self.entities.append(bullet)
            self.bullets.append(bullet)

            eject_vec = glm.vec2(-fire_vec.y, fire_vec.x)
            self.entities.append(
                Shell(self.player.pos + (fire_vec * 4) + (eject_vec * 4), eject_vec)
            )

            shake = fire_vec * -(random.random() * 1.5 + 1.5)
            self.player.vel = shake * 10
            self.sound_payer.play("Shoot1")

            self.camera.shake = glm.vec2(shake)

            rate = self.fire_rate / 2 if self.speed_buff_timer > 0 else self.fire_rate
            self.shot_timer = rate
            self.time_scale = 0.2

    def process_pygame_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (
                event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
            ):
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_q, pygame.K_e):
                    aim_dir = self.mpos_world - self.player.pos
                    hit = self.game_map.find_nearest_wall_hit(
                        self.player.pos, aim_dir
                    )
                    if hit:
                        idx = 0 if event.key == pygame.K_q else 1
                        color = (255, 127, 0) if idx == 0 else (41, 174, 255)
                        self.portals[idx] = Portal(
                            hit[0] + hit[1] * 2, hit[1], color
                        )
                elif event.key == pygame.K_z:
                    self.portals[0] = None
                elif event.key == pygame.K_x:
                    self.portals[1] = None

                elif event.key == pygame.K_SPACE:
                    print(f"{self.player.health=} {self.clock.get_fps()=}")

            elif event.type == pygame.MOUSEWHEEL:
                self.screen_scale = min(6, max(self.screen_scale + event.y * 0.05, 1))
                self.screen = pygame.Surface(self.window_size / self.screen_scale)
                self.screen_size = glm.vec2(self.screen.get_size())
                self.layer = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
                self.fog = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
                self._layer_size = self.screen.get_size()

    def update(self) -> None:
        tdt = min(self.clock.tick() * 0.001, 0.05)

        if self.player.health > 0:
            self.time_scale = min(1, self.time_scale + tdt * 2)

        dt = tdt * self.time_scale
        self.shot_timer = max(0, self.shot_timer - dt)

        self.player_walk_timer += dt

        old_pos = glm.vec2(self.player.pos)
        self.player.update(dt)
        self.game_map.collide_player(self.player, old_pos)
        self.camera.update(dt, self.screen_size)

        self.do_portal(self.player)

        dead: set[Bullet | Shell] = set()
        for entity in self.entities:
            old_pos = glm.vec2(entity.pos)
            entity.update(dt)

            if entity.life < 0:
                dead.add(entity)
                continue

            if self.game_map.collide_entity(entity, old_pos):
                volume = remap(glm.distance(self.player.pos, entity.pos), 200, 0, 0, 1)
                if volume:
                    self.sound_payer.play("Ricochet1", volume=volume)

            self.do_portal(entity)

        for collision in get_collisions(self.player, self.bullets):
            self.player.health -= 10
            dead.add(collision)
            if self.player.health > 0:
                vel = glm.vec2(-collision.vel.y, collision.vel.x)
                self.player.emitter.vel = vel
                self.player.emitter.burst()
                self.sound_payer.play("Hurt1")
            else:
                self.player.emitter.vel = None
                self.player.emitter.burst(50)
                self.time_scale = 0.05

        if dead:
            self.entities = [e for e in self.entities if e not in dead]
            self.bullets = [b for b in self.bullets if b not in dead]

        for portal in self.portals:
            if portal:
                portal.update(dt)
                portal.active = all(self.portals)

        collected: list[Pickup] = []
        for pickup in self.pickups:
            pickup.update(dt)
            if self.player.rect.colliderect(pickup.rect):
                if pickup.kind == PickupKind.HEALTH:
                    self.player.health = min(
                        self.player.health + 25, self.player.max_health
                    )
                else:
                    self.speed_buff_timer = 5.0
                self.sound_payer.play("Portal1", volume=0.5)
                collected.append(pickup)
        if collected:
            self.pickups = [p for p in self.pickups if p not in collected]

        if self.speed_buff_timer > 0:
            self.speed_buff_timer = max(0, self.speed_buff_timer - dt)

    def do_portal(self, entity: Player | Bullet | Shell) -> None:
        if not (all(self.portals) and entity.vel):
            return
        for i, portal in enumerate(self.portals):
            assert portal is not None
            intersects = intersect(
                entity.pos, entity.pos + glm.normalize(entity.vel) * 10, *portal.line
            )
            dist = point_dist_to_line(entity.pos, portal.line)
            if intersects and dist <= 3:
                dest = self.portals[(i + 1) % 2]
                assert dest is not None
                entity.pos = glm.vec2(dest.exit)
                # Decompose velocity into entry portal's local frame,
                # then reconstruct in destination portal's frame
                into = glm.dot(entity.vel, -portal.normal)
                lateral = glm.dot(entity.vel, portal.perp)
                entity.vel = dest.normal * into + dest.perp * lateral
                portal.burst()
                dest.burst()
                volume = remap(glm.distance(self.player.pos, entity.pos), 200, 0, 0, 1)
                self.sound_payer.play("Portal1", volume=volume)

    def draw(self) -> None:
        cam_offset = self.camera.pos + self.camera.shake - self.screen_size / 2
        self.screen.fill((10, 8, 12))
        self.game_map.draw(self.screen, cam_offset)

        # Compute visibility polygon
        cox, coy = cam_offset.x, cam_offset.y
        assert self.game_map._wall_grid is not None
        vis_points = compute_visibility(
            self.player.pos, self.game_map._wall_grid, max_dist=200
        )

        screen_pts: list[tuple[int, int]] = []
        if len(vis_points) >= 3:
            screen_pts = [(int(x - cox), int(y - coy)) for x, y in vis_points]

            # Fog on map — walls visible but dimmed outside visibility
            self.fog.fill((0, 0, 0, 200))
            pygame.draw.polygon(self.fog, (0, 0, 0, 0), screen_pts)
            self.screen.blit(self.fog, (0, 0))

        # Draw entities onto layer
        self.layer.fill((0, 0, 0, 0))

        for entity in self.entities:
            entity.draw(self.layer, cam_offset)

        for pickup in self.pickups:
            pickup.draw(self.layer, cam_offset)

        self.player.aim_target = self.mpos_world
        self.player.draw(self.layer, cam_offset)

        for portal in self.portals:
            if portal:
                portal.draw(self.layer, cam_offset)

        # Mask entities to visible area only
        if screen_pts:
            self.fog.fill((255, 255, 255, 0))
            pygame.draw.polygon(self.fog, (255, 255, 255, 255), screen_pts)
            self.layer.blit(self.fog, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

        self.screen.blit(self.layer, (0, 0))

        pygame.transform.scale(self.screen, self.window_size, self.window)
        self.hud.draw(self.window, self)
        pygame.display.flip()
