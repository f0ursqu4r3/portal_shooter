from __future__ import annotations

import pygame
from pyglm import glm


class Entity:
    __slots__ = ["pos", "vel"]

    def __init__(self, pos: glm.vec2, vel: glm.vec2 | None = None) -> None:
        self.pos: glm.vec2 = glm.vec2(pos)
        self.vel: glm.vec2 = glm.vec2(vel) if vel else glm.vec2()

    def update(self, dt: float) -> None: ...

    def draw(self, surface: pygame.Surface, offset: glm.vec2 = glm.vec2()) -> None: ...
