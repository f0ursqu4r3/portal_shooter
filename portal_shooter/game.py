from __future__ import annotations

import cProfile
import math
import pstats
import random

import pygame
from pyglm import glm

from portal_shooter.entities import (
    Bullet,
    Camera,
    Pickup,
    PickupKind,
    Player,
    Portal,
    Shell,
)
from portal_shooter.hud import HUD
from portal_shooter.map import GameMap, compute_visibility
from portal_shooter.sound import SoundPlayer
from portal_shooter.sound_propagation import PortalData, compute_sound
from portal_shooter.util import get_collisions, intersect, point_dist_to_line
from portal_shooter.weapons import WEAPON_STATS, WeaponKind

pygame.init()


class Game:
    def __init__(self) -> None:
        self.window_size: glm.vec2 = glm.vec2(1280, 720)
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

        self.sound_player: SoundPlayer = SoundPlayer("./assets/sounds", "wav")

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

        self.owned_weapons: set[WeaponKind] = {WeaponKind.PISTOL}

        _weapon_kind_map: dict[str, WeaponKind] = {
            "shotgun": WeaponKind.SHOTGUN,
            "smg": WeaponKind.SMG,
            "rifle": WeaponKind.RIFLE,
        }
        self.pickups: list[Pickup] = []
        for pos, kind_str, weapon_sub in self.game_map.pickup_positions:
            pk = PickupKind(kind_str)
            wk = (
                _weapon_kind_map.get(weapon_sub or "")
                if pk == PickupKind.WEAPON
                else None
            )
            self.pickups.append(Pickup(pos, pk, weapon_kind=wk))

        self.time_scale: float = 1
        self.shot_timer: float = 0
        self.speed_buff_timer: float = 0

        self.current_weapon: WeaponKind = WeaponKind.PISTOL
        self.ammo: dict[WeaponKind, int] = {
            WeaponKind.PISTOL: 0,
            WeaponKind.SHOTGUN: 0,
            WeaponKind.SMG: 0,
            WeaponKind.RIFLE: 0,
        }

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
            self.sound_player.play("Step1", volume=0.2)
            self.player_walk_timer = 0

        if pygame.mouse.get_pressed()[0] and not self.shot_timer:
            stats = WEAPON_STATS[self.current_weapon]

            # Check ammo
            if (
                stats.ammo_per_shot
                and self.ammo[self.current_weapon] < stats.ammo_per_shot
            ):
                pass  # No ammo — don't fire
            else:
                fire_vec = glm.normalize(self.mpos_world - self.player.pos)

                for _ in range(stats.pellets):
                    spread_offset = (
                        random.uniform(-stats.spread / 2, stats.spread / 2)
                        if stats.spread
                        else 0.0
                    )
                    angle = math.atan2(fire_vec.y, fire_vec.x) + spread_offset
                    pellet_dir = glm.vec2(math.cos(angle), math.sin(angle))
                    bullet = Bullet(
                        self.player.pos + pellet_dir * 15,
                        pellet_dir,
                        speed=stats.bullet_speed,
                        damage=stats.damage,
                        piercing=stats.piercing,
                        color=stats.color,
                    )
                    self.entities.append(bullet)
                    self.bullets.append(bullet)

                # Consume ammo
                if stats.ammo_per_shot:
                    self.ammo[self.current_weapon] -= stats.ammo_per_shot

                eject_vec = glm.vec2(-fire_vec.y, fire_vec.x)
                self.entities.append(
                    Shell(
                        self.player.pos + (fire_vec * 4) + (eject_vec * 4),
                        eject_vec,
                        self.current_weapon,
                    )
                )

                shake = fire_vec * -(random.random() * 1.5 + 1.5) * stats.recoil
                self.player.vel = shake * 10
                self.sound_player.play("Shoot1")

                self.camera.shake = glm.vec2(shake)

                rate = (
                    stats.fire_rate / 2
                    if self.speed_buff_timer > 0
                    else stats.fire_rate
                )
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
                    hit = self.game_map.find_nearest_wall_hit(self.player.pos, aim_dir)
                    if hit:
                        idx = 0 if event.key == pygame.K_q else 1
                        color = (255, 127, 0) if idx == 0 else (41, 174, 255)
                        self.portals[idx] = Portal(hit[0] + hit[1] * 2, hit[1], color)
                elif event.key == pygame.K_z:
                    self.portals[0] = None
                elif event.key == pygame.K_x:
                    self.portals[1] = None

                elif event.key == pygame.K_SPACE:
                    print(f"{self.player.health=} {self.clock.get_fps()=}")

                elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                    owned = sorted(self.owned_weapons)
                    slot = event.key - pygame.K_1
                    if slot < len(owned):
                        self.current_weapon = owned[slot]

            elif event.type == pygame.MOUSEWHEEL:
                owned = sorted(self.owned_weapons)
                if len(owned) > 1:
                    idx = owned.index(self.current_weapon)
                    idx = (idx + event.y) % len(owned)
                    self.current_weapon = owned[idx]

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
                self.play_spatial("Ricochet1", float(entity.pos.x), float(entity.pos.y))

            self.do_portal(entity)

        for collision in get_collisions(self.player, self.bullets):
            self.player.health -= collision.damage
            dead.add(collision)
            if self.player.health > 0:
                vel = glm.vec2(-collision.vel.y, collision.vel.x)
                self.player.emitter.vel = vel
                self.player.emitter.burst()
                self.sound_player.play("Hurt1")
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
                elif pickup.kind == PickupKind.SPEED:
                    self.speed_buff_timer = 5.0
                elif pickup.kind == PickupKind.WEAPON:
                    wk = pickup.weapon_kind
                    if wk is not None:
                        self.owned_weapons.add(wk)
                        wstats = WEAPON_STATS[wk]
                        self.ammo[wk] = min(
                            self.ammo[wk] + wstats.pickup_ammo, wstats.max_ammo
                        )
                else:
                    # Ammo pickup: give 5-10 ammo for a random owned non-pistol weapon
                    ammo_weapons = [
                        w for w in self.owned_weapons if w != WeaponKind.PISTOL
                    ]
                    if not ammo_weapons:
                        continue
                    weapon = random.choice(ammo_weapons)
                    wstats = WEAPON_STATS[weapon]
                    amount = random.randint(5, 10)
                    self.ammo[weapon] = min(self.ammo[weapon] + amount, wstats.max_ammo)
                self.sound_player.play("Portal1", volume=0.5)
                collected.append(pickup)
        if collected:
            self.pickups = [p for p in self.pickups if p not in collected]

        if self.speed_buff_timer > 0:
            self.speed_buff_timer = max(0, self.speed_buff_timer - dt)

    def play_spatial(
        self, sound_name: str, source_x: float, source_y: float, base_volume: float = 1.0
    ) -> None:
        aim = self.mpos_world - self.player.pos
        mag = float((aim.x**2 + aim.y**2) ** 0.5)
        if mag < 1e-10:
            fx, fy = 1.0, 0.0
        else:
            fx, fy = float(aim.x) / mag, float(aim.y) / mag

        portal_data: tuple[PortalData, PortalData] | None = None
        p0, p1 = self.portals[0], self.portals[1]
        if p0 is not None and p1 is not None:
            portal_data = (
                PortalData(
                    float(p0.pos.x), float(p0.pos.y),
                    float(p0.normal.x), float(p0.normal.y),
                    float(p0.exit.x), float(p0.exit.y),
                    float(p0.line[0].x), float(p0.line[0].y),
                    float(p0.line[1].x), float(p0.line[1].y),
                ),
                PortalData(
                    float(p1.pos.x), float(p1.pos.y),
                    float(p1.normal.x), float(p1.normal.y),
                    float(p1.exit.x), float(p1.exit.y),
                    float(p1.line[0].x), float(p1.line[0].y),
                    float(p1.line[1].x), float(p1.line[1].y),
                ),
            )

        assert self.game_map._wall_grid is not None
        volume, pan = compute_sound(
            float(self.player.pos.x), float(self.player.pos.y),
            fx, fy,
            source_x, source_y,
            self.game_map._wall_grid,
            portal_data,
        )
        final_vol = volume * base_volume
        if final_vol > 0.01:
            self.sound_player.play(sound_name, volume=final_vol, pan=pan)

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
                self.play_spatial("Portal1", float(entity.pos.x), float(entity.pos.y))

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
