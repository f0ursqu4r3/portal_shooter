from __future__ import annotations

from typing import Any

from pyglm import glm


def direction(p1: glm.vec2, p2: glm.vec2, p3: glm.vec2) -> float:
    return glm.cross(p3 - p1, p2 - p1)


def intersect(p1: glm.vec2, p2: glm.vec2, p3: glm.vec2, p4: glm.vec2) -> bool:
    d1 = direction(p3, p4, p1)
    d2 = direction(p3, p4, p2)
    d3 = direction(p1, p2, p3)
    d4 = direction(p1, p2, p4)

    return ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and (
        (d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)
    )


def point_dist_to_line(point: glm.vec2, segment: tuple[glm.vec2, glm.vec2]) -> float:
    p1, p2 = segment
    v1 = p2 - p1
    v2 = point - p1
    t = glm.dot(v2, v1) / glm.dot(v1, v1)
    if t < 0:
        return glm.length(p1 - point)
    if t > 1:
        return glm.length(p2 - point)
    return glm.length(p1 + v1 * t - point)


def get_collisions(entity: Any, others: list[Any]) -> list[Any]:
    if not hasattr(entity, "rect"):
        raise AttributeError("Entity must have a rect attribute")
    return [o for o in others if hasattr(o, "rect") and o.rect.colliderect(entity.rect)]


def remap(val: float, min_in: float, max_in: float, min_out: float, max_out: float, clamp: bool = True) -> float:
    if clamp:
        return min(
            max(
                min_out,
                (val - min_in) * (max_out - min_out) / (max_in - min_in) + min_out,
            ),
            max_out,
        )
    return (val - min_in) / (max_in - min_in) * (max_out - min_out) + min_out


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t
