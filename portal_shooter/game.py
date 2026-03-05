from __future__ import annotations

import cProfile
import math
import pstats
import random
from collections.abc import Callable

import pygame
from pyglm import glm

from portal_shooter.entities import (
    Bullet,
    Camera,
    Enemy,
    EnemyState,
    ExitDoor,
    ExploderEnemy,
    MeleeEnemy,
    Pickup,
    PickupKind,
    Player,
    RangedEnemy,
    Rocket,
    Shell,
)
from portal_shooter.entities.crate import Crate
from portal_shooter.entities.door import Door, Switch
from portal_shooter.entities.enemy import EXPLODER_DAMAGE, EXPLODER_RADIUS, _SIGHT_RANGE
from portal_shooter.entities.grenade import GRENADE_DAMAGE, GRENADE_RADIUS, Grenade
from portal_shooter.entities.pickup import PICKUP_RANGE
from portal_shooter.entities.rocket import ROCKET_DAMAGE, ROCKET_RADIUS
from portal_shooter.hud import HUD
from portal_shooter.inventory import Inventory, InventoryItem
from portal_shooter.inventory_ui import InventoryUI
from portal_shooter.level import LevelState, get_difficulty_params
from portal_shooter.map import GameMap, compute_visibility
from portal_shooter.map.pathfinding import has_line_of_sight
from portal_shooter.particles import FadeOutParticle, ParticleEmitter
from portal_shooter.sound import SoundPlayer
from portal_shooter.sound_propagation import compute_sound
from portal_shooter.weapons import (
    AMMO_COLORS,
    AMMO_PICKUP_QTY,
    WEAPON_STATS,
    AmmoType,
    MeleeStyle,
    WeaponKind,
)

pygame.init()

def _point_in_polygon(px: float, py: float, verts: list[glm.vec2]) -> bool:
    """Ray-casting point-in-polygon test."""
    n = len(verts)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = verts[i].x, verts[i].y
        xj, yj = verts[j].x, verts[j].y
        if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


_WEAPON_KIND_MAP: dict[str, WeaponKind] = {
    "shotgun": WeaponKind.SHOTGUN,
    "smg": WeaponKind.SMG,
    "rifle": WeaponKind.RIFLE,
    "machine_gun": WeaponKind.MACHINE_GUN,
    "sniper_rifle": WeaponKind.SNIPER_RIFLE,
    "grenade_launcher": WeaponKind.GRENADE_LAUNCHER,
    "rocket_launcher": WeaponKind.ROCKET_LAUNCHER,
    "sword": WeaponKind.SWORD,
    "axe": WeaponKind.AXE,
}

_AMMO_TYPE_MAP: dict[str, AmmoType] = {
    "light": AmmoType.LIGHT,
    "medium": AmmoType.MEDIUM,
    "heavy": AmmoType.HEAVY,
    "shells": AmmoType.SHELLS,
    "grenade": AmmoType.GRENADE,
    "rocket": AmmoType.ROCKET,
}


