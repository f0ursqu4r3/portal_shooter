from __future__ import annotations

from typing import TYPE_CHECKING

from pyglm import glm

if TYPE_CHECKING:
    from portal_shooter.entities.player import Player


class Camera:
    __slots__ = ["pos", "offset", "target"]

    def __init__(
        self,
        pos: glm.vec2,
        target: Player | None = None,
        offset: glm.vec2 | None = None,
    ) -> None:
        self.pos: glm.vec2 = glm.vec2(pos)
        self.target: Player | None = target
        self.offset: glm.vec2 = glm.vec2(offset) if offset else glm.vec2()

    def update(self) -> None:
        if not self.target:
            return
        if hasattr(self.target, "vel") and hasattr(self.target, "speed"):
            self.pos = (
                glm.lerp(
                    self.pos,
                    self.target.pos + (self.target.vel * self.target.speed),
                    0.1,
                )
                + self.offset
            )
        else:
            self.pos = glm.lerp(self.pos, self.target.pos, 0.1) + self.offset
