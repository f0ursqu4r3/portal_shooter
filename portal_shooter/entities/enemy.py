from __future__ import annotations

import enum
import random

import pygame
from pyglm import glm

from portal_shooter.entities.entity import Entity
from portal_shooter.particles import FadeOutParticle, ParticleEmitter


class EnemyState(enum.Enum):
    IDLE = "idle"
    ROAMING = "roaming"
    ALERT = "alert"
    PURSUING = "pursuing"
    ATTACKING = "attacking"
    FLEEING = "fleeing"
    DEAD = "dead"


# How long an enemy stays alert after losing LOS before going idle
_ALERT_TIMEOUT = 3.0
# How long a melee enemy retreats after landing an attack
_RETREAT_DURATION = 0.4
# LOS range — enemies can only "see" this far
_SIGHT_RANGE = 120.0


class Enemy(Entity):
    __slots__ = [
        "speed",
        "max_health",
        "health",
        "damage",
        "state",
        "emitter",
        "current_room",
        "target_waypoint",
        "attack_cooldown",
        "_attack_timer",
        "_path_timer",
        "_stun_timer",
        "_alert_timer",
        "_roam_target",
        "_roam_timer",
        "_last_known_pos",
        "drop_table",
    ]

    def __init__(
        self,
        pos: glm.vec2,
        speed: float = 40,
        health: int = 25,
        damage: int = 10,
    ) -> None:
        super().__init__(pos)
        self.speed: float = speed
        self.max_health: int = health
        self.health: int = health
        self.damage: int = damage
        self.state: EnemyState = EnemyState.IDLE
        self.current_room: int | None = None
        self.target_waypoint: glm.vec2 | None = None
        self.attack_cooldown: float = 1.0
        self._attack_timer: float = 0.0
        self._path_timer: float = 0.0
        self._stun_timer: float = 0.0
        self._alert_timer: float = 0.0
        self._roam_target: glm.vec2 | None = None
        self._roam_timer: float = 0.0
        self._last_known_pos: glm.vec2 | None = None
        self.drop_table: list[tuple[str, str | None, float]] = [
            ("health", None, 0.3),
            ("ammo", None, 0.2),
        ]

        self.emitter: ParticleEmitter = ParticleEmitter(
            pos=self.pos,
            vel=glm.vec2(),
            spawn_rate=0,
            shape=ParticleEmitter.Point(30),
            particle_class=FadeOutParticle,
            particle_kwargs={"color": (200, 60, 60)},
        )

    @property
    def aware(self) -> bool:
        """True if enemy knows where the player is (or was recently)."""
        return self._last_known_pos is not None

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(self.pos.x - 3, self.pos.y - 3, 6, 6)

    @property
    def alive(self) -> bool:
        return self.state != EnemyState.DEAD

    def hear_sound(self, source_pos: glm.vec2) -> None:
        """React to a loud sound — become alert and investigate."""
        if self.state in (EnemyState.DEAD, EnemyState.PURSUING, EnemyState.ATTACKING):
            return
        self._last_known_pos = glm.vec2(source_pos)
        self._alert_timer = _ALERT_TIMEOUT
        if self.state in (EnemyState.IDLE, EnemyState.ROAMING):
            self.state = EnemyState.ALERT

    def take_damage(
        self,
        amount: int,
        knockback: glm.vec2 | None = None,
        source_pos: glm.vec2 | None = None,
    ) -> None:
        self.health -= amount
        self._stun_timer = 0.15
        if knockback is not None:
            self.vel = knockback
        # Getting hit alerts and gives a rough idea of the source direction.
        # We set last_known_pos so the enemy investigates the attacker's
        # position even if they can't see them yet.
        if source_pos is not None:
            self._last_known_pos = glm.vec2(source_pos)
        if self.state in (EnemyState.IDLE, EnemyState.ROAMING):
            self.state = EnemyState.ALERT
            self._alert_timer = _ALERT_TIMEOUT
        self.emitter.vel = glm.vec2(
            random.uniform(-1, 1), random.uniform(-1, 1)
        )
        self.emitter.burst(5)
        if self.health <= 0:
            self.state = EnemyState.DEAD
            self.emitter.vel = None
            self.emitter.burst(15)

    def update(self, dt: float) -> None:
        if self.state == EnemyState.DEAD:
            self.emitter.pos = self.pos
            self.emitter.update(dt)
            return

        self._attack_timer = max(0.0, self._attack_timer - dt)
        self._path_timer = max(0.0, self._path_timer - dt)
        self._roam_timer = max(0.0, self._roam_timer - dt)

        if self._alert_timer > 0:
            self._alert_timer -= dt
            if self._alert_timer <= 0:
                # Alert expired — forget player position
                self._last_known_pos = None

        if self._stun_timer > 0:
            self._stun_timer -= dt
            self.pos += self.vel * dt
            self.vel *= 0.85
        else:
            self.pos += self.vel * dt

        self.emitter.pos = self.pos
        self.emitter.update(dt)

    def _pick_roam_target(self) -> None:
        """Pick a random nearby point to roam toward."""
        angle = random.uniform(0, 6.283)
        dist = random.uniform(15, 40)
        self._roam_target = self.pos + glm.vec2(
            dist * glm.cos(angle), dist * glm.sin(angle)
        )
        self._roam_timer = random.uniform(2.0, 4.0)

    def update_ai(
        self,
        player_pos: glm.vec2,
        has_los: bool,
        waypoint: glm.vec2 | None,
    ) -> bool:
        """Update AI state. Returns True if enemy wants to fire (ranged only).

        has_los: True only if the enemy actually has clear line-of-sight AND
                 the player is within sight range.
        waypoint: pathfinding waypoint toward _last_known_pos (NOT the live
                  player position). None if unaware.
        """
        if self.state == EnemyState.DEAD or self._stun_timer > 0:
            return False

        # --- Acquire / refresh awareness ---
        if has_los:
            self._last_known_pos = glm.vec2(player_pos)
            self._alert_timer = _ALERT_TIMEOUT
            if self.state not in (EnemyState.ATTACKING, EnemyState.FLEEING):
                self.state = EnemyState.PURSUING
        elif self.state in (EnemyState.PURSUING, EnemyState.ATTACKING):
            # Lost LOS while actively engaged — go alert
            self.state = EnemyState.ALERT
            self._alert_timer = _ALERT_TIMEOUT
        elif self.state == EnemyState.ALERT and self._alert_timer <= 0:
            self.state = EnemyState.IDLE
            self._last_known_pos = None
            self.target_waypoint = None

        # Idle → roaming
        if self.state == EnemyState.IDLE and self._roam_timer <= 0:
            self.state = EnemyState.ROAMING
            self._pick_roam_target()

        # --- Execute behavior ---
        if self.state == EnemyState.IDLE:
            self.vel = glm.vec2()
        elif self.state == EnemyState.ROAMING:
            if self._roam_target is not None:
                diff = self._roam_target - self.pos
                if glm.length(diff) > 3:
                    self.vel = glm.normalize(diff) * self.speed * 0.4
                else:
                    self.state = EnemyState.IDLE
                    self._roam_timer = random.uniform(2.0, 5.0)
                    self.vel = glm.vec2()
            else:
                self.state = EnemyState.IDLE
                self.vel = glm.vec2()
        elif self.state == EnemyState.ALERT:
            # Move toward last-known position via waypoint
            if waypoint is not None:
                diff = waypoint - self.pos
                if glm.length(diff) > 2:
                    self.vel = glm.normalize(diff) * self.speed * 0.7
                else:
                    self.vel = glm.vec2()
            else:
                self.vel = glm.vec2()
        elif self.state == EnemyState.PURSUING:
            # Has LOS — move directly toward player
            if has_los:
                diff = player_pos - self.pos
                if glm.length(diff) > 2:
                    self.vel = glm.normalize(diff) * self.speed
                else:
                    self.vel = glm.vec2()
            elif waypoint is not None:
                diff = waypoint - self.pos
                if glm.length(diff) > 2:
                    self.vel = glm.normalize(diff) * self.speed
                else:
                    self.vel = glm.vec2()
            else:
                self.vel = glm.vec2()

        return False

    def _draw_health_bar(self, surface: pygame.Surface, p: glm.vec2) -> None:
        if self.health >= self.max_health:
            return
        bar_w = 10
        bar_h = 2
        bx = int(p.x) - bar_w // 2
        by = int(p.y) - 6
        fill = max(0, int(bar_w * self.health / self.max_health))
        pygame.draw.rect(surface, (40, 20, 20), (bx, by, bar_w, bar_h))
        if fill > 0:
            pygame.draw.rect(surface, (200, 50, 50), (bx, by, fill, bar_h))


