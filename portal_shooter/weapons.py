from __future__ import annotations

import enum
import math
from dataclasses import dataclass


class AmmoType(enum.Enum):
    LIGHT = "light"
    MEDIUM = "medium"
    HEAVY = "heavy"
    SHELLS = "shells"
    GRENADE = "grenade"
    ROCKET = "rocket"


class MeleeStyle(enum.Enum):
    NONE = "none"
    STAB = "stab"   # narrow thrust (knife)
    ARC = "arc"     # sweeping arc (sword, axe)


class WeaponKind(enum.IntEnum):
    PISTOL = 0
    SHOTGUN = 1
    SMG = 2
    RIFLE = 3
    MACHINE_GUN = 4
    SNIPER_RIFLE = 5
    GRENADE_LAUNCHER = 6
    ROCKET_LAUNCHER = 7
    KNIFE = 8
    SWORD = 9
    AXE = 10


@dataclass(frozen=True)
class WeaponStats:
    fire_rate: float
    bullet_speed: int
    damage: int
    ammo_per_shot: int  # 0 = unlimited
    magazine_size: int  # 0 = no reload needed
    reload_time: float  # seconds
    recoil: float
    spread: float  # radians
    pellets: int
    piercing: bool
    color: tuple[int, int, int]
    ammo_type: AmmoType | None = None
    pickup_ammo: int = 0
    melee_style: MeleeStyle = MeleeStyle.NONE
    melee_range: float = 0.0
    melee_arc_half: float = 0.0
    melee_knockback: float = 0.0


AMMO_COLORS: dict[AmmoType, tuple[int, int, int]] = {
    AmmoType.LIGHT: (180, 180, 180),
    AmmoType.MEDIUM: (160, 140, 80),
    AmmoType.HEAVY: (100, 180, 255),
    AmmoType.SHELLS: (220, 160, 60),
    AmmoType.GRENADE: (180, 200, 60),
    AmmoType.ROCKET: (200, 80, 60),
}

AMMO_NAMES: dict[AmmoType, str] = {
    AmmoType.LIGHT: "Light",
    AmmoType.MEDIUM: "Medium",
    AmmoType.HEAVY: "Heavy",
    AmmoType.SHELLS: "Shell",
    AmmoType.GRENADE: "Grenade",
    AmmoType.ROCKET: "Rocket",
}

AMMO_PICKUP_QTY: dict[AmmoType, int] = {
    AmmoType.LIGHT: 24,
    AmmoType.MEDIUM: 30,
    AmmoType.HEAVY: 5,
    AmmoType.SHELLS: 8,
    AmmoType.GRENADE: 3,
    AmmoType.ROCKET: 2,
}


WEAPON_STATS: dict[WeaponKind, WeaponStats] = {
    WeaponKind.PISTOL: WeaponStats(
        fire_rate=1 / 8,
        bullet_speed=500,
        damage=10,
        ammo_per_shot=1,
        magazine_size=12,
        reload_time=1.0,
        recoil=0.5,
        spread=0.0,
        pellets=1,
        piercing=False,
        color=(180, 180, 180),
        ammo_type=AmmoType.LIGHT,
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
        ammo_type=AmmoType.SHELLS,
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
        ammo_type=AmmoType.LIGHT,
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
        ammo_type=AmmoType.HEAVY,
        pickup_ammo=5,
    ),
    WeaponKind.MACHINE_GUN: WeaponStats(
        fire_rate=1 / 20,
        bullet_speed=420,
        damage=8,
        ammo_per_shot=1,
        magazine_size=50,
        reload_time=2.5,
        recoil=0.6,
        spread=math.radians(5),
        pellets=1,
        piercing=False,
        color=(160, 140, 80),
        ammo_type=AmmoType.MEDIUM,
    ),
    WeaponKind.SNIPER_RIFLE: WeaponStats(
        fire_rate=1.2,
        bullet_speed=1200,
        damage=50,
        ammo_per_shot=1,
        magazine_size=3,
        reload_time=2.5,
        recoil=3.5,
        spread=0.0,
        pellets=1,
        piercing=True,
        color=(180, 100, 255),
        ammo_type=AmmoType.HEAVY,
    ),
    WeaponKind.GRENADE_LAUNCHER: WeaponStats(
        fire_rate=0.8,
        bullet_speed=0,
        damage=50,
        ammo_per_shot=1,
        magazine_size=1,
        reload_time=1.8,
        recoil=2.0,
        spread=0.0,
        pellets=1,
        piercing=False,
        color=(180, 200, 60),
        ammo_type=AmmoType.GRENADE,
    ),
    WeaponKind.ROCKET_LAUNCHER: WeaponStats(
        fire_rate=0.5,
        bullet_speed=0,
        damage=70,
        ammo_per_shot=1,
        magazine_size=1,
        reload_time=2.5,
        recoil=3.0,
        spread=0.0,
        pellets=1,
        piercing=False,
        color=(200, 80, 60),
        ammo_type=AmmoType.ROCKET,
    ),
    WeaponKind.KNIFE: WeaponStats(
        fire_rate=0.2,
        bullet_speed=0,
        damage=15,
        ammo_per_shot=0,
        magazine_size=0,
        reload_time=0,
        recoil=0,
        spread=0.0,
        pellets=1,
        piercing=False,
        color=(200, 200, 200),
        melee_style=MeleeStyle.STAB,
        melee_range=20.0,
        melee_arc_half=math.radians(10),
        melee_knockback=15.0,
    ),
    WeaponKind.SWORD: WeaponStats(
        fire_rate=0.4,
        bullet_speed=0,
        damage=25,
        ammo_per_shot=0,
        magazine_size=0,
        reload_time=0,
        recoil=0,
        spread=0.0,
        pellets=1,
        piercing=True,
        color=(100, 180, 255),
        melee_style=MeleeStyle.ARC,
        melee_range=25.0,
        melee_arc_half=math.radians(45),
        melee_knockback=25.0,
    ),
    WeaponKind.AXE: WeaponStats(
        fire_rate=0.7,
        bullet_speed=0,
        damage=45,
        ammo_per_shot=0,
        magazine_size=0,
        reload_time=0,
        recoil=0,
        spread=0.0,
        pellets=1,
        piercing=True,
        color=(200, 120, 60),
        melee_style=MeleeStyle.ARC,
        melee_range=30.0,
        melee_arc_half=math.radians(60),
        melee_knockback=40.0,
    ),
}

MELEE_WEAPONS: frozenset[WeaponKind] = frozenset({
    WeaponKind.KNIFE, WeaponKind.SWORD, WeaponKind.AXE,
})
