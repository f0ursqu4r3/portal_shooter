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
    Enemy,
    EnemyState,
    ExitDoor,
    MeleeEnemy,
    Pickup,
    PickupKind,
    Player,
    Portal,
    RangedEnemy,
    Shell,
)
from portal_shooter.entities.entity import Entity
from portal_shooter.entities.grenade import Grenade, GRENADE_DAMAGE, GRENADE_RADIUS
from portal_shooter.entities.pickup import PICKUP_RANGE
from portal_shooter.hud import HUD
from portal_shooter.inventory import Inventory, InventoryItem
from portal_shooter.inventory_ui import InventoryUI
from portal_shooter.level import LevelState, get_difficulty_params
from portal_shooter.map import GameMap, compute_visibility
from portal_shooter.map.pathfinding import has_line_of_sight
from portal_shooter.particles import FadeOutParticle, ParticleEmitter
from portal_shooter.sound import SoundPlayer
from portal_shooter.sound_propagation import PortalData, compute_sound
from portal_shooter.util import get_collisions, intersect, point_dist_to_line
from portal_shooter.weapons import WEAPON_STATS, WeaponKind

pygame.init()

_WEAPON_KIND_MAP: dict[str, WeaponKind] = {
    "shotgun": WeaponKind.SHOTGUN,
    "smg": WeaponKind.SMG,
    "rifle": WeaponKind.RIFLE,
}


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
        self.enemy_bullets: list[Bullet] = []

        self.portals: list[Portal | None] = [None, None]

        self.owned_weapons: set[WeaponKind] = {WeaponKind.PISTOL}

        self.pickups: list[Pickup] = []

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

        self.inventory: Inventory = Inventory()
        self.inventory_ui: InventoryUI = InventoryUI()

        self._nearest_pickup: Pickup | None = None
        self._pickup_font: pygame.font.Font = pygame.font.Font(
            "assets/fonts/homespun.ttf", 8
        )

        self.layer: pygame.Surface = pygame.Surface(
            self.screen.get_size(), pygame.SRCALPHA
        )
        self.fog: pygame.Surface = pygame.Surface(
            self.screen.get_size(), pygame.SRCALPHA
        )
        self._layer_size: tuple[int, int] = self.screen.get_size()

        # Enemies
        self.enemies: list[Enemy] = []

        # Grenades
        self.grenades: list[Grenade] = []

        # Level progression
        self.level: LevelState = LevelState()
        self.exit_door: ExitDoor | None = None

        self.setup_floor()

    def setup_floor(self) -> None:
        """Set up (or reset) a floor: regenerate map, spawn enemies, place key + exit."""
        self.game_map = GameMap()
        self.player.pos = glm.vec2(self.game_map.spawn_pos)
        self.camera = Camera(
            self.player.pos,
            target=self.player,
            map_bounds=self.game_map.bounds,
        )

        # Reset projectiles and portals
        self.entities = []
        self.bullets = []
        self.enemy_bullets = []
        self.grenades = []
        self.portals = [None, None]

        # Spawn pickups from map generation
        self.pickups = []
        for pos, kind_str, weapon_sub in self.game_map.pickup_positions:
            pk = PickupKind(kind_str)
            wk = (
                _WEAPON_KIND_MAP.get(weapon_sub or "")
                if pk in (PickupKind.WEAPON, PickupKind.AMMO)
                else None
            )
            self.pickups.append(Pickup(pos, pk, weapon_kind=wk))

        # Level setup: key + exit
        self.level.setup_floor(self.game_map.rooms)
        # Place key pickup
        self.pickups.append(
            Pickup(glm.vec2(self.level.key_pos), PickupKind.KEY)
        )
        # Place exit door
        self.exit_door = ExitDoor(glm.vec2(self.level.exit_pos))

        # Spawn enemies
        self.spawn_enemies_for_rooms()

        # Re-bake minimap
        self.hud.bake_minimap(self)

    def spawn_enemies_for_rooms(self) -> None:
        """Spawn enemies in rooms (skip room 0 = spawn room)."""
        self.enemies = []
        params = get_difficulty_params(self.level.floor)
        count_mul = params["enemy_count_mul"]
        health_mul = params["enemy_health_mul"]

        for i, room in enumerate(self.game_map.rooms):
            if i == 0:
                continue
            area = room.bounds.width * room.bounds.height
            if area < 2000:
                continue
            base_count = 1 if area < 5000 else (2 if area < 10000 else 3)
            count = max(1, int(base_count * count_mul))

            for _ in range(count):
                offset = glm.vec2(
                    random.uniform(-20, 20), random.uniform(-20, 20)
                )
                pos = room.center + offset

                enemy: Enemy
                if random.random() < 0.6:
                    enemy = MeleeEnemy(pos)
                else:
                    enemy = RangedEnemy(pos)

                enemy.health = int(enemy.health * health_mul)
                enemy.max_health = enemy.health
                enemy.current_room = i

                # Drop table: random ammo type
                weapon_types = ["shotgun", "smg", "rifle"]
                enemy.drop_table = [
                    ("health", None, 0.3),
                    ("ammo", random.choice(weapon_types), 0.2),
                ]
                self.enemies.append(enemy)

    def _apply_damage(self, amount: int) -> None:
        """Apply damage to player: armor absorbs first, then health."""
        if self.player.invincible:
            return
        if self.player.armor > 0:
            absorbed = min(self.player.armor, amount)
            self.player.armor -= absorbed
            amount -= absorbed
        if amount > 0:
            self.player.health -= amount

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

        if not self.player.is_dashing:
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

        if pygame.mouse.get_pressed()[0] and not self.shot_timer and not self.inventory_ui.is_open:
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
                self._alert_enemies_at(
                    float(self.player.pos.x), float(self.player.pos.y), loudness=1.0
                )

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
                continue

            if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                if self.inventory_ui.handle_event(event, self):
                    continue  # consumed by inventory

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_i:
                    self.inventory_ui.toggle()
                    pygame.mouse.set_visible(self.inventory_ui.is_open)
                elif event.key in (pygame.K_q, pygame.K_e):
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

                elif event.key == pygame.K_f:
                    if self.inventory_ui.handle_key(event.key, self):
                        pass  # consumed by inventory UI
                    elif self._nearest_pickup is not None:
                        pickup = self._nearest_pickup
                        # KEY pickup: set level state directly
                        if pickup.kind == PickupKind.KEY:
                            self.level.has_key = True
                            if self.exit_door is not None:
                                self.exit_door.active = True
                            self.sound_player.play("Portal1", volume=0.5)
                            self.pickups.remove(pickup)
                            self._nearest_pickup = None
                        else:
                            item = InventoryItem.from_pickup(pickup)
                            if self.inventory.add(item):
                                self.sound_player.play("Portal1", volume=0.5)
                                self.pickups.remove(pickup)
                                self._nearest_pickup = None

                elif event.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
                    self.player.start_dash()

                elif event.key == pygame.K_g:
                    self._throw_grenade()

                elif event.key == pygame.K_SPACE:
                    print(f"{self.player.health=} {self.clock.get_fps()=}")

                elif not self.inventory_ui.is_open and event.key in (
                    pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4
                ):
                    owned = sorted(self.owned_weapons)
                    slot = event.key - pygame.K_1
                    if slot < len(owned):
                        self.current_weapon = owned[slot]

            elif event.type == pygame.MOUSEWHEEL and not self.inventory_ui.is_open:
                owned = sorted(self.owned_weapons)
                if len(owned) > 1:
                    idx = owned.index(self.current_weapon)
                    idx = (idx + event.y) % len(owned)
                    self.current_weapon = owned[idx]

    def _throw_grenade(self) -> None:
        """Find a grenade in inventory and throw it toward cursor."""
        for i, slot in enumerate(self.inventory.slots):
            if slot is not None and slot.kind == PickupKind.GRENADE:
                self.inventory.remove_one(i)
                direction = self.mpos_world - self.player.pos
                if glm.length(direction) > 1:
                    direction = glm.normalize(direction)
                else:
                    direction = glm.vec2(1, 0)
                grenade = Grenade(
                    glm.vec2(self.player.pos) + direction * 10,
                    direction,
                )
                self.grenades.append(grenade)
                self.sound_player.play("Shoot1", volume=0.3)
                break

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

        # Entity updates (bullets + shells)
        dead: set[Bullet | Shell] = set()
        for entity in self.entities:
            old_pos = glm.vec2(entity.pos)
            entity.update(dt)

            if entity.life < 0:
                dead.add(entity)
                continue

            if self.game_map.collide_entity(entity, old_pos):
                self.play_spatial("Ricochet1", float(entity.pos.x), float(entity.pos.y))
                self._alert_enemies_at(float(entity.pos.x), float(entity.pos.y), loudness=0.5)

            self.do_portal(entity)

        # Enemy bullets hit player
        for collision in get_collisions(self.player, self.enemy_bullets):
            self._apply_damage(collision.damage)
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
            self.enemy_bullets = [b for b in self.enemy_bullets if b not in dead]

        # Enemy updates
        self._update_enemies(dt)

        # Grenade updates
        self._update_grenades(dt)

        for portal in self.portals:
            if portal:
                portal.update(dt)
                portal.active = all(self.portals)

        # Update pickups and find nearest within range
        self._nearest_pickup = None
        best_dist = PICKUP_RANGE + 1.0
        for pickup in self.pickups:
            pickup.update(dt)
            dx = pickup.pos.x - self.player.pos.x
            dy = pickup.pos.y - self.player.pos.y
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < best_dist:
                best_dist = dist
                self._nearest_pickup = pickup

        if self.speed_buff_timer > 0:
            self.speed_buff_timer = max(0, self.speed_buff_timer - dt)

        # Exit door
        if self.exit_door is not None:
            self.exit_door.update(dt)
            if self.exit_door.active and self.exit_door.in_range(self.player.pos):
                self.level.advance_floor()
                self.setup_floor()

    def _update_enemies(self, dt: float) -> None:
        """Update all enemies: pathfinding, AI, collision, damage."""
        assert self.game_map._wall_grid is not None
        room_graph = self.game_map.room_graph

        dead_enemies: list[Enemy] = []

        for enemy in self.enemies:
            if not enemy.alive:
                enemy.update(dt)
                # Keep dead enemies briefly for particle effects
                if not enemy.emitter.particles:
                    dead_enemies.append(enemy)
                continue

            # LOS check — only within sight range
            from portal_shooter.entities.enemy import _SIGHT_RANGE
            dist_to_player = glm.distance(enemy.pos, self.player.pos)
            los = (
                dist_to_player <= _SIGHT_RANGE
                and has_line_of_sight(
                    enemy.pos, self.player.pos, self.game_map._wall_grid
                )
            )

            # Re-path every 0.5s — only if enemy is aware (has a last-known pos)
            if enemy._path_timer <= 0 and room_graph is not None:
                enemy._path_timer = 0.5
                if los:
                    # Live tracking — path toward actual player position
                    enemy.target_waypoint = glm.vec2(self.player.pos)
                elif enemy._last_known_pos is not None:
                    # Path toward remembered position
                    enemy.current_room = room_graph.find_room(enemy.pos)
                    target_room = room_graph.find_room(enemy._last_known_pos)
                    if enemy.current_room is not None and target_room is not None:
                        path = room_graph.find_path(enemy.current_room, target_room)
                        if len(path) > 1:
                            next_room = path[1]
                            enemy.target_waypoint = glm.vec2(
                                self.game_map.rooms[next_room].center
                            )
                        else:
                            enemy.target_waypoint = glm.vec2(enemy._last_known_pos)
                    else:
                        enemy.target_waypoint = glm.vec2(enemy._last_known_pos)
                else:
                    # Unaware — no waypoint
                    enemy.target_waypoint = None

            # AI update
            wants_fire = enemy.update_ai(
                self.player.pos, los, enemy.target_waypoint
            )

            # Ranged enemy firing
            if wants_fire:
                fire_dir = glm.normalize(self.player.pos - enemy.pos)
                bullet = Bullet(
                    enemy.pos + fire_dir * 8,
                    fire_dir,
                    speed=80,
                    damage=enemy.damage,
                    color=(160, 80, 200),
                )
                self.entities.append(bullet)
                self.enemy_bullets.append(bullet)
                self.play_spatial("Shoot1", float(enemy.pos.x), float(enemy.pos.y), 0.3)

            old_pos = glm.vec2(enemy.pos)
            enemy.update(dt)
            self.game_map.collide_player(enemy, old_pos, radius=3.0)
            self.do_portal(enemy)

            # Player bullets hit enemies
            for collision in get_collisions(enemy, self.bullets):
                knockback = glm.normalize(collision.vel) * 30 if collision.vel else None
                enemy.take_damage(
                    collision.damage, knockback, source_pos=self.player.pos
                )
                collision.life = 0
                self.play_spatial("Hurt1", float(enemy.pos.x), float(enemy.pos.y), 0.5)

            # Melee contact damage
            if (
                isinstance(enemy, MeleeEnemy)
                and enemy.alive
                and enemy._attack_timer <= 0
                and enemy.rect.colliderect(self.player.rect)
            ):
                self._apply_damage(enemy.damage)
                enemy._attack_timer = enemy.attack_cooldown
                # Retreat after landing the hit
                enemy.start_retreat(self.player.pos)
                if self.player.health > 0:
                    self.player.emitter.vel = glm.vec2(
                        random.uniform(-1, 1), random.uniform(-1, 1)
                    )
                    self.player.emitter.burst()
                    self.sound_player.play("Hurt1")
                else:
                    self.player.emitter.vel = None
                    self.player.emitter.burst(50)
                    self.time_scale = 0.05

        # Remove fully dead enemies and spawn drops
        for enemy in dead_enemies:
            self._spawn_enemy_drops(enemy)
            self.enemies.remove(enemy)

        # Clean up dead bullets
        self.bullets = [b for b in self.bullets if b.life > 0]

    def _spawn_enemy_drops(self, enemy: Enemy) -> None:
        """Spawn pickup drops from enemy's drop table."""
        for kind_str, weapon_sub, chance in enemy.drop_table:
            if random.random() < chance:
                pk = PickupKind(kind_str)
                wk = _WEAPON_KIND_MAP.get(weapon_sub or "") if weapon_sub else None
                offset = glm.vec2(random.uniform(-5, 5), random.uniform(-5, 5))
                self.pickups.append(Pickup(enemy.pos + offset, pk, weapon_kind=wk))

    def _update_grenades(self, dt: float) -> None:
        """Update grenades: movement, bounce, portal, detonation."""
        dead_grenades: list[Grenade] = []

        for grenade in self.grenades:
            if grenade.detonated:
                # Keep updating emitter for explosion particles
                grenade.update(dt)
                if not grenade.emitter.particles:
                    dead_grenades.append(grenade)
                continue

            old_pos = glm.vec2(grenade.pos)
            grenade.update(dt)

            if grenade.detonated:
                # Just detonated this frame — apply area damage
                self._detonate_grenade(grenade)
                continue

            self.game_map.collide_grenade(grenade, old_pos)
            self.do_portal(grenade)

        for g in dead_grenades:
            self.grenades.remove(g)

    def _detonate_grenade(self, grenade: Grenade) -> None:
        """Apply area damage from grenade explosion."""
        # Damage enemies
        for enemy in self.enemies:
            if not enemy.alive:
                continue
            dist = glm.distance(grenade.pos, enemy.pos)
            if dist < GRENADE_RADIUS:
                falloff = 1.0 - dist / GRENADE_RADIUS
                damage = int(GRENADE_DAMAGE * falloff)
                knockback = None
                if dist > 1:
                    knockback = glm.normalize(enemy.pos - grenade.pos) * 50
                enemy.take_damage(damage, knockback, source_pos=self.player.pos)

        # Self-damage to player (50% reduced)
        player_dist = glm.distance(grenade.pos, self.player.pos)
        if player_dist < GRENADE_RADIUS:
            falloff = 1.0 - player_dist / GRENADE_RADIUS
            damage = int(GRENADE_DAMAGE * falloff * 0.5)
            self._apply_damage(damage)
            if self.player.health > 0:
                self.player.emitter.burst()
            else:
                self.player.emitter.burst(50)
                self.time_scale = 0.05

        # Explosion particles — replace the trail emitter with a big burst
        grenade.emitter = ParticleEmitter(
            pos=glm.vec2(grenade.pos),
            vel=None,
            spawn_rate=0,
            shape=ParticleEmitter.Circle(10),
            particle_class=FadeOutParticle,
            particle_kwargs={"color": (255, 180, 40)},
        )
        grenade.emitter.burst(30)
        # Secondary darker ring
        inner = ParticleEmitter(
            pos=glm.vec2(grenade.pos),
            vel=None,
            spawn_rate=0,
            shape=ParticleEmitter.Circle(4),
            particle_class=FadeOutParticle,
            particle_kwargs={"color": (255, 80, 20)},
        )
        inner.burst(15)
        # Merge inner particles into main emitter so they draw together
        grenade.emitter.particles.extend(inner.particles)
        self.play_spatial("Shoot1", float(grenade.pos.x), float(grenade.pos.y), 0.8)
        self._alert_enemies_at(float(grenade.pos.x), float(grenade.pos.y), loudness=1.5)

    def _get_portal_data(self) -> tuple[PortalData, PortalData] | None:
        p0, p1 = self.portals[0], self.portals[1]
        if p0 is None or p1 is None:
            return None
        n0x, n0y = float(p0.normal.x), float(p0.normal.y)
        n1x, n1y = float(p1.normal.x), float(p1.normal.y)
        return (
            PortalData(
                float(p0.pos.x) - n0x * 2, float(p0.pos.y) - n0y * 2,
                n0x, n0y,
                float(p0.pos.x), float(p0.pos.y),
                float(p0.line[0].x), float(p0.line[0].y),
                float(p0.line[1].x), float(p0.line[1].y),
            ),
            PortalData(
                float(p1.pos.x) - n1x * 2, float(p1.pos.y) - n1y * 2,
                n1x, n1y,
                float(p1.pos.x), float(p1.pos.y),
                float(p1.line[0].x), float(p1.line[0].y),
                float(p1.line[1].x), float(p1.line[1].y),
            ),
        )

    def play_spatial(
        self, sound_name: str, source_x: float, source_y: float, base_volume: float = 1.0
    ) -> None:
        aim = self.mpos_world - self.player.pos
        mag = float((aim.x**2 + aim.y**2) ** 0.5)
        if mag < 1e-10:
            fx, fy = 1.0, 0.0
        else:
            fx, fy = float(aim.x) / mag, float(aim.y) / mag

        portal_data = self._get_portal_data()

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

    def _alert_enemies_at(
        self, source_x: float, source_y: float, loudness: float = 1.0
    ) -> None:
        """Alert enemies that can 'hear' a sound at the given position.

        Uses the same raytraced sound propagation as the player audio —
        volume is computed at each enemy's position accounting for walls and
        portals.  If the perceived volume * loudness exceeds a threshold the
        enemy becomes ALERT and remembers the sound source location.
        """
        assert self.game_map._wall_grid is not None
        portal_data = self._get_portal_data()
        hearing_threshold = 0.05

        for enemy in self.enemies:
            if not enemy.alive:
                continue
            # Skip enemies that are already actively engaged
            if enemy.state in (EnemyState.PURSUING, EnemyState.ATTACKING):
                continue

            vol, _ = compute_sound(
                float(enemy.pos.x), float(enemy.pos.y),
                1.0, 0.0,  # facing doesn't affect volume
                source_x, source_y,
                self.game_map._wall_grid,
                portal_data,
            )
            if vol * loudness >= hearing_threshold:
                enemy.hear_sound(glm.vec2(source_x, source_y))

    def do_portal(self, entity: Entity) -> None:
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

        # Draw enemies
        for enemy in self.enemies:
            enemy.draw(self.layer, cam_offset)

        # Draw grenades
        for grenade in self.grenades:
            grenade.draw(self.layer, cam_offset)

        # Draw exit door
        if self.exit_door is not None:
            self.exit_door.draw(self.layer, cam_offset)

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

        if self._nearest_pickup is not None:
            self._draw_pickup_tooltip(self.screen, self._nearest_pickup, cam_offset)

        pygame.transform.scale(self.screen, self.window_size, self.window)
        self.hud.draw(self.window, self)
        self.inventory_ui.draw(self.window, self)
        pygame.display.flip()

    def _draw_pickup_tooltip(
        self, surface: pygame.Surface, pickup: Pickup, cam_offset: glm.vec2
    ) -> None:
        bob = math.sin(pickup.age * 3) * 2
        screen_pos = pickup.pos - cam_offset + glm.vec2(0, bob)

        label = f"F: {pickup.display_name}"
        if pickup.quantity > 1:
            label += f" x{pickup.quantity}"
        text_surf = self._pickup_font.render(label, False, (220, 220, 220))
        tw, th = text_surf.get_size()
        pad = 2
        bx = int(screen_pos.x) - (tw + pad * 2) // 2
        by = int(screen_pos.y) - th - pad * 2 - 8

        bg_rect = pygame.Rect(bx, by, tw + pad * 2, th + pad * 2)
        pygame.draw.rect(surface, (10, 8, 12, 180), bg_rect)
        surface.blit(text_surf, (bx + pad, by + pad))
