from __future__ import annotations

import enum
import math

import pygame
from pyglm import glm

from portal_shooter.entities.entity import Entity
from portal_shooter.weapons import WEAPON_STATS, WeaponKind


class PickupKind(enum.Enum):
    HEALTH = "health"
    SPEED = "speed"
    AMMO = "ammo"
    WEAPON = "weapon"
    ARMOR = "armor"
    KEY = "key"
    GRENADE = "grenade"


_COLORS: dict[PickupKind, tuple[int, int, int]] = {
    PickupKind.HEALTH: (0, 200, 80),
    PickupKind.SPEED: (220, 200, 40),
    PickupKind.AMMO: (100, 200, 220),
    PickupKind.ARMOR: (120, 160, 220),
    PickupKind.KEY: (255, 200, 50),
    PickupKind.GRENADE: (180, 200, 60),
}

_SIZE = 4  # half-size for collision rect
PICKUP_RANGE = 16  # world-space px for F-key pickup (~2x collision rect)

_NAMES: dict[PickupKind, str] = {
    PickupKind.HEALTH: "Health",
    PickupKind.SPEED: "Speed",
    PickupKind.AMMO: "Ammo",
    PickupKind.ARMOR: "Armor",
    PickupKind.KEY: "Key",
    PickupKind.GRENADE: "Grenade",
}

_WEAPON_NAMES: dict[WeaponKind, str] = {
    WeaponKind.PISTOL: "Pistol",
    WeaponKind.SHOTGUN: "Shotgun",
    WeaponKind.SMG: "SMG",
    WeaponKind.RIFLE: "Rifle",
}


class Pickup(Entity):
    __slots__ = ["kind", "color", "age", "weapon_kind", "quantity"]

    def __init__(
        self,
        pos: glm.vec2,
        kind: PickupKind,
        weapon_kind: WeaponKind | None = None,
        quantity: int = 1,
    ) -> None:
        super().__init__(pos)
        self.kind: PickupKind = kind
        self.weapon_kind: WeaponKind | None = weapon_kind
        if weapon_kind is not None and kind in (PickupKind.WEAPON, PickupKind.AMMO):
            self.color: tuple[int, int, int] = WEAPON_STATS[weapon_kind].color
        else:
            self.color = _COLORS.get(kind, (200, 200, 200))
        self.age: float = 0.0
        self.quantity: int = quantity

    @property
    def display_name(self) -> str:
        if self.kind == PickupKind.WEAPON and self.weapon_kind is not None:
            return _WEAPON_NAMES.get(self.weapon_kind, "Weapon")
        if self.kind == PickupKind.AMMO and self.weapon_kind is not None:
            wname = _WEAPON_NAMES.get(self.weapon_kind, "")
            return f"{wname} Ammo"
        return _NAMES.get(self.kind, "Item")

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(self.pos.x - _SIZE, self.pos.y - _SIZE, _SIZE * 2, _SIZE * 2)

    def update(self, dt: float) -> None:
        self.age += dt

    def draw(self, surface: pygame.Surface, offset: glm.vec2 = glm.vec2()) -> None:
        bob = math.sin(self.age * 3) * 2
        p = self.pos - offset + glm.vec2(0, bob)

        if self.kind == PickupKind.HEALTH:
            # Draw a + cross
            pygame.draw.line(surface, self.color, (p.x - 3, p.y), (p.x + 3, p.y), 1)
            pygame.draw.line(surface, self.color, (p.x, p.y - 3), (p.x, p.y + 3), 1)
        elif self.kind == PickupKind.SPEED:
            # Draw a diamond
            pts = [
                (p.x, p.y - 3),
                (p.x + 3, p.y),
                (p.x, p.y + 3),
                (p.x - 3, p.y),
            ]
            pygame.draw.polygon(surface, self.color, pts, 1)
        elif self.kind == PickupKind.AMMO:
            # Ammo: small square
            pygame.draw.rect(
                surface, self.color, (p.x - 2, p.y - 2, 5, 5), 1
            )
        elif self.kind == PickupKind.ARMOR:
            # Shield outline
            pts = [
                (p.x - 3, p.y - 3),
                (p.x + 3, p.y - 3),
                (p.x + 3, p.y + 1),
                (p.x, p.y + 4),
                (p.x - 3, p.y + 1),
            ]
            pygame.draw.polygon(surface, self.color, pts, 1)
        elif self.kind == PickupKind.KEY:
            # Key shape: circle head + line shaft + teeth
            pygame.draw.circle(surface, self.color, (p.x - 1, p.y - 1), 2, 1)
            pygame.draw.line(surface, self.color, (p.x + 1, p.y), (p.x + 4, p.y), 1)
            pygame.draw.line(surface, self.color, (p.x + 3, p.y), (p.x + 3, p.y + 2), 1)
        elif self.kind == PickupKind.GRENADE:
            # Small circle + fuse line
            pygame.draw.circle(surface, self.color, (p.x, p.y), 2)
            pygame.draw.line(surface, self.color, (p.x, p.y - 2), (p.x + 2, p.y - 4), 1)
        else:
            # Weapon: small gun silhouette (horizontal barrel + grip)
            pygame.draw.line(surface, self.color, (p.x - 4, p.y), (p.x + 4, p.y), 1)
            pygame.draw.line(surface, self.color, (p.x + 1, p.y), (p.x + 1, p.y + 3), 1)
