from __future__ import annotations

import pygame
from pyglm import glm

from portal_shooter.entities.entity import Entity


class Bullet(Entity):
    __slots__ = [
        "speed",
        "_speed",
        "life",
        "damage",
        "piercing",
        "color",
        "_trail_len",
    ]

    def __init__(
        self,
        pos: glm.vec2,
        vel: glm.vec2,
        *,
        speed: int = 100,
        damage: int = 10,
        piercing: bool = False,
        color: tuple[int, int, int] = (100, 100, 100),
    ) -> None:
        super().__init__(pos, vel)
        self.speed: int = speed
        self._speed: int = speed
        # Lifetime caps max travel distance to ~1500 units (just over map diagonal)
        self.life: float = 1500 / speed
        self.damage: int = damage
        self.piercing: bool = piercing
        self.color: tuple[int, int, int] = color
        # Trail length proportional to speed — faster rounds leave longer streaks
        self._trail_len: float = speed * 0.018

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(self.pos - glm.vec2(1), (2, 2))

    def update(self, dt: float) -> None:
        self.pos += self.vel * self.speed * dt
        self.life -= dt

    def draw(self, surface: pygame.Surface, offset: glm.vec2 = glm.vec2()) -> None:
        if not self.vel:
            return

        ox, oy = offset.x, offset.y
        nvx, nvy = glm.normalize(self.vel)

        # Fade during last 20% of lifetime
        max_life = 1500 / self.speed
        life_fade = min(1.0, self.life / (max_life * 0.2))

        r, g, b = self.color
        tl = self._trail_len

        # Draw trail as 3 segments with decreasing alpha (tail -> tip)
        for i in range(3):
            t0 = i / 3
            t1 = (i + 1) / 3
            alpha = int((1 - t1) * 160 * life_fade)
            if alpha <= 0:
                continue
            x0 = self.pos.x - nvx * tl * t0 - ox
            y0 = self.pos.y - nvy * tl * t0 - oy
            x1 = self.pos.x - nvx * tl * t1 - ox
            y1 = self.pos.y - nvy * tl * t1 - oy
            pygame.draw.line(
                surface, (r, g, b, alpha), (int(x0), int(y0)), (int(x1), int(y1))
            )

        # Bright core at tip — white-hot center blended toward weapon color
        tip_alpha = int(230 * life_fade)
        tr = min(255, r + 120)
        tg = min(255, g + 120)
        tb = min(255, b + 120)
        sx = int(self.pos.x - ox)
        sy = int(self.pos.y - oy)
        surface.set_at((sx, sy), (tr, tg, tb, tip_alpha))

        # Sub-pixel bright leading edge (1px ahead of tip)
        lx = int(self.pos.x + nvx * 1 - ox)
        ly = int(self.pos.y + nvy * 1 - oy)
        surface.set_at((lx, ly), (255, 255, 255, int(180 * life_fade)))
