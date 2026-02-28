from __future__ import annotations

import pygame
from pyglm import glm

Wall = tuple[glm.vec2, glm.vec2]

VOID_COLOR = (10, 8, 12)
FLOOR_COLOR = (40, 35, 42)
WALL_COLOR = (100, 90, 100)


class Room:
    __slots__ = ["vertices", "walls", "center", "bounds"]

    def __init__(self, vertices: list[glm.vec2]) -> None:
        self.vertices: list[glm.vec2] = vertices
        self.walls: list[Wall] = []
        for i in range(len(vertices)):
            self.walls.append((vertices[i], vertices[(i + 1) % len(vertices)]))
        xs = [v.x for v in vertices]
        ys = [v.y for v in vertices]
        self.bounds: pygame.Rect = pygame.Rect(
            min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
        )
        self.center: glm.vec2 = glm.vec2(
            self.bounds.centerx, self.bounds.centery
        )


class BSPNode:
    __slots__ = ["rect", "left", "right", "room"]

    def __init__(self, rect: pygame.Rect) -> None:
        self.rect: pygame.Rect = rect
        self.left: BSPNode | None = None
        self.right: BSPNode | None = None
        self.room: Room | None = None
