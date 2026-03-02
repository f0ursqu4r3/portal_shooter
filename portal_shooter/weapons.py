from __future__ import annotations

import enum
import math
from dataclasses import dataclass


class WeaponKind(enum.IntEnum):
    PISTOL = 0
    SHOTGUN = 1
    SMG = 2
    RIFLE = 3


@dataclass(frozen=True)
class WeaponStats:
    fire_rate: float
    bullet_speed: int
    damage: int
    ammo_per_shot: int  # 0 = unlimited
    max_ammo: int  # 0 = unlimited
    recoil: float
    spread: float  # radians
    pellets: int
    piercing: bool
    color: tuple[int, int, int]
    pickup_ammo: int = 0


WEAPON_STATS: dict[WeaponKind, WeaponStats] = {
    WeaponKind.PISTOL: WeaponStats(
        fire_rate=1 / 8,
        bullet_speed=500,
        damage=10,
        ammo_per_shot=0,
        max_ammo=0,
        recoil=0.5,
        spread=0.0,
        pellets=1,
        piercing=False,
        color=(180, 180, 180),
    ),
    WeaponKind.SHOTGUN: WeaponStats(
        fire_rate=1 / 2,
        bullet_speed=400,
        damage=6,
        ammo_per_shot=1,
        max_ammo=20,
        recoil=2.0,
        spread=math.radians(30),
        pellets=5,
        piercing=False,
        color=(220, 160, 60),
        pickup_ammo=8,
    ),
    WeaponKind.SMG: WeaponStats(
        fire_rate=1 / 40,
        bullet_speed=450,
        damage=5,
        ammo_per_shot=1,
        max_ammo=120,
        recoil=0.8,
        spread=0.0,
        pellets=1,
        piercing=False,
        color=(100, 100, 100),
        pickup_ammo=30,
    ),
    WeaponKind.RIFLE: WeaponStats(
        fire_rate=1 / 1.5,
        bullet_speed=900,
        damage=30,
        ammo_per_shot=1,
        max_ammo=15,
        recoil=2.5,
        spread=0.0,
        pellets=1,
        piercing=True,
        color=(100, 180, 255),
        pickup_ammo=5,
    ),
}