class MeleeEnemy(Enemy):
    __slots__ = ["_retreat_timer"]

    def __init__(self, pos: glm.vec2) -> None:
        super().__init__(pos, speed=45, health=25, damage=15)
        self.attack_cooldown = 0.8
        self._retreat_timer: float = 0.0
        self.emitter.particle_kwargs = {"color": (220, 120, 40)}

    def update(self, dt: float) -> None:
        super().update(dt)
        if self._retreat_timer > 0:
            self._retreat_timer -= dt
            if self._retreat_timer <= 0 and self.state == EnemyState.FLEEING:
                self.state = EnemyState.PURSUING

    def start_retreat(self, player_pos: glm.vec2) -> None:
        """Back away from player after landing a hit."""
        self.state = EnemyState.FLEEING
        self._retreat_timer = _RETREAT_DURATION
        diff = self.pos - player_pos
        if glm.length(diff) > 0.5:
            self.vel = glm.normalize(diff) * self.speed * 1.5
        else:
            self.vel = glm.vec2(random.uniform(-1, 1), random.uniform(-1, 1)) * self.speed

    def update_ai(
        self,
        player_pos: glm.vec2,
        has_los: bool,
        waypoint: glm.vec2 | None,
    ) -> bool:
        if self.state == EnemyState.DEAD or self._stun_timer > 0:
            return False

        dist_to_player = glm.distance(self.pos, player_pos)

        # Fleeing state is handled by timer — don't override velocity
        if self.state == EnemyState.FLEEING:
            return False

        # --- Acquire / refresh awareness ---
        if has_los:
            self._last_known_pos = glm.vec2(player_pos)
            self._alert_timer = _ALERT_TIMEOUT
            if dist_to_player < 10:
                self.state = EnemyState.ATTACKING
            else:
                self.state = EnemyState.PURSUING
        elif self.state in (EnemyState.PURSUING, EnemyState.ATTACKING):
            self.state = EnemyState.ALERT
            self._alert_timer = _ALERT_TIMEOUT
        elif self.state == EnemyState.ALERT and self._alert_timer <= 0:
            self.state = EnemyState.IDLE
            self._last_known_pos = None
            self.target_waypoint = None

        # Idle → roaming
        if self.state == EnemyState.IDLE and self._roam_timer <= 0:
            self.state = EnemyState.ROAMING
            self._pick_roam_target()

        # --- Execute behavior ---
        if self.state == EnemyState.IDLE:
            self.vel = glm.vec2()
        elif self.state == EnemyState.ROAMING:
            if self._roam_target is not None:
                diff = self._roam_target - self.pos
                if glm.length(diff) > 3:
                    self.vel = glm.normalize(diff) * self.speed * 0.4
                else:
                    self.state = EnemyState.IDLE
                    self._roam_timer = random.uniform(2.0, 5.0)
                    self.vel = glm.vec2()
            else:
                self.state = EnemyState.IDLE
                self.vel = glm.vec2()
        elif self.state in (EnemyState.PURSUING, EnemyState.ATTACKING):
            if has_los:
                direction = player_pos - self.pos
            elif waypoint is not None:
                direction = waypoint - self.pos
            else:
                direction = glm.vec2()
            if glm.length(direction) > 1:
                speed = 70.0 if dist_to_player < 40 and has_los else self.speed
                self.vel = glm.normalize(direction) * speed
            else:
                self.vel = glm.vec2()
        elif self.state == EnemyState.ALERT:
            if waypoint is not None:
                diff = waypoint - self.pos
                if glm.length(diff) > 2:
                    self.vel = glm.normalize(diff) * self.speed * 0.7
                else:
                    self.vel = glm.vec2()
            else:
                self.vel = glm.vec2()

        return False

    def draw(self, surface: pygame.Surface, offset: glm.vec2 = glm.vec2()) -> None:
        self.emitter.draw(surface, offset)
        if self.state == EnemyState.DEAD:
            return
        p = self.pos - offset
        # Red-orange diamond
        pts = [
            (p.x, p.y - 3),
            (p.x + 3, p.y),
            (p.x, p.y + 3),
            (p.x - 3, p.y),
        ]
        pygame.draw.polygon(surface, (220, 100, 40), pts)
        self._draw_health_bar(surface, p)


