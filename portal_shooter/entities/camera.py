from __future__ import annotations

from typing import TYPE_CHECKING

from pyglm import glm

if TYPE_CHECKING:
    from portal_shooter.entities.player import Player


class Camera:
    __slots__ = ["pos", "offset", "shake", "target", "map_bounds"]

    def __init__(
        self,
        pos: glm.vec2,
        target: Player | None = None,
        offset: glm.vec2 | None = None,
        map_bounds: glm.vec2 | None = None,
    ) -> None:
        self.pos: glm.vec2 = glm.vec2(pos)
        self.target: Player | None = target
        self.offset: glm.vec2 = glm.vec2(offset) if offset else glm.vec2()
        self.shake: glm.vec2 = glm.vec2()
        self.map_bounds: glm.vec2 | None = map_bounds

    def update(self, dt: float, screen_size: glm.vec2) -> None:
        if not self.target:
            return
        look_ahead = glm.vec2()
        if hasattr(self.target, "vel") and self.target.vel != glm.vec2():
            look_ahead = glm.normalize(self.target.vel) * 15
        self.pos = (
            glm.lerp(self.pos, self.target.pos + look_ahead, 1 - 0.1**dt)
            + self.offset
        )
        self.shake *= 0.85
