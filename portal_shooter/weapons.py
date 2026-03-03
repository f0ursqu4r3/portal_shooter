from __future__ import annotations

import enum
import math
from dataclasses import dataclass


class WeaponKind(enum.IntEnum):
    PISTOL = 0
    SHOTGUN = 1
    SMG = 2
    RIFLE = 3
    PORTAL_GUN = 4


@dataclass(frozen=True)
class WeaponStats:
    fire_rate: float
    bullet_speed: int
    damage: int
    ammo_per_shot: int  # 0 = unlimited
    magazine_size: int  # 0 = no reload needed (pistol)
    reload_time: float  # seconds
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
        magazine_size=0,
        reload_time=0.0,
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
        magazine_size=6,
        reload_time=1.8,
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
        magazine_size=30,
        reload_time=1.5,
        recoil=0.8,
        spread=0.0,
        pellets=1,
        piercing=False,
        color=(100, 100, 100),
        pickup_ammo=15,
    ),
    WeaponKind.RIFLE: WeaponStats(
        fire_rate=1 / 1.5,
        bullet_speed=900,
        damage=30,
        ammo_per_shot=1,
        magazine_size=5,
        reload_time=2.0,
        recoil=2.5,
        spread=0.0,
        pellets=1,
        piercing=True,
        color=(100, 180, 255),
        pickup_ammo=5,
    ),
    WeaponKind.PORTAL_GUN: WeaponStats(
        fire_rate=0.15,
        bullet_speed=0,
        damage=0,
        ammo_per_shot=0,
        magazine_size=0,
        reload_time=0.0,
        recoil=0,
        spread=0.0,
        pellets=0,
        piercing=False,
        color=(255, 127, 0),
    ),
}