class RangedEnemy(Enemy):
    __slots__ = ["preferred_range", "fire_rate", "_fire_timer"]

    def __init__(self, pos: glm.vec2) -> None:
        super().__init__(pos, speed=25, health=35, damage=8)
        self.preferred_range: float = 80.0
        self.fire_rate: float = 1.5
        self._fire_timer: float = 0.0
        self.attack_cooldown = self.fire_rate
        self.emitter.particle_kwargs = {"color": (160, 80, 200)}

    def update(self, dt: float) -> None:
        super().update(dt)
        self._fire_timer = max(0.0, self._fire_timer - dt)

    def update_ai(
        self,
        player_pos: glm.vec2,
        has_los: bool,
        waypoint: glm.vec2 | None,
    ) -> bool:
        if self.state == EnemyState.DEAD or self._stun_timer > 0:
            return False

        dist_to_player = glm.distance(self.pos, player_pos)
        wants_fire = False

        if has_los:
            self._last_known_pos = glm.vec2(player_pos)
            self._alert_timer = _ALERT_TIMEOUT

            direction = player_pos - self.pos
            if glm.length(direction) > 1:
                norm_dir = glm.normalize(direction)
                if dist_to_player < self.preferred_range * 0.5:
                    # Too close — flee backwards
                    self.state = EnemyState.FLEEING
                    self.vel = -norm_dir * self.speed * 1.3
                elif dist_to_player > self.preferred_range * 1.4:
                    # Too far — approach
                    self.state = EnemyState.PURSUING
                    self.vel = norm_dir * self.speed
                else:
                    # In range — strafe and attack
                    self.state = EnemyState.ATTACKING
                    perp = glm.vec2(-norm_dir.y, norm_dir.x)
                    self.vel = perp * self.speed * 0.7
            else:
                self.vel = glm.vec2()

            if self._fire_timer <= 0 and dist_to_player < 150:
                wants_fire = True
                self._fire_timer = self.fire_rate
        elif self.state in (EnemyState.PURSUING, EnemyState.ATTACKING, EnemyState.FLEEING):
            # Lost LOS — go alert
            self.state = EnemyState.ALERT
            self._alert_timer = _ALERT_TIMEOUT
            if waypoint is not None:
                diff = waypoint - self.pos
                if glm.length(diff) > 2:
                    self.vel = glm.normalize(diff) * self.speed
                else:
                    self.vel = glm.vec2()
            else:
                self.vel = glm.vec2()
        elif self.state == EnemyState.ALERT:
            if self._alert_timer <= 0:
                self.state = EnemyState.IDLE
                self._last_known_pos = None
                self.target_waypoint = None
                self.vel = glm.vec2()
            elif waypoint is not None:
                diff = waypoint - self.pos
                if glm.length(diff) > 2:
                    self.vel = glm.normalize(diff) * self.speed
                else:
                    self.vel = glm.vec2()
        elif self.state == EnemyState.IDLE:
            if self._roam_timer <= 0:
                self.state = EnemyState.ROAMING
                self._pick_roam_target()
            self.vel = glm.vec2()
        elif self.state == EnemyState.ROAMING:
            if self._roam_target is not None:
                diff = self._roam_target - self.pos
                if glm.length(diff) > 3:
                    self.vel = glm.normalize(diff) * self.speed * 0.4
                else:
                    self.state = EnemyState.IDLE
                    self._roam_timer = random.uniform(2.0, 5.0)
                    self.vel = glm.vec2()

        return wants_fire

    def draw(self, surface: pygame.Surface, offset: glm.vec2 = glm.vec2()) -> None:
        self.emitter.draw(surface, offset)
        if self.state == EnemyState.DEAD:
            return
        p = self.pos - offset
        # Purple square
        pygame.draw.rect(
            surface, (140, 60, 180), (p.x - 3, p.y - 3, 6, 6)
        )
        self._draw_health_bar(surface, p)