class _DamageNumber:
    """Floating damage number that drifts upward and fades out."""

    __slots__ = ["pos", "text", "age", "color"]

    def __init__(
        self, pos: glm.vec2, amount: int, color: tuple[int, int, int] = (255, 220, 80)
    ) -> None:
        self.pos: glm.vec2 = glm.vec2(pos)
        self.text: str = str(amount)
        self.age: float = 0.0
        self.color: tuple[int, int, int] = color

    @property
    def alive(self) -> bool:
        return self.age < 0.8

    def update(self, dt: float) -> None:
        self.age += dt
        self.pos.y -= 15 * dt  # float upward


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

        self.owned_weapons: set[WeaponKind] = {WeaponKind.PISTOL, WeaponKind.KNIFE}

        self.pickups: list[Pickup] = []

        self.time_scale: float = 1
        self.shot_timer: float = 0
        self.speed_buff_timer: float = 0

        self.current_weapon: WeaponKind = WeaponKind.PISTOL
        self.ammo: dict[WeaponKind, int] = {k: 0 for k in WeaponKind}
        self.ammo[WeaponKind.PISTOL] = 12

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

        # Visibility cache
        self._vis_cache: list[tuple[float, float]] = []
        self._vis_cache_pos: tuple[float, float] = (0.0, 0.0)

        # Enemies
        self.enemies: list[Enemy] = []

        # Grenades
        self.grenades: list[Grenade] = []

        # Rockets
        self.rockets: list[Rocket] = []

        # Destructible crates
        self.crates: list[Crate] = []
        self._crate_wall_lookup: dict[tuple[float, float, float, float], Crate] = {}

        # Doors and switches
        self.doors: list[Door] = []
        self.switches: list[Switch] = []

        # Muzzle flash
        self._muzzle_flash_timer: float = 0.0
        self._muzzle_flash_pos: glm.vec2 = glm.vec2()
        self._muzzle_flash_color: tuple[int, int, int] = (255, 255, 200)

        # Melee flash
        self._melee_flash_timer: float = 0.0
        self._melee_flash_angle: float = 0.0
        self._melee_flash_range: float = 0.0
        self._melee_flash_arc: float = 0.0
        self._melee_flash_style: MeleeStyle = MeleeStyle.NONE
        self._melee_flash_color: tuple[int, int, int] = (200, 200, 200)

        # Wall impact sparks
        self._impact_emitters: list[ParticleEmitter] = []

        # Damage numbers
        self._damage_numbers: list[_DamageNumber] = []

        # Reload state
        self._reloading: bool = False
        self._reload_timer: float = 0.0

        # Death / pause state
        self._dead: bool = False
        self._paused: bool = False
        self._death_font: pygame.font.Font = pygame.font.Font(
            "assets/fonts/homespun.ttf", 32
        )
        self._ui_font: pygame.font.Font = pygame.font.Font(
            "assets/fonts/homespun.ttf", 14
        )

        # Upgrade screen state
        self._upgrade_screen: bool = False
        self._upgrade_choices: list[tuple[str, str, Callable[[], None]]] = []
        self._upgrade_font: pygame.font.Font = pygame.font.Font(
            "assets/fonts/homespun.ttf", 12
        )
        self._upgrade_title_font: pygame.font.Font = pygame.font.Font(
            "assets/fonts/homespun.ttf", 24
        )

        # Permanent run modifiers
        self._damage_mul: float = 1.0
        self._fire_rate_mul: float = 1.0
        self._has_regen: bool = False
        self._regen_timer: float = 0.0

        # Level progression
        self.level: LevelState = LevelState()
        self.exit_door: ExitDoor | None = None

        self.setup_floor()

        # Initial light ammo reserve (12 rounds)
        self.inventory.add(InventoryItem(
            kind=PickupKind.AMMO,
            weapon_kind=None,
            color=AMMO_COLORS[AmmoType.LIGHT],
            quantity=12,
            ammo_type=AmmoType.LIGHT,
        ))

    def setup_floor(self) -> None:
        """Set up (or reset) a floor: regenerate map, spawn enemies, place key + exit."""
        self.game_map = GameMap()
        self.player.pos = glm.vec2(self.game_map.spawn_pos)
        self.camera = Camera(
            self.player.pos,
            target=self.player,
            map_bounds=self.game_map.bounds,
        )

        # Reset projectiles
        self.entities = []
        self.bullets = []
        self.enemy_bullets = []
        self.grenades = []
        self.rockets = []
        # Spawn pickups from map generation
        self.pickups = []
        for pos, kind_str, weapon_sub in self.game_map.pickup_positions:
            pk = PickupKind(kind_str)
            if pk == PickupKind.AMMO and weapon_sub:
                at = _AMMO_TYPE_MAP.get(weapon_sub)
                qty = AMMO_PICKUP_QTY[at] if at else 1
                self.pickups.append(Pickup(pos, pk, ammo_type=at, quantity=qty))
            elif pk == PickupKind.WEAPON and weapon_sub:
                wk = _WEAPON_KIND_MAP.get(weapon_sub)
                self.pickups.append(Pickup(pos, pk, weapon_kind=wk))
            else:
                self.pickups.append(Pickup(pos, pk))

        # Level setup: key + exit
        self.level.setup_floor(self.game_map.rooms)
        # Place key pickup
        self.pickups.append(Pickup(glm.vec2(self.level.key_pos), PickupKind.KEY))
        # Place exit door
        self.exit_door = ExitDoor(glm.vec2(self.level.exit_pos))

        # Spawn crates and register their walls
        self.crates = []
        self._crate_wall_lookup = {}
        crate_walls_to_add: list[tuple[glm.vec2, glm.vec2]] = []
        for cpos in self.game_map.crate_positions:
            crate = Crate(cpos)
            self.crates.append(crate)
            crate_walls_to_add.extend(crate.walls)
            for key in crate._wall_keys:
                self._crate_wall_lookup[key] = crate
        if crate_walls_to_add:
            self.game_map.add_walls(crate_walls_to_add)

        # Spawn doors and switches
        self.doors = []
        self.switches = []
        door_walls_to_add: list[tuple[glm.vec2, glm.vec2]] = []
        for door_p1, door_p2, switch_pos in self.game_map.door_positions:
            door = Door(door_p1, door_p2)
            switch = Switch(switch_pos, door, color=door.color)
            self.doors.append(door)
            self.switches.append(switch)
            door_walls_to_add.append(door.wall)
        if door_walls_to_add:
            self.game_map.add_walls(door_walls_to_add)

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
                # Try random positions inside the room polygon
                pos: glm.vec2 | None = None
                for _attempt in range(20):
                    candidate = room.center + glm.vec2(
                        random.uniform(-20, 20), random.uniform(-20, 20)
                    )
                    if _point_in_polygon(
                        float(candidate.x), float(candidate.y), room.vertices
                    ):
                        pos = candidate
                        break
                if pos is None:
                    # Fallback: use center only if inside
                    if _point_in_polygon(
                        float(room.center.x), float(room.center.y), room.vertices
                    ):
                        pos = glm.vec2(room.center)
                    else:
                        continue

                enemy: Enemy
                roll = random.random()
                if roll < 0.50:
                    enemy = MeleeEnemy(pos)
                elif roll < 0.85:
                    enemy = RangedEnemy(pos)
                else:
                    enemy = ExploderEnemy(pos)

                enemy.health = int(enemy.health * health_mul)
                enemy.max_health = enemy.health
                enemy.current_room = i

                # Drop table: random ammo type
                ammo_types = ["light", "medium", "heavy", "shells"]
                enemy.drop_table = [
                    ("health", None, 0.3),
                    ("ammo", random.choice(ammo_types), 0.2),
                ]
                self.enemies.append(enemy)

    def _destroy_crate(self, crate: Crate) -> None:
        """Remove a crate's walls from the map and clean up lookup."""
        self.game_map.remove_walls(crate.walls)
        for key in crate._wall_keys:
            self._crate_wall_lookup.pop(key, None)
        self._vis_cache = []  # invalidate visibility cache

    def _restart_game(self) -> None:
        """Reset entire game state for a new run."""
        self._dead = False
        self._paused = False
        self.player.health = self.player.max_health
        self.player.armor = 0
        self.player.invincible = False
        self.player.is_dashing = False
        self.time_scale = 1.0
        self.owned_weapons = {WeaponKind.PISTOL, WeaponKind.KNIFE}
        self.current_weapon = WeaponKind.PISTOL
        self.ammo = {k: 0 for k in WeaponKind}
        self.ammo[WeaponKind.PISTOL] = 12
        self.speed_buff_timer = 0
        self.shot_timer = 0
        self._reloading = False
        self._reload_timer = 0.0
        self.inventory = Inventory()
        # Initial light ammo reserve
        self.inventory.add(InventoryItem(
            kind=PickupKind.AMMO,
            weapon_kind=None,
            color=AMMO_COLORS[AmmoType.LIGHT],
            quantity=12,
            ammo_type=AmmoType.LIGHT,
        ))
        self._impact_emitters.clear()
        self._damage_numbers.clear()
        # Reset upgrade state
        self._damage_mul = 1.0
        self._fire_rate_mul = 1.0
        self._has_regen = False
        self._regen_timer = 0.0
        self._upgrade_screen = False
        self._upgrade_choices = []
        self.player.max_health = 100
        self.player.health = 100
        self.player.max_armor = 50
        self.player.armor = 0
        self.player.speed = 50
        self.level = LevelState()
        self.setup_floor()
        pygame.mouse.set_visible(False)

    def _generate_upgrade_choices(
        self,
    ) -> list[tuple[str, str, "Callable[[], None]"]]:
        """Return 3 random upgrade options as (name, description, apply_fn) tuples."""
        pool: list[tuple[str, str, Callable[[], None]]] = [
            ("+20 Max HP", "Increase max health by 20\nand heal 20 HP", self._upgrade_hp),
            ("+15 Max Armor", "Increase max armor by 15\nand gain 15 armor", self._upgrade_armor),
            ("+5 Speed", "Increase movement\nspeed by 5", self._upgrade_speed),
            ("+10% Damage", "All weapons deal\n10% more damage", self._upgrade_damage),
            ("Faster Fire Rate", "All weapons fire\n15% faster", self._upgrade_fire_rate),
        ]
        if not self._has_regen:
            pool.append(("Regeneration", "Slowly regenerate\n1 HP every 3 seconds", self._upgrade_regen))
        return random.sample(pool, min(3, len(pool)))

    def _upgrade_hp(self) -> None:
        self.player.max_health += 20
        self.player.health = min(self.player.health + 20, self.player.max_health)

    def _upgrade_armor(self) -> None:
        self.player.max_armor += 15
        self.player.armor = min(self.player.armor + 15, self.player.max_armor)

    def _upgrade_speed(self) -> None:
        self.player.speed += 5

    def _upgrade_damage(self) -> None:
        self._damage_mul += 0.10

    def _upgrade_fire_rate(self) -> None:
        self._fire_rate_mul *= 0.85

    def _upgrade_regen(self) -> None:
        self._has_regen = True

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

        if self._dead or self._paused or self._upgrade_screen:
            return

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

        _inv_blocks = self.inventory_ui.is_open and self.inventory_ui.is_over_panel(
            *pygame.mouse.get_pos()
        )
        mouse_buttons = pygame.mouse.get_pressed()

        if (
            mouse_buttons[0]
            and not self.shot_timer
            and not _inv_blocks
            and not self._reloading
        ):
            stats = WEAPON_STATS[self.current_weapon]

            if stats.melee_style != MeleeStyle.NONE:
                self._perform_melee_attack()
            elif (
                stats.ammo_per_shot
                and self.ammo[self.current_weapon] < stats.ammo_per_shot
            ):
                self._start_reload()  # Auto-reload on empty
            else:
                fire_vec = glm.normalize(self.mpos_world - self.player.pos)

                if self.current_weapon == WeaponKind.GRENADE_LAUNCHER:
                    grenade = Grenade(self.player.pos + fire_vec * 15, fire_vec)
                    grenade.speed = 180.0
                    self.grenades.append(grenade)
                elif self.current_weapon == WeaponKind.ROCKET_LAUNCHER:
                    rocket = Rocket(self.player.pos + fire_vec * 15, fire_vec)
                    self.rockets.append(rocket)
                else:
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
                            damage=int(stats.damage * self._damage_mul),
                            piercing=stats.piercing,
                            color=stats.color,
                        )
                        self.entities.append(bullet)
                        self.bullets.append(bullet)

                # Consume ammo and auto-reload when empty
                if stats.ammo_per_shot:
                    self.ammo[self.current_weapon] -= stats.ammo_per_shot
                    if self.ammo[self.current_weapon] < stats.ammo_per_shot:
                        self._start_reload()

                # Muzzle flash
                self._muzzle_flash_timer = 0.06
                self._muzzle_flash_pos = glm.vec2(self.player.pos + fire_vec * 12)
                self._muzzle_flash_color = stats.color

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

                rate = stats.fire_rate * self._fire_rate_mul
                if self.speed_buff_timer > 0:
                    rate /= 2
                self.shot_timer = rate
                self.time_scale = 0.2

    def process_pygame_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                continue

            if event.type == pygame.KEYDOWN:
                # Death screen: R to restart
                if self._dead and event.key == pygame.K_r:
                    self._restart_game()
                    continue

                # Pause toggle
                if event.key == pygame.K_ESCAPE:
                    if self._dead:
                        continue
                    if self._paused:
                        self._paused = False
                        pygame.mouse.set_visible(self.inventory_ui.is_open)
                    else:
                        self._paused = True
                    continue

                # Q to quit while paused
                if self._paused and event.key == pygame.K_q:
                    self.running = False
                    continue

            if self._upgrade_screen:
                if (
                    event.type == pygame.MOUSEBUTTONDOWN
                    and event.button == 1
                ):
                    mx, my = event.pos
                    self._handle_upgrade_click(mx, my)
                continue

            if self._dead or self._paused:
                continue

            if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                if self.inventory_ui.handle_event(event, self):
                    continue  # consumed by inventory

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_TAB:
                    self.inventory_ui.toggle()
                    pygame.mouse.set_visible(self.inventory_ui.is_open)
                elif event.key == pygame.K_e:
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
                        elif pickup.kind == PickupKind.WEAPON:
                            wk = pickup.weapon_kind
                            if wk is not None:
                                self.owned_weapons.add(wk)
                                stats = WEAPON_STATS[wk]
                                self.ammo[wk] = (
                                    stats.magazine_size
                                    if stats.magazine_size > 0
                                    else 0
                                )
                                self.current_weapon = wk
                                self._reloading = False
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

                elif event.key == pygame.K_r:
                    self._start_reload()

                elif event.key in (
                    pygame.K_1,
                    pygame.K_2,
                    pygame.K_3,
                    pygame.K_4,
                    pygame.K_5,
                    pygame.K_6,
                    pygame.K_7,
                    pygame.K_8,
                    pygame.K_9,
                ):
                    owned = sorted(self.owned_weapons)
                    slot = event.key - pygame.K_1
                    if slot < len(owned):
                        self.current_weapon = owned[slot]
                        self._reloading = False

            elif event.type == pygame.MOUSEWHEEL:
                owned = sorted(self.owned_weapons)
                if len(owned) > 1:
                    idx = owned.index(self.current_weapon)
                    idx = (idx + event.y) % len(owned)
                    self.current_weapon = owned[idx]
                    self._reloading = False

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

        if self._paused or self._upgrade_screen:
            return

        if self.player.health <= 0 and not self._dead:
            self._dead = True

        if self.player.health > 0:
            self.time_scale = min(1, self.time_scale + tdt * 2)

        dt = tdt * self.time_scale
        self.shot_timer = max(0, self.shot_timer - dt)

        # Reload timer
        if self._reloading:
            self._reload_timer -= dt
            if self._reload_timer <= 0:
                self._finish_reload()

        self.player_walk_timer += dt

        old_pos = glm.vec2(self.player.pos)
        self.player.update(dt)
        self.game_map.collide_player(self.player, old_pos)
        self.camera.update(dt, self.screen_size)

        # Check switches
        for switch in self.switches:
            if switch.check_activate(self.player.pos):
                # Door opened — remove its wall
                self.game_map.remove_walls([switch.door.wall])
                self.sound_player.play("Portal1", volume=0.4)
                self._vis_cache = []  # invalidate visibility cache

        # Entity updates (bullets + shells)
        dead: set[Bullet | Shell] = set()
        for entity in self.entities:
            old_pos = glm.vec2(entity.pos)
            entity.update(dt)

            if entity.life < 0:
                dead.add(entity)
                continue

            hit_wall = self.game_map.collide_entity(entity, old_pos)
            if hit_wall:
                self.play_spatial(
                    "Ricochet",
                    float(entity.pos.x),
                    float(entity.pos.y),
                    random_variant=True,
                )
                self._alert_enemies_at(
                    float(entity.pos.x), float(entity.pos.y), loudness=0.5
                )
                # Wall impact sparks
                spark = ParticleEmitter(
                    pos=glm.vec2(entity.pos),
                    vel=None,
                    spawn_rate=0,
                    shape=ParticleEmitter.Circle(3),
                    particle_class=FadeOutParticle,
                    particle_kwargs={"color": (255, 220, 120)},
                )
                spark.burst(random.randint(3, 6))
                self._impact_emitters.append(spark)
                # Check if a crate was hit
                crate = self._crate_wall_lookup.get(hit_wall)
                if crate is not None and crate.alive:
                    from portal_shooter.entities.bullet import Bullet as _Bullet

                    bullet_dmg = entity.damage if isinstance(entity, _Bullet) else 0
                    if bullet_dmg > 0:
                        crate.take_damage(bullet_dmg)
                        if not crate.alive:
                            self._destroy_crate(crate)


        # Enemy bullets hit player
        player_rect = self.player.rect
        for collision in [
            b for b in self.enemy_bullets if b.rect.colliderect(player_rect)
        ]:
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

        # Rocket updates
        self._update_rockets(dt)

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

        if self._muzzle_flash_timer > 0:
            self._muzzle_flash_timer -= dt
        if self._melee_flash_timer > 0:
            self._melee_flash_timer -= dt

        # Update doors and switches
        for door in self.doors:
            door.update(dt)
        for switch in self.switches:
            switch.update(dt)

        # Update crates (for particle emitters on dead crates)
        dead_crates: list[Crate] = []
        for crate in self.crates:
            crate.update(dt)
            if not crate.alive and not crate.emitter.particles:
                dead_crates.append(crate)
        for crate in dead_crates:
            self.crates.remove(crate)

        # Update impact emitters + damage numbers
        for emitter in self._impact_emitters:
            emitter.update(dt)
        self._impact_emitters = [e for e in self._impact_emitters if e.particles]
        for dmg in self._damage_numbers:
            dmg.update(dt)
        self._damage_numbers = [d for d in self._damage_numbers if d.alive]

        # Regeneration tick
        if self._has_regen and self.player.health > 0:
            self._regen_timer += dt
            if self._regen_timer >= 3.0:
                self._regen_timer -= 3.0
                if self.player.health < self.player.max_health:
                    self.player.health = min(self.player.health + 1, self.player.max_health)

        # Exit door
        if self.exit_door is not None:
            self.exit_door.update(dt)
            if self.exit_door.active and self.exit_door.in_range(self.player.pos):
                self._upgrade_choices = self._generate_upgrade_choices()
                self._upgrade_screen = True

    def _update_enemies(self, dt: float) -> None:
        """Update all enemies: pathfinding, AI, collision, damage."""
        assert self.game_map._wall_grid is not None
        room_graph = self.game_map.room_graph

        dead_enemies: list[Enemy] = []
        los_enemies: list[Enemy] = []

        player_px: float = self.player.pos.x
        player_py: float = self.player.pos.y
        # Distance beyond which enemies get a lightweight update (no LOS/collision)
        _ACTIVE_RANGE_SQ: float = 250.0 * 250.0

        for enemy in self.enemies:
            if not enemy.alive:
                enemy.update(dt)
                # Handle exploder detonation
                if (
                    isinstance(enemy, ExploderEnemy)
                    and enemy.exploded
                    and not enemy._explosion_done
                ):
                    enemy._explosion_done = True
                    self._detonate_exploder(enemy)
                # Keep dead enemies briefly for particle effects
                if not enemy.emitter.particles:
                    dead_enemies.append(enemy)
                continue

            # Squared distance to player (cheap — no sqrt)
            epx: float = enemy.pos.x
            epy: float = enemy.pos.y
            ddx = epx - player_px
            ddy = epy - player_py
            dist_sq = ddx * ddx + ddy * ddy

            # Far enemies: lightweight update (move + timers only, no LOS/collision)
            far = dist_sq > _ACTIVE_RANGE_SQ
            if far:
                enemy.update(dt)
                # Still check bullet hits on far enemies
                enemy_rect = enemy.rect
                for collision in [
                    b for b in self.bullets if b.rect.colliderect(enemy_rect)
                ]:
                    knockback = (
                        glm.normalize(collision.vel) * 30 if collision.vel else None
                    )
                    enemy.take_damage(
                        collision.damage, knockback, source_pos=self.player.pos
                    )
                    collision.life = 0
                    self._damage_numbers.append(
                        _DamageNumber(
                            enemy.pos
                            + glm.vec2(random.uniform(-4, 4), random.uniform(-6, -2)),
                            collision.damage,
                        )
                    )
                continue

            dist_to_player = math.sqrt(dist_sq)
            los = dist_to_player <= _SIGHT_RANGE and has_line_of_sight(
                enemy.pos, self.player.pos, self.game_map._wall_grid
            )
            if los:
                los_enemies.append(enemy)

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
                self.player.pos, los, enemy.target_waypoint, self.game_map._wall_grid
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

            # Save old pos as raw floats to avoid glm.vec2 allocation
            old_x, old_y = enemy.pos.x, enemy.pos.y
            enemy.update(dt)
            # Only run collision if enemy actually moved
            if enemy.pos.x != old_x or enemy.pos.y != old_y:
                _old_pos = glm.vec2(old_x, old_y)
                self.game_map.collide_player(enemy, _old_pos, radius=3.0, push_iters=1)

            # Player bullets hit enemies
            enemy_rect = enemy.rect
            for collision in [
                b for b in self.bullets if b.rect.colliderect(enemy_rect)
            ]:
                knockback = glm.normalize(collision.vel) * 30 if collision.vel else None
                enemy.take_damage(
                    collision.damage, knockback, source_pos=self.player.pos
                )
                collision.life = 0
                self.play_spatial("Hurt1", float(enemy.pos.x), float(enemy.pos.y), 0.5)
                # Damage number
                offset = glm.vec2(random.uniform(-4, 4), random.uniform(-6, -2))
                self._damage_numbers.append(
                    _DamageNumber(enemy.pos + offset, collision.damage)
                )

            # Melee contact damage
            if (
                isinstance(enemy, MeleeEnemy)
                and enemy.alive
                and enemy._attack_timer <= 0
                and enemy_rect.colliderect(self.player.rect)
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

        # Inter-enemy alerting: enemies with LOS shout to nearby allies
        _SHOUT_RANGE_SQ: float = 80.0 * 80.0
        for shouter in los_enemies:
            sx, sy = shouter.pos.x, shouter.pos.y
            for ally in self.enemies:
                if ally is shouter or not ally.alive:
                    continue
                if ally.state in (EnemyState.PURSUING, EnemyState.ATTACKING):
                    continue
                adx = ally.pos.x - sx
                ady = ally.pos.y - sy
                if adx * adx + ady * ady <= _SHOUT_RANGE_SQ:
                    ally.hear_sound(shouter.pos)

        # Remove fully dead enemies and spawn drops
        for enemy in dead_enemies:
            self._spawn_enemy_drops(enemy)
            self.enemies.remove(enemy)

        # Clean up dead bullets (both player and enemy)
        self.bullets = [b for b in self.bullets if b.life > 0]
        self.enemy_bullets = [b for b in self.enemy_bullets if b.life > 0]

    def _spawn_enemy_drops(self, enemy: Enemy) -> None:
        """Spawn pickup drops from enemy's drop table."""
        for kind_str, weapon_sub, chance in enemy.drop_table:
            if random.random() < chance:
                pk = PickupKind(kind_str)
                offset = glm.vec2(random.uniform(-5, 5), random.uniform(-5, 5))
                if pk == PickupKind.AMMO and weapon_sub:
                    at = _AMMO_TYPE_MAP.get(weapon_sub)
                    qty = AMMO_PICKUP_QTY[at] if at else 1
                    self.pickups.append(
                        Pickup(enemy.pos + offset, pk, ammo_type=at, quantity=qty)
                    )
                else:
                    self.pickups.append(Pickup(enemy.pos + offset, pk))

    def _perform_melee_attack(self) -> None:
        """Execute a melee attack with the current weapon."""
        stats = WEAPON_STATS[self.current_weapon]
        fire_vec = glm.normalize(self.mpos_world - self.player.pos)
        attack_angle = math.atan2(fire_vec.y, fire_vec.x)
        hit_count = 0

        # Hit enemies in range/arc
        for enemy in self.enemies:
            if not enemy.alive:
                continue
            dx = enemy.pos.x - self.player.pos.x
            dy = enemy.pos.y - self.player.pos.y
            dist = math.sqrt(dx * dx + dy * dy)
            if dist > stats.melee_range:
                continue
            enemy_angle = math.atan2(dy, dx)
            diff = (enemy_angle - attack_angle + math.pi) % (2 * math.pi) - math.pi
            if abs(diff) > stats.melee_arc_half:
                continue
            kb_dir = glm.normalize(enemy.pos - self.player.pos) if dist > 0.1 else fire_vec
            enemy.take_damage(
                int(stats.damage * self._damage_mul),
                knockback=kb_dir * stats.melee_knockback,
                source_pos=self.player.pos,
            )
            self._damage_numbers.append(
                _DamageNumber(enemy.pos, int(stats.damage * self._damage_mul))
            )
            hit_count += 1
            # Impact spark
            spark = ParticleEmitter(
                pos=glm.vec2(enemy.pos),
                vel=None,
                spawn_rate=0,
                shape=ParticleEmitter.Circle(3),
                particle_class=FadeOutParticle,
                particle_kwargs={"color": stats.color},
            )
            spark.burst(random.randint(3, 6))
            self._impact_emitters.append(spark)
            if not stats.piercing:
                break

        # Hit crates in range/arc
        for crate in self.crates:
            if not crate.alive:
                continue
            dx = crate.pos.x - self.player.pos.x
            dy = crate.pos.y - self.player.pos.y
            dist = math.sqrt(dx * dx + dy * dy)
            if dist > stats.melee_range:
                continue
            crate_angle = math.atan2(dy, dx)
            diff = (crate_angle - attack_angle + math.pi) % (2 * math.pi) - math.pi
            if abs(diff) > stats.melee_arc_half:
                continue
            crate.take_damage(int(stats.damage * self._damage_mul))
            if not crate.alive:
                self._destroy_crate(crate)
            hit_count += 1

        # Screen shake + lunge on hit
        if hit_count > 0:
            shake_strength = min(stats.melee_knockback * 0.08, 3.0)
            self.camera.shake = fire_vec * -shake_strength
            lunge = min(stats.melee_knockback * 0.15, 5.0)
            self.player.pos += fire_vec * lunge

        # Set melee flash state
        self._melee_flash_timer = 0.1
        self._melee_flash_angle = attack_angle
        self._melee_flash_range = stats.melee_range
        self._melee_flash_arc = stats.melee_arc_half
        self._melee_flash_style = stats.melee_style
        self._melee_flash_color = stats.color

        if stats.melee_style == MeleeStyle.STAB:
            self.sound_player.play_random("Ricochet", volume=0.5)
        else:
            self.sound_player.play("Hurt1", volume=0.6)
        self._alert_enemies_at(
            float(self.player.pos.x), float(self.player.pos.y), loudness=0.3
        )

        rate = stats.fire_rate * self._fire_rate_mul
        if self.speed_buff_timer > 0:
            rate /= 2
        self.shot_timer = rate

    def _start_reload(self) -> None:
        """Begin reloading the current weapon if conditions are met."""
        stats = WEAPON_STATS[self.current_weapon]
        if stats.ammo_type is None or stats.magazine_size <= 0:
            return
        if (
            self._reloading
            or self.ammo[self.current_weapon] >= stats.magazine_size
            or self._count_reserve_ammo(stats.ammo_type) <= 0
        ):
            return
        self._reloading = True
        self._reload_timer = stats.reload_time

    def _finish_reload(self) -> None:
        """Complete reload: consume reserve ammo and fill magazine."""
        self._reloading = False
        wk = self.current_weapon
        stats = WEAPON_STATS[wk]
        if stats.ammo_type is None:
            return
        rounds_needed = stats.magazine_size - self.ammo[wk]
        available = self._count_reserve_ammo(stats.ammo_type)
        load = min(rounds_needed, available)
        if load > 0:
            self._consume_reserve_ammo(stats.ammo_type, load)
            self.ammo[wk] += load
            self.sound_player.play("Portal1", volume=0.4)

    def _count_reserve_ammo(self, ammo_type: AmmoType) -> int:
        """Sum all ammo item quantities in inventory matching ammo_type."""
        total = 0
        for slot in self.inventory.slots:
            if (
                slot is not None
                and slot.kind == PickupKind.AMMO
                and slot.ammo_type == ammo_type
            ):
                total += slot.quantity
        return total

    def _consume_reserve_ammo(self, ammo_type: AmmoType, amount: int) -> None:
        """Remove `amount` rounds from matching inventory ammo items."""
        remaining = amount
        for i, slot in enumerate(self.inventory.slots):
            if remaining <= 0:
                break
            if (
                slot is not None
                and slot.kind == PickupKind.AMMO
                and slot.ammo_type == ammo_type
            ):
                take = min(slot.quantity, remaining)
                slot.quantity -= take
                remaining -= take
                if slot.quantity <= 0:
                    self.inventory.slots[i] = None

    def _update_grenades(self, dt: float) -> None:
        """Update grenades: movement, bounce, detonation."""
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

        for g in dead_grenades:
            self.grenades.remove(g)

    def _detonate_explosion(
        self, pos: glm.vec2, damage: int, radius: int
    ) -> None:
        """Apply area damage from an explosion at pos."""
        # Damage enemies
        for enemy in self.enemies:
            if not enemy.alive:
                continue
            dist = glm.distance(pos, enemy.pos)
            if dist < radius:
                falloff = 1.0 - dist / radius
                dmg = int(damage * falloff)
                knockback = None
                if dist > 1:
                    knockback = glm.normalize(enemy.pos - pos) * 50
                enemy.take_damage(dmg, knockback, source_pos=self.player.pos)
                if dmg > 0:
                    offset = glm.vec2(random.uniform(-4, 4), random.uniform(-6, -2))
                    self._damage_numbers.append(
                        _DamageNumber(enemy.pos + offset, dmg, color=(255, 180, 40))
                    )

        # Damage crates in blast radius
        for crate in self.crates:
            if not crate.alive:
                continue
            dist = glm.distance(pos, crate.pos)
            if dist < radius:
                falloff = 1.0 - dist / radius
                dmg = int(damage * falloff)
                if dmg > 0:
                    crate.take_damage(dmg)
                    if not crate.alive:
                        self._destroy_crate(crate)

        # Self-damage to player (50% reduced)
        player_dist = glm.distance(pos, self.player.pos)
        if player_dist < radius:
            falloff = 1.0 - player_dist / radius
            dmg = int(damage * falloff * 0.5)
            self._apply_damage(dmg)
            if self.player.health > 0:
                self.player.emitter.burst()
            else:
                self.player.emitter.burst(50)
                self.time_scale = 0.05

        self.play_spatial("Shoot1", float(pos.x), float(pos.y), 0.8)
        self._alert_enemies_at(float(pos.x), float(pos.y), loudness=1.5)

    def _detonate_exploder(self, enemy: ExploderEnemy) -> None:
        """Apply area damage from an exploder enemy's self-destruct."""
        pos = glm.vec2(enemy.pos)
        damage = int(EXPLODER_DAMAGE * self._damage_mul) if self._damage_mul != 1.0 else EXPLODER_DAMAGE
        radius = EXPLODER_RADIUS

        # Damage other enemies in radius (with distance falloff + knockback)
        for other in self.enemies:
            if other is enemy or not other.alive:
                continue
            dist = glm.distance(pos, other.pos)
            if dist < radius:
                falloff = 1.0 - dist / radius
                dmg = int(damage * falloff)
                knockback = None
                if dist > 1:
                    knockback = glm.normalize(other.pos - pos) * 50
                other.take_damage(dmg, knockback, source_pos=pos)
                if dmg > 0:
                    offset = glm.vec2(random.uniform(-4, 4), random.uniform(-6, -2))
                    self._damage_numbers.append(
                        _DamageNumber(other.pos + offset, dmg, color=(255, 180, 40))
                    )
                # Chain reaction: if killing another exploder, set its flag
                if isinstance(other, ExploderEnemy) and other.health <= 0:
                    other._exploded = True

        # Damage player (full rate, no 0.5 reduction)
        player_dist = glm.distance(pos, self.player.pos)
        if player_dist < radius:
            falloff = 1.0 - player_dist / radius
            dmg = int(EXPLODER_DAMAGE * falloff)
            self._apply_damage(dmg)
            if self.player.health > 0:
                self.player.emitter.burst()
            else:
                self.player.emitter.burst(50)
                self.time_scale = 0.05

        # Damage crates
        for crate in self.crates:
            if not crate.alive:
                continue
            dist = glm.distance(pos, crate.pos)
            if dist < radius:
                falloff = 1.0 - dist / radius
                dmg = int(damage * falloff)
                if dmg > 0:
                    crate.take_damage(dmg)
                    if not crate.alive:
                        self._destroy_crate(crate)

        # Explosion particles
        outer = ParticleEmitter(
            pos=glm.vec2(pos),
            vel=None,
            spawn_rate=0,
            shape=ParticleEmitter.Circle(8),
            particle_class=FadeOutParticle,
            particle_kwargs={"color": (255, 120, 30)},
        )
        outer.burst(25)
        inner = ParticleEmitter(
            pos=glm.vec2(pos),
            vel=None,
            spawn_rate=0,
            shape=ParticleEmitter.Circle(3),
            particle_class=FadeOutParticle,
            particle_kwargs={"color": (200, 40, 20)},
        )
        inner.burst(12)
        outer.particles.extend(inner.particles)
        self._impact_emitters.append(outer)

        # Screen shake
        self.camera.shake = glm.vec2(
            random.uniform(-3.0, 3.0), random.uniform(-3.0, 3.0)
        )

        # Sound + alert
        self.play_spatial("Shoot1", float(pos.x), float(pos.y), 0.8)
        self._alert_enemies_at(float(pos.x), float(pos.y), loudness=1.5)

    def _detonate_grenade(self, grenade: Grenade) -> None:
        """Apply area damage from grenade explosion."""
        self._detonate_explosion(grenade.pos, int(GRENADE_DAMAGE * self._damage_mul), GRENADE_RADIUS)

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

    def _update_rockets(self, dt: float) -> None:
        """Update rockets: movement, collision, detonation."""
        dead_rockets: list[Rocket] = []

        for rocket in self.rockets:
            if rocket.detonated:
                rocket.update(dt)
                if not rocket.emitter.particles:
                    dead_rockets.append(rocket)
                continue

            old_pos = glm.vec2(rocket.pos)
            rocket.update(dt)

            # Check wall collision (reuse grenade bounce detection — detonate instead)
            if self.game_map.collide_grenade(rocket, old_pos):
                rocket.detonated = True
                self._detonate_explosion(rocket.pos, int(ROCKET_DAMAGE * self._damage_mul), ROCKET_RADIUS)
                rocket.emitter = ParticleEmitter(
                    pos=glm.vec2(rocket.pos),
                    vel=None,
                    spawn_rate=0,
                    shape=ParticleEmitter.Circle(12),
                    particle_class=FadeOutParticle,
                    particle_kwargs={"color": (255, 120, 40)},
                )
                rocket.emitter.burst(35)
                continue

            # Check enemy proximity collision
            for enemy in self.enemies:
                if not enemy.alive:
                    continue
                if glm.distance(rocket.pos, enemy.pos) < 6:
                    rocket.detonated = True
                    self._detonate_explosion(rocket.pos, int(ROCKET_DAMAGE * self._damage_mul), ROCKET_RADIUS)
                    rocket.emitter = ParticleEmitter(
                        pos=glm.vec2(rocket.pos),
                        vel=None,
                        spawn_rate=0,
                        shape=ParticleEmitter.Circle(12),
                        particle_class=FadeOutParticle,
                        particle_kwargs={"color": (255, 120, 40)},
                    )
                    rocket.emitter.burst(35)
                    break

        for r in dead_rockets:
            self.rockets.remove(r)

    def play_spatial(
        self,
        sound_name: str,
        source_x: float,
        source_y: float,
        base_volume: float = 1.0,
        random_variant: bool = False,
    ) -> None:
        aim = self.mpos_world - self.player.pos
        mag = float((aim.x**2 + aim.y**2) ** 0.5)
        if mag < 1e-10:
            fx, fy = 1.0, 0.0
        else:
            fx, fy = float(aim.x) / mag, float(aim.y) / mag

        assert self.game_map._wall_grid is not None
        volume, pan = compute_sound(
            float(self.player.pos.x),
            float(self.player.pos.y),
            fx,
            fy,
            source_x,
            source_y,
            self.game_map._wall_grid,
        )
        final_vol = volume * base_volume
        if final_vol > 0.01:
            if random_variant:
                self.sound_player.play_random(sound_name, volume=final_vol, pan=pan)
            else:
                self.sound_player.play(sound_name, volume=final_vol, pan=pan)

    def _alert_enemies_at(
        self, source_x: float, source_y: float, loudness: float = 1.0
    ) -> None:
        """Alert enemies that can 'hear' a sound at the given position.

        Uses the same raytraced sound propagation as the player audio —
        volume is computed at each enemy's position accounting for walls.
        If the perceived volume * loudness exceeds a threshold the enemy
        becomes ALERT and remembers the sound source location.
        """
        assert self.game_map._wall_grid is not None
        hearing_threshold = 0.05

        for enemy in self.enemies:
            if not enemy.alive:
                continue
            # Skip enemies that are already actively engaged
            if enemy.state in (EnemyState.PURSUING, EnemyState.ATTACKING):
                continue

            vol, _ = compute_sound(
                float(enemy.pos.x),
                float(enemy.pos.y),
                1.0,
                0.0,  # facing doesn't affect volume
                source_x,
                source_y,
                self.game_map._wall_grid,
            )
            if vol * loudness >= hearing_threshold:
                enemy.hear_sound(glm.vec2(source_x, source_y))

    def draw(self) -> None:
        cam_offset = self.camera.pos + self.camera.shake - self.screen_size / 2
        self.screen.fill((10, 8, 12))
        self.game_map.draw(self.screen, cam_offset)

        # Compute visibility polygon (cached — recompute only when player moves >1px)
        cox, coy = cam_offset.x, cam_offset.y
        assert self.game_map._wall_grid is not None
        px, py = self.player.pos.x, self.player.pos.y
        cx, cy = self._vis_cache_pos
        dx = px - cx
        dy = py - cy
        if dx * dx + dy * dy > 1.0 or not self._vis_cache:
            self._vis_cache = compute_visibility(
                self.player.pos, self.game_map._wall_grid, max_dist=200
            )
            self._vis_cache_pos = (px, py)
        vis_points = self._vis_cache

        screen_pts: list[tuple[int, int]] = []
        if len(vis_points) >= 3:
            screen_pts = [(int(x - cox), int(y - coy)) for x, y in vis_points]

            # Fog on map — walls visible but dimmed outside visibility
            self.fog.fill((0, 0, 0, 200))
            pygame.draw.polygon(self.fog, (0, 0, 0, 0), screen_pts)
            self.screen.blit(self.fog, (0, 0))

        # Draw entities onto layer
        self.layer.fill((0, 0, 0, 0))

        # Viewport bounds for off-screen culling (world coords, with margin)
        sw, sh = self._layer_size
        vl = cox - 16.0
        vt = coy - 16.0
        vr = cox + sw + 16.0
        vb = coy + sh + 16.0

        for entity in self.entities:
            ex = entity.pos.x
            ey = entity.pos.y
            if vl <= ex <= vr and vt <= ey <= vb:
                entity.draw(self.layer, cam_offset)

        for pickup in self.pickups:
            ex = pickup.pos.x
            ey = pickup.pos.y
            if vl <= ex <= vr and vt <= ey <= vb:
                pickup.draw(self.layer, cam_offset)

        # Draw switches (on floor, below everything)
        for switch in self.switches:
            ex = switch.pos.x
            ey = switch.pos.y
            if vl <= ex <= vr and vt <= ey <= vb:
                switch.draw(self.layer, cam_offset)

        # Draw doors
        for door in self.doors:
            if not door.is_open:
                ex = door.pos.x
                ey = door.pos.y
                if vl <= ex <= vr and vt <= ey <= vb:
                    door.draw(self.layer, cam_offset)

        # Draw crates
        for crate in self.crates:
            ex = crate.pos.x
            ey = crate.pos.y
            if vl <= ex <= vr and vt <= ey <= vb:
                crate.draw(self.layer, cam_offset)

        # Draw impact sparks
        for emitter in self._impact_emitters:
            ex = emitter.pos.x
            ey = emitter.pos.y
            if vl <= ex <= vr and vt <= ey <= vb:
                emitter.draw(self.layer, cam_offset)

        # Draw enemies
        for enemy in self.enemies:
            ex = enemy.pos.x
            ey = enemy.pos.y
            if vl <= ex <= vr and vt <= ey <= vb:
                enemy.draw(self.layer, cam_offset)

        # Draw grenades
        for grenade in self.grenades:
            ex = grenade.pos.x
            ey = grenade.pos.y
            if vl <= ex <= vr and vt <= ey <= vb:
                grenade.draw(self.layer, cam_offset)

        # Draw rockets
        for rocket in self.rockets:
            ex = rocket.pos.x
            ey = rocket.pos.y
            if vl <= ex <= vr and vt <= ey <= vb:
                rocket.draw(self.layer, cam_offset)

        # Draw damage numbers
        for dmg in self._damage_numbers:
            ex = dmg.pos.x
            ey = dmg.pos.y
            if vl <= ex <= vr and vt <= ey <= vb:
                alpha = max(0, int(255 * (1.0 - dmg.age / 0.8)))
                r, g, b = dmg.color
                txt = self._pickup_font.render(dmg.text, False, (r, g, b))
                txt.set_alpha(alpha)
                dp = dmg.pos - cam_offset
                self.layer.blit(txt, (int(dp.x) - txt.get_width() // 2, int(dp.y)))

        # Draw exit door
        if self.exit_door is not None:
            ex = self.exit_door.pos.x
            ey = self.exit_door.pos.y
            if vl <= ex <= vr and vt <= ey <= vb:
                self.exit_door.draw(self.layer, cam_offset)

        self.player.aim_target = self.mpos_world
        self.player.current_weapon_kind = self.current_weapon
        self.player.draw(self.layer, cam_offset)

        # Reload progress bar near player
        if self._reloading:
            rstats = WEAPON_STATS[self.current_weapon]
            if rstats.reload_time > 0:
                pp = self.player.pos - cam_offset
                bar_w, bar_h = 16, 2
                bx = int(pp.x) - bar_w // 2
                by = int(pp.y) + 8
                progress = 1.0 - self._reload_timer / rstats.reload_time
                fill_w = max(0, int(bar_w * progress))
                pygame.draw.rect(self.layer, (40, 40, 40), (bx, by, bar_w, bar_h))
                if fill_w > 0:
                    pygame.draw.rect(
                        self.layer, rstats.color, (bx, by, fill_w, bar_h)
                    )

        # Muzzle flash
        if self._muzzle_flash_timer > 0:
            fp = self._muzzle_flash_pos - cam_offset
            r, g, b = self._muzzle_flash_color
            # Bright core
            cr = min(255, r + 100)
            cg = min(255, g + 100)
            cb = min(255, b + 100)
            pygame.draw.circle(self.layer, (cr, cg, cb, 220), (int(fp.x), int(fp.y)), 2)
            # Outer glow
            pygame.draw.circle(
                self.layer, (255, 255, 200, 100), (int(fp.x), int(fp.y)), 4
            )

        # Melee flash
        if self._melee_flash_timer > 0:
            pp = self.player.pos - cam_offset
            ppx, ppy = int(pp.x), int(pp.y)
            alpha = int(200 * (self._melee_flash_timer / 0.1))
            r, g, b = self._melee_flash_color
            if self._melee_flash_style == MeleeStyle.STAB:
                # Draw line from player toward cursor
                end_x = ppx + int(math.cos(self._melee_flash_angle) * self._melee_flash_range)
                end_y = ppy + int(math.sin(self._melee_flash_angle) * self._melee_flash_range)
                pygame.draw.line(self.layer, (r, g, b, alpha), (ppx, ppy), (end_x, end_y), 2)
            elif self._melee_flash_style == MeleeStyle.ARC:
                # Draw filled pie-slice polygon
                n_segs = 8
                arc_pts: list[tuple[int, int]] = [(ppx, ppy)]
                start_a = self._melee_flash_angle - self._melee_flash_arc
                step = (2 * self._melee_flash_arc) / n_segs
                for i in range(n_segs + 1):
                    a = start_a + step * i
                    ax = ppx + int(math.cos(a) * self._melee_flash_range)
                    ay = ppy + int(math.sin(a) * self._melee_flash_range)
                    arc_pts.append((ax, ay))
                if len(arc_pts) >= 3:
                    pygame.draw.polygon(self.layer, (r, g, b, alpha), arc_pts)

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

        if self._dead:
            self._draw_death_screen()
        elif self._upgrade_screen:
            self._draw_upgrade_screen()
        elif self._paused:
            self._draw_pause_screen()

        pygame.display.flip()

    def _draw_death_screen(self) -> None:
        # Lazy-init cached surfaces
        if not hasattr(self, "_death_overlay"):
            self._death_overlay = pygame.Surface(self.window_size, pygame.SRCALPHA)
            self._death_overlay.fill((0, 0, 0, 120))
            self._death_title = self._death_font.render(
                "GAME OVER", False, (200, 40, 40)
            )
            self._death_restart = self._ui_font.render(
                "R to Restart", False, (160, 160, 160)
            )
            self._death_floor_text: pygame.Surface | None = None
            self._death_floor_val: int = -1

        self.window.blit(self._death_overlay, (0, 0))
        cx, cy = int(self.window_size.x) // 2, int(self.window_size.y) // 2
        self.window.blit(
            self._death_title, (cx - self._death_title.get_width() // 2, cy - 40)
        )

        if self.level.floor != self._death_floor_val:
            self._death_floor_val = self.level.floor
            self._death_floor_text = self._ui_font.render(
                f"Floor {self.level.floor}", False, (180, 180, 180)
            )
        assert self._death_floor_text is not None
        self.window.blit(
            self._death_floor_text,
            (cx - self._death_floor_text.get_width() // 2, cy + 10),
        )
        self.window.blit(
            self._death_restart, (cx - self._death_restart.get_width() // 2, cy + 40)
        )

    def _draw_pause_screen(self) -> None:
        if not hasattr(self, "_pause_overlay"):
            self._pause_overlay = pygame.Surface(self.window_size, pygame.SRCALPHA)
            self._pause_overlay.fill((0, 0, 0, 140))
            self._pause_title = self._death_font.render(
                "PAUSED", False, (180, 180, 180)
            )
            self._pause_resume = self._ui_font.render(
                "ESC to Resume", False, (140, 140, 140)
            )
            self._pause_quit = self._ui_font.render("Q to Quit", False, (140, 140, 140))

        self.window.blit(self._pause_overlay, (0, 0))
        cx, cy = int(self.window_size.x) // 2, int(self.window_size.y) // 2
        self.window.blit(
            self._pause_title, (cx - self._pause_title.get_width() // 2, cy - 30)
        )
        self.window.blit(
            self._pause_resume, (cx - self._pause_resume.get_width() // 2, cy + 20)
        )
        self.window.blit(
            self._pause_quit, (cx - self._pause_quit.get_width() // 2, cy + 46)
        )

    def _get_upgrade_box_rects(self) -> list[pygame.Rect]:
        """Compute 3 upgrade box rects centered on the window."""
        box_w, box_h = 280, 150
        gap = 30
        total_w = box_w * 3 + gap * 2
        wx, wy = int(self.window_size.x), int(self.window_size.y)
        start_x = (wx - total_w) // 2
        start_y = wy // 2 - box_h // 2 + 20
        rects: list[pygame.Rect] = []
        for i in range(min(3, len(self._upgrade_choices))):
            bx = start_x + i * (box_w + gap)
            rects.append(pygame.Rect(bx, start_y, box_w, box_h))
        return rects

    def _handle_upgrade_click(self, mx: int, my: int) -> None:
        """Handle a click on the upgrade selection screen."""
        rects = self._get_upgrade_box_rects()
        for i, rect in enumerate(rects):
            if rect.collidepoint(mx, my):
                _, _, apply_fn = self._upgrade_choices[i]
                apply_fn()
                self._upgrade_screen = False
                self._upgrade_choices = []
                self.level.advance_floor()
                self.setup_floor()
                self.sound_player.play("Portal1")
                pygame.mouse.set_visible(False)
                return

    def _draw_upgrade_screen(self) -> None:
        """Draw the upgrade selection overlay."""
        pygame.mouse.set_visible(True)
        # Dark overlay
        overlay = pygame.Surface(self.window_size, pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.window.blit(overlay, (0, 0))

        wx, wy = int(self.window_size.x), int(self.window_size.y)
        cx = wx // 2

        # Title
        title = self._upgrade_title_font.render(
            "CHOOSE AN UPGRADE", False, (255, 220, 80)
        )
        self.window.blit(title, (cx - title.get_width() // 2, wy // 2 - 130))

        # Subtitle
        subtitle = self._ui_font.render(
            f"Floor {self.level.floor} Complete", False, (180, 180, 180)
        )
        self.window.blit(subtitle, (cx - subtitle.get_width() // 2, wy // 2 - 95))

        # Boxes
        rects = self._get_upgrade_box_rects()
        mx, my = pygame.mouse.get_pos()
        for i, rect in enumerate(rects):
            name, desc, _ = self._upgrade_choices[i]
            hovered = rect.collidepoint(mx, my)

            # Background
            bg_color = (40, 40, 50) if not hovered else (50, 50, 65)
            pygame.draw.rect(self.window, bg_color, rect)

            # Border
            border_color = (200, 180, 60) if hovered else (80, 80, 100)
            pygame.draw.rect(self.window, border_color, rect, 2)

            # Name
            name_surf = self._upgrade_font.render(name, False, (255, 255, 255))
            self.window.blit(
                name_surf,
                (rect.x + rect.width // 2 - name_surf.get_width() // 2, rect.y + 20),
            )

            # Description (multiline)
            lines = desc.split("\n")
            for li, line in enumerate(lines):
                line_surf = self._upgrade_font.render(line, False, (180, 180, 180))
                self.window.blit(
                    line_surf,
                    (
                        rect.x + rect.width // 2 - line_surf.get_width() // 2,
                        rect.y + 55 + li * 22,
                    ),
                )

    def _draw_pickup_tooltip(
        self, surface: pygame.Surface, pickup: Pickup, cam_offset: glm.vec2
    ) -> None:
        bob = math.sin(pickup.age * 3) * 2
        screen_pos = pickup.pos - cam_offset + glm.vec2(0, bob)

        label = f"E: {pickup.display_name}"
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
